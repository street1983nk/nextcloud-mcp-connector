# MCP Connector für Nextcloud (Arbeitstitel)

## What This Is

Ein schlankes MCP-only-ExApp für Nextcloud: Nutzer installieren es per Klick aus dem Nextcloud App Store und verbinden damit ihre Nextcloud (Dateien, Kalender, Notizen, Aufgaben, Kontakte, Deck, Talk, Tables, Mail strikt lesend) als Werkzeug mit KI-Assistenten wie Claude, MUCGPT, Cursor oder eigenen Agenten. Zielgruppe v1: Entwickler und Selfhoster; ab Phase 2 deutsche Behörden und Unternehmen mit Datenschutz-Anforderungen (souveräner Arbeitsplatz, openDesk).

## Core Value

Die zugänglichste und sauberste MCP-Anbindung für Nextcloud: per Klick installierbar, spec-konformes OAuth statt App-Passwort-Gebastel, und der Assistent sieht niemals mehr als der angemeldete Nutzer.

## Current Milestone

Keiner aktiv. v1.6 wurde am 2026-09-26 abgeschlossen; der nächste Zyklus startet mit `/gsd:new-milestone`, sobald das Owner-Thema feststeht. Kandidat ist files_update (Schreibzugriff mit harten Schienen, Massnahmenkatalog in scripts/docs/specs/ideation-isv-monetarisierung-2026-08-25/brainstorm-schreibzugriffe-2026-09-25.md), extern getaktet durch Daniels Antwort auf das Design-Issue-Angebot.

## Current State

**v1.6 shipped 2026-09-26** (kein separates Milestone-Audit, wie v1.5; 15/15 Requirements, jede Phase goal-backward verifiziert, secure-phase 24 mit 38/38 Threats, 4428 Tests): Der Connector nimmt einen nach RFC 8693 getauschten Keycloak-Token (F13-Orchestrator) an und handelt unter dem gemappten Nextcloud-Konto, ohne die Rechtegrenze aufzuweichen. Der Pfad ist ab Werk aus, im Aus-Zustand byte-gleich zu vorher, vor-authentisch gedrosselt, hash-verkettet auditiert (actor-Spalte, Abweisungskette x:exchange), per `occ mcp_connector:exchange:check` ohne Live-Zugriff verprobbar und in docs/token-exchange.md mit ehrlich markierten Grenzen dokumentiert. Zwei-Konten-Negativbeweis gemessen (docs/exchange-evidence.md). Die vier F13-Entscheidungen bleiben Konfiguration mit dokumentierten Defaults; die Rolle von `occ oauth2:add-client` ist als offene F13-Antwort markiert (Owner 24.09.). Akzeptiert: T-24-32 (mitfahrende Nextcloud-Anmeldung entscheidet vor dem Token; gemessen, dokumentiert, keine Rechteausweitung; R-24-05, Owner 26.09.). NICHT released: der Exchange-Pfad reist erst mit 0.3.0 (nur mit Owner-Freigabe). Nebenläufig im Milestone-Zeitraum: Community-PR #8 (piAreSquare) gemergt (files_download, Chunk-Upload, NC_MCP_FILES_ROOT-Sandbox), main darauf rebased.

**v1.5 shipped 2026-08-31, Abschluss nachgetragen 2026-09-18** (kein Milestone-Audit): Release 0.1.11 (gekürzter Trifecta-Absatz, Autorenkontakt admin@infranode.dev), zeitboxierter openDesk-Spike auf OpenProject mit Fragenliste für den ISV-Call, Audit-Log als erster Enterprise-Baustein (hash-verkettet, ab Werk aus, Phasen 18+19 inkl. Bedienung und Textnachzug). Zwischen v1.5 und v1.6 ausserhalb von Milestones: PR #6 Standalone-OAuth (DaniW42, 0.2.0) und PR #7 Anzeigename gemergt, Releases 0.2.0 (nur GitHub/ghcr) und 0.2.1 (Store, Textrelease).

**v1.4 shipped 2026-08-28** (Audit passed 4/4, Release 0.1.10 live im Store): Die Store-Beschreibung trägt jetzt einen kurzen Enterprise-Abschnitt mit dem Kontakt admin@infranode.dev, und die private Outlook-Adresse ist aus dem öffentlichen Manifest verschwunden. Dazu die Doku-Reste aus v1.3: Übersetzungsfehler in README.fr/de, hängende Changelog-Linkdefinition, Ampersand-Kommentar, chronologische Nachweistabelle, und die Reichweite des Vokabular-Gates gegenüber .planning ist als begründete Ausnahme mit Halter-Test entschieden. Kein Code geändert: dieselben 21 Werkzeuge, Budget 15712/18000. Lehre des Milestones: Beweisdokumente brauchen dieselbe Faktenprüfung wie Code, und ein als behoben gebuchter Review-Befund ohne nachgefahrenen Beleg ist schlimmer als ein offener.

**v1.3 shipped 2026-08-26** (Audit passed 6/6, Release 0.1.9 live im Store): Konsistenz- und Härtungs-Schulden aus v1.2 geschlossen (`message_truncated` je Ebene eine Bedeutung, Id-Codec einzige Quelle, AST-Gate gegen Privat-Durchgriffe, drei Security-Nachzieher als Regressionstests). CIMD nach den v1.1-Review-Fixes live NACHGEMESSEN statt behauptet (Messweg A, echter Client, POST /register = 0, Gegenprobe mit abgeschaltetem Schalter). Enterprise-Fake-Door (ISV-Vorhaben) in READMEs und Store-Beschreibungen EN/DE/FR, ohne Preis, Kontakt k.cherif@outlook.de; Owner-Entscheid D-07: kein Issue, keine Enterprise-Interna im Repo. GitHub-Actions auf Node-24-Majors (setup-uv exakt gepinnt), per CI-Lauf und release.yml-Dry-Run validiert. Codebasis: ~2812 Tests grün, Budget 15711/18000 über 21 Tools.

**v1.2 shipped 2026-08-25** (Audit passed 17/17, Release 0.1.8 live im Store): 21 Tools über neun Familien. Talk (Konversationen/Verlauf nachweislich nebenwirkungsfrei lesen, Senden als einziger direkter Nachrichtenkanal, instanzweit abschaltbar per NC_MCP_TALK_SEND), Tables (lesen über drei Ebenen, Zeile anlegen über Spaltentitel), Mail strikt lesend (Konten/Postfächer/Envelopes/Volltext, AST-Grep-Gate gegen jeden Schreibaufruf, Lethal-Trifecta-Doku). prepare_context mit vier Beinen (Termine, Suche, Talk-Digest, Mail-Ungelesen-Zähler), je eigenes Zeitbudget und degraded-Eintrag, live gemessen. fetch löst sieben Id-Arten auf (file/note/card/event/mail/message/table). Budget-Gate erstmals gesenkt statt angehoben: 18000 aus 15612 gemessenen Bytes. Codebasis: ~2770 Tests grün, ruff/pyright/vulture sauber.

**v1.1 shipped 2026-08-20** (Audit passed 7/7, Verification 6/6, Security 74/74): CIMD als DCR-Alternative live bewiesen (Claude Code verbindet ohne Registrierung), SSRF-gehärteter Dokumentabruf, RFC-8252-Loopback-Portregel, CIMD als fünfter Admin-Settings-Wert, Cursor-Befund gemessen und per BL-14 entschieden ("sichtbar machen plus Doku", D-35 steht), Ein-Klick-Story auf NC 34.0.3 wörtlich wahr (Store-UI zeigt beide Knöpfe), Conference-Demo-Runbook (82 s, durchgefahren) plus Lightning-Talk-Entwurf. Phase 7 (MUCGPT/F13/BaerGPT) per Owner-Entscheid deferred, extern getaktet. **Release 0.1.3 ist seit 21.08. live im Store** (Owner-Freigabe erteilt, alle Runbook-Proofs geschlossen; trägt CIMD, Loopback-Portregel, Admin-CIMD-Schalter, E5-Ausweg, F2 serverInfo.version). Codebasis: ~2208 Unit-/Contract-Tests grün, ruff/pyright/vulture sauber.

**v1.0 shipped 2026-08-20.** Release 0.1.2 ist live im Nextcloud App Store
(apps.nextcloud.com/apps/mcp_connector), 16 Tools, OAuth 2.1 E2E gegen Claude.ai und
ChatGPT bewiesen, Per-User-Verwaltung live, Purge/Deinstallation live bewiesen, alle 27
v1-Requirements erfüllt (Audit passed). Codebasis: Python 3.13, mcp 2.0, ~1800 Unit-/
Contract-Tests grün, ruff/pyright/vulture sauber. Offene Posten im BACKLOG (BL-01..05,
BL-12 MUCGPT-Verprobung wartet auf it@M-Antwort).

## Next Milestone Goals

Kandidaten nach v1.6 (Stand 2026-09-26):
- **files_update / Schreibzugriff mit harten Schienen (Kandidat Nr. 1):** Owner-Entscheid 25.09.: Daniel (DaniW42/simul8) baut als Community-PR, Prozess über ein Design-Issue (Entwurf: Desktop/design-issue-files-update-ENTWURF.md), Massnahmenkatalog verbindlich; WARTET auf Daniels Antwort. Linie: sicheres Editieren frei (B), Freigabe-Governance bezahlt (D), Scope-Fence gegen den Audit-Log-Präzedenzfall
- **Release 0.3.0** (nur mit Owner-Freigabe): bündelt Exchange-Pfad (v1.6), PR-#8-Features (files_download, Chunk-Upload, Sandbox), Store-Text-Fixes (RAG raus, Findling-Satz) und Public-URL-Ableitung
- **F13-Wiederaufnahme**, sobald Denny Mattern antwortet: EXCH-F01 (Golden-Fixture aus echtem Token), EXCH-F02 (vier verprobte Konfigurationswerte), CLIENT-02 (Live-Verprobung)
- Enterprise-/ISV-Spur: Fabrice-Call nachholen (Wiedervorlage war 25.09.), Approved-Write-Suite (D) erst danach öffentlich; Fake-Door-Auswertung ab Oktober, Findling-Pro-Entscheid vertagt auf 03.11.
- openDesk in der Breite (v2.0) und Mail-Entwürfe/Talk-Threads: unverändert spätere Kandidaten
- MUCGPT/BaerGPT live verproben, sobald externer Zugang besteht (deferred CLIENT-01/03)

## Requirements

### Validated

- ✓ Als ExApp per Klick aus dem Nextcloud App Store installierbar (AppAPI/Deploy Daemon) , v1.0 (Store-Release 0.1.0..0.1.2; Ein-Klick-Lücke via Declarative Admin-Settings geschlossen)
- ✓ MCP-Spec-konformes OAuth 2.1 , v1.0 (Claude.ai und ChatGPT verbinden sich nur mit der Resource-URL; DCR, PKCE, Rotation mit Reuse-Detection)
- ✓ Per-User-Verwaltung in den Nextcloud-Settings , v1.0 (Verbindungsseite unter Settings/Security, Pause wirkt an allen 4 Autorisierungspunkten)
- ✓ Kuratierte Tool-Basis , v1.0 (16 Tools, Budget-Gate 12500 Bytes, Contract-Test gegen die aktive Registry)
- ✓ prepare_context , v1.0 (Suche + Terminwoche in einem Aufruf, Marker-Filter gegen Text-Fälschung)
- ✓ Risikoarme Writes, destruktive Ops konstruktionsbedingt ausgeschlossen , v1.0 (AST-Grep-Gate, Zwei-Konten-Negativbeweis)
- ✓ Transport stdio + Streamable HTTP, App-Passwort + Login Flow v2 , v1.0
- ✓ App-Store-Einreichung vor der Nextcloud Conference September 2026 , v1.0 (eingereicht 2026-08-19, fünf Wochen vor Termin)
- ✓ Contribution-Fix an nextcloud/context_agent#227 , v1.0 (Fork + DCO-signierter Fix, Disclosure in #203)
- ✓ Client ID Metadata Documents als DCR-Alternative, SSRF-geprüft , v1.1 Phase 6 (Claude Code verbindet sich live ohne Registrierung; DCR-Kontrollen greifen wortgleich, kein Fetch außerhalb von /authorize)
- ✓ Cursor-Verhalten gemessen statt vermutet, Loopback-Portfrage beantwortet , v1.1 Phase 6 (Teilregistrierung wirkt live mit 201; Cursor scheitert belegt an seiner eigenen cursor://-Adresse, Owner-Entscheid BL-14 "sichtbar machen plus Doku"; RFC-8252-7.3-Portregel eingebaut und mit wechselnden Ports live bestätigt)
- ✓ NC-34.0.3-UI-Smoke: Ein-Klick-Installation über die Store-UI nachgewiesen , v1.1 Phase 6 (Deploy-and-enable- und Remove-Knopf gemessen, Doku/Store-Text EN/DE/FR sagen das Gemessene)
- ✓ Conference-Demo-Material , v1.1 Phase 6 (Runbook einmal komplett durchgefahren, 82 s; Lightning-Talk-Entwurf, CfP-Schließung im Kopf vermerkt)
- ✓ Talk-Familie: lesen nebenwirkungsfrei (vier Leseparameter live gemessen), senden token-adressiert und admin-abschaltbar , v1.2 (TALK-01..04)
- ✓ Tables-Familie: drei Lese-Ebenen gekappt, Zeile anlegen über Spaltentitel mit Vorab-Ablehnungen , v1.2 (TABLES-01..02)
- ✓ Mail-Familie strikt lesend inkl. Volltext, Filtergrammatik und AppAPI-Erreichbarkeitsbeweis , v1.2 (MAIL-01..04)
- ✓ Lethal-Trifecta ausdrücklich adressiert (Doku + Store-Text dreisprachig + TALK-04-Schalter) , v1.2 (SEC-01)
- ✓ prepare_context mit Talk-Digest und Mail-Zählern, gemessen statt geschätzt , v1.2 (CTX-01..02)
- ✓ Budget-Gate auf Messung verankert (18000), Suchtreffer aus Talk/Tables auflösbar , v1.2 (TOOL-15..16)
- ✓ Release 0.1.8 im Store mit vier Nachweisen und Owner-Tag-Gate , v1.2 (EXAPP-07)
- ✓ Konsistenz-Nachzieher: eine Bedeutung je Antwortschlüssel, Id-Codec als einzige Quelle, keine Privat-Durchgriffe (AST-Gate) , v1.3 (TOOL-17..19)
- ✓ Security-Nachzieher als Regressionstests statt Prüfschritte, Vokabular-Gate in voller Reichweite , v1.3 (SEC-02)
- ✓ CIMD live nachgemessen: echter Client verbindet ohne Registrierung, Gegenprobe mit Schalter aus, selbsttragende Proof-Zeile , v1.3 (EXAPP-08)
- ✓ Release 0.1.9 im Store mit elf Proof-Zeilen, Owner-Tag-Gate und Signatur über das heruntergeladene Asset , v1.3 (EXAPP-09)
- ✓ Doku-Reste aus v1.3 geschlossen und Vokabular-Gate-Reichweite entschieden , v1.4 (DOC-01, DOC-02, SEC-03)
- ✓ Release 0.1.10 im Store mit dem gekürzten Enterprise-Abschnitt und dem Kontaktwechsel auf admin@infranode.dev , v1.4 (EXAPP-10)
- ✓ Release 0.1.11, openDesk-Spike (OpenProject, Fragenliste für den ISV-Call) und Audit-Log als erster Enterprise-Baustein , v1.5 (Abschluss nachgetragen 2026-09-18)
- ✓ Eine gehärtete Schlüsselsatz-Schicht (oauth/jwks.py: Abkühlzeit, Single-Flight, fail-closed), PyJWT 2.14 + cryptography 50.0.1 , v1.6 (EXCH-01, DEP-01)
- ✓ Vollständige Keycloak-JWS-Prüfung als freistehende Funktionen, jede Abweichung ein eigener detailfreier Grund , v1.6 (EXCH-02, EXCH-03)
- ✓ Exchange-Pfad als Kette hinter unveränderter Transportgrenze: eigener Namensraum ab Werk aus, formbasierte Weiche, vor-authentische Drossel, Aus-Zustand byte-gleich , v1.6 (CONF-01, EXCH-04, EXCH-05)
- ✓ Konto-Mapping ohne stille Kontoanlage (zwei Profile, kanonischer Principal), AppAPI-Impersonation fail-closed, Standalone-Bindung mit Enrollment und sofortigem Widerruf , v1.6 (MAP-01, MAP-02, CRED-01, CRED-02)
- ✓ Audit-Anschluss (actor-Spalte, gebremste Abweisungskette), Trockenlauf-Kommando, Zwei-Konten-Negativbeweis gemessen, Einrichtungsdoku mit ehrlichen F13-Grenzen , v1.6 (AUDIT-07, EXCH-06, EXCH-07, EXCH-08)

### Active

(Leer. MUCGPT/F13/BaerGPT-Verprobungen am 2026-08-20 per Owner-Entscheid deferred: extern getaktet, Trigger it@M-Antwort bzw. Owner-Kontakte; siehe Future Requirements in REQUIREMENTS.md und BL-12.)

### Out of Scope

- openDesk-Suite-Breite (OpenProject, XWiki, Matrix, OX) - Phase 3 nach Oktober 2026, eigener Meilenstein
- Tool-Flut (100+ Tools) - bewusste Gegenposition zum Platzhirsch; Client-Tool-Limits (z.B. Cursor 80) machen Flut zum Nachteil
- Destruktive Operationen (Löschen, Überschreiben, Teilen/Freigaben ändern) - Sicherheitsversprechen der v1: "kann konstruktionsbedingt nichts zerstören"
- Eigener LLM/RAG-Index - der MCP liefert Daten, das Modell sitzt beim Client; semantische Suche hat der Platzhirsch (Qdrant+Ollama), wir differenzieren über Zugänglichkeit und Auth
- Konkurrenz zum Nextcloud Assistant/context_agent als Agent-Plattform - wir sind bewusst MCP-only (genau die in context_agent#203 gewünschte, unerfüllte Nische)

## Context

**Marktlage (recherchiert 14.08.2026):**
- Offizieller MCP-Server existiert versteckt in der ExApp context_agent: nur statische App-Passwort-Bearer (kein OAuth, Issue #74), skaliert laut eigener Doku nicht, aktuell inkompatibel mit MCP-SDK >= 1.28 (Issue #227), MCP-only-ExApp explizit gewünscht und abgelehnt/nicht gebaut (Issue #203)
- Community-Platzhirsch cbcoutinho/nextcloud-mcp-server: 324 Stars, sehr aktiv, 110+ Tools über 12 Apps, AGPL, Login Flow v2, semantische Suche; kein ExApp, kein spec-konformes OAuth, keine Per-User-Verwaltung in der NC-UI
- Unbesetzte Lücken = unsere Differenzierer: (1) MCP-Authorization-Spec-OAuth, (2) Per-User-Verwaltung in Nextcloud-Settings, (3) Remote-Skalierbarkeit, (4) MCP-only-ExApp im Store

**Wiederverwendbare Basis:** InfraNode-MCP (C:\Users\Student\infranode-api\src\infranode\mcp\, live auf mcp.infranode.dev): Tool-Annotationen, Schema-Diät (-27% Tokens), Graceful-Degradation-Wrapper, ASGI-Rate-Limiting, freistehende testbare Tool-Funktionen, Registry-Listing-Playbook.

**Nextcloud-API-Matrix (recherchiert):** WebDAV (Dateien + SEARCH), CalDAV, CardDAV, Notes-REST, Deck-REST, Unified Search OCS (berechtigungstreu, parallelisierbar über Provider). OCS immer mit OCS-APIRequest: true + Accept: application/json.

**MCP-Spec-Lage (korrigiert 14.08. nach Stack-Research):** mcp 2.0.0 ist seit 28.07.2026 GA (stabil), 1.x ist Maintenance-only. Entscheidung: mcp>=2.0,<3 (bedient 2025er- und 2026er-Stateless-Clients aus demselben Endpoint), dokumentierter Fallback-Pin >=1.29,<2. Kein Session-State in Tools (Pagination über Handles).

**Strategisches Umfeld:** Dataport/Brandmann-Termin 21.08. GESTRICHEN (keine Rückmeldung seit 13.07., Owner-Entscheid 20.08.), DFKI/Porta ab 25.08., MUCGPT 2.0 kann MCP (Abnehmer-Story München/Stuttgart, Verprobung deferred bis it@M antwortet), ZenDiS/openDesk als Phase-3-Ziel. Nextcloud Conference September 2026 = Launch-Anker (CfP zu; Demo + Talk-Entwurf liegen bereit).

## Constraints

- **Timeline**: v1 lauffähig + App-Store-Einreichung vor der Nextcloud Conference September 2026 - harte Deadline, notfalls Scope kürzen, nie den Termin
- **Tech stack**: Python 3.13 + offizielles MCP-SDK (mcp[cli] ~1.27), uv als Toolchain (lokales System-Python ist defekt), Docker/WSL2 für lokale Test-Nextcloud
- **Lizenz**: AGPL-3.0 - passt zur Nextcloud-Ökosystem-Kultur und maximiert die Chance offizieller Übernahme
- **Repo**: public auf GitHub street1983nk (privates Konto, NICHT Akara-GitLab) - Konto-Trennungs-Regel
- **Solo-Betrieb**: Ein Entwickler; Wartungsaufwand pro Feature zählt, kuratiert schlank schlägt breit
- **Sprache**: Code/README Englisch (internationales Nextcloud-Publikum), Projektkommunikation Deutsch; keine Em-Dashes, echte Umlaute in deutschen Texten
- **Security**: Der MCP darf nie mehr sehen als der angemeldete Nutzer (Berechtigungs-Durchgriff); keine destruktiven Writes in v1

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MCP-only-ExApp statt Standalone-Server oder context_agent-Konkurrenz | Explizit nachgefragte, unbesetzte Nische (context_agent#203); Store-Distribution = Zugänglichkeits-Vorsprung | ✓ Good , im Store gelandet, Nische bestätigt (Release-Ankündigung in #203 positiv aufgenommen) |
| OAuth 2.1 nach MCP-Authorization-Spec als Kern-Differenzierer | Meistgefordertes Feature im Ökosystem (context_agent#74); niemand hat es | ✓ Good , Claude.ai und ChatGPT verbinden plug-and-play, E2E gemessen |
| Kuratiert schlank (~15-20 Tools) statt Tool-Flut | Client-Tool-Limits real; Platzhirsch hat Breite schon; Schema-Diät-Patterns vorhanden | ✓ Good , 16 Tools bei 11268/12500 Bytes Budget |
| mcp>=2.0,<3 statt 1.x (revidiert 14.08.) | 2.0.0 seit 28.07. GA; v2 bedient alte und neue Clients aus einem Endpoint | ✓ Good , Matrix-Test SDK 1.29 + 2.x gegen dieselbe URL grün |
| Contribution-Fix an context_agent#227 als Flanke | Sichtbarkeit + Goodwill beim Nextcloud-Team vor der Conference | ✓ Good , Fix eingereicht, Disclosure platziert |
| AGPL-3.0 | Ökosystem-Kultur; Übernahme-Chance wichtiger als maximale Wiederverwendbarkeit | ✓ Good |
| Risikoarme Writes, destruktive Ops ausgeschlossen | "Kann nichts zerstören" ist Verkaufsargument, kein Mangel | ✓ Good , als Gate implementiert (AST-Grep), Kern der Store-Beschreibung und des LinkedIn-Narrativs |
| Fail-closed bei DCR-redirect_uris revidiert zu Teilregistrierung (20.08.) | Cursor registriert 3 URIs auf einmal, eine unzulässige sperrte den ganzen Client aus | ✓ Good , wirkt live (201 mit den zwei zulässigen Adressen); Cursor scheitert danach an sich selbst (schickt die verworfene cursor://-Adresse an /authorize) |
| BL-14 "sichtbar machen plus Doku" statt cursor://-Registrierung (Owner, 20.08.) | D-35 steht (Desktop-Schemes kann jede App abfangen); E5-Seite nennt den App-Passwort-Ausweg, Doku den Grund | ✓ Good , Phase 6 verified 6/6, kein Sicherheitsversprechen aufgeweicht |
| MUCGPT-Verprobung als geführte Lücke abgenommen (Owner, 20.08.) | Braucht fremde Instanz (it@M); Protokoll einlösbar dokumentiert | , Pending (Mail gesendet, Antwort ausstehend) |
| v1.2 "Kuratierte Breite" vorgezogen statt auf Store-Feedback zu warten (Owner, 21.08.) | Talk/Tables/Mail sind die meistgefragten Familien; Schlankheit bleibt über Schema-Diät und Budget-Gate | ✓ Good , 21 Tools bei 15657/18000 Bytes, Gate gesenkt statt angehoben |
| talk_send kommt, hinter neuem Admin-Schalter (Owner, 21.08., Lethal-Trifecta-Entscheid) | Ausgangskanal gehört der Administration; Kette benannt statt beschwiegen | ✓ Good , Ende-zu-Ende gemessen, SEC-01 dreisprachig im Store-Text |
| Mail strikt lesend, kein Schreibpfad im Client | Sensibelste Familie; "kann nichts zerstören" bleibt wörtlich wahr | ✓ Good , AST-Grep-Gate mit 9 Nadeln + Gegenproben, live nebenwirkungsfrei bewiesen |
| Release-Signatur immer über das heruntergeladene Asset, Branch-Push vor dem Tag | tar.gz nicht byte-reproduzierbar (45710 lokal vs 45546 publiziert bei 0.1.8); Store-Links zeigen auf main | ✓ Good , Runbook Schritt 4/6 präzisiert, Skript-Ausgabe entschärft (eb05a6f); bei 0.1.9 wörtlich eingehalten (47546 lokal vs 47264 publiziert, Verified OK) |
| Enterprise-Fake-Door mit dem Release 0.1.9 ausgeliefert (Owner, 25.08., ISV-Vorhaben) | Store liest das Manifest nur beim Upload; READMEs waren ohnehin offen; Signale messen statt bauen | , Pending (Go-Kriterium: >=5 Org-Signale in 6 Wochen oder 1 Ankerkunde; Auswertung ab Oktober) |
| D-07: kein Enterprise-Issue, keine Enterprise-Interna im Repo (Owner, 26.08.) | Interne Messkriterien gehören nicht vor die Zielgruppe, die gemessen wird | ✓ Good , Entwurf + Go-Kriterium aus dem Repo entfernt (f9b3d2d), nur lokal beim Owner |
| CIMD-Nachmessung über Messweg A gegen den Kandidaten VOR dem Tag (25.08.) | Beweis darf nicht von der Owner-Freigabe abhängen; Quellstand == Tag-Stand per leerem Diff belegt | ✓ Good , echter Client, POST /register = 0, Gegenprobe 0 Sockets |
| D-v1.6-01: Exchange-Vollmacht über AppAPI-Impersonation (ExApp) bzw. vorab gebundene Autorisierung (Standalone), keine neue Vollmachtsklasse (Owner, 18.09.) | Rechtegrenze bleibt bei Nextcloud; keine stille Kontoanlage, kein Provisioning je Nutzer | ✓ Good , beide Wege gemessen (Impersonationslog, 200-dann-401-Widerruf) |
| Nur entscheidungsunabhängige Teile bauen, F13-Abhängiges als Konfiguration mit Defaults (Milestone-Prämisse 18.09.) | Kein Warten auf externe Antworten; Spec-Note-Zusage einhalten | ✓ Good , 15/15 Requirements ohne eine einzige F13-Antwort geliefert, Andockpunkte dokumentiert |
| Rolle von occ oauth2:add-client als OFFENE F13-Antwort markiert statt geraten (Owner, 24.09., Checkpoint 24-09) | Eine geratene Empfehlung in einer Einrichtungsdoku baut falsche Instanzen | , Pending (Frage liegt bei F13, ein Test hält die Markierung) |
| T-24-32 akzeptiert statt Code-Mitigation (Owner, 26.09., R-24-05) | Gemessen, dokumentiert, keine Rechteausweitung; vorgesehener Betrieb ist Server-zu-Server ohne zweite Anmeldung | ✓ Good , Härtung in middleware.py bleibt als Option benannt |
| PR #8 nach 4 Tagen Funkstille selbst fertiggestellt und gemergt (25.09.) | Sollte den Beitrag nicht verfallen lassen; verstiess aber gegen die Owner-Ansage "erst handeln, wenn er antwortet" | ⚠ Revisit , Regel seitdem: fremde PRs nie ohne Antwort des Beitragenden oder fallbezogene Owner-Freigabe fertigstellen |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-26 after v1.6 milestone*

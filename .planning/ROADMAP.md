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
- **v1.8 Tasks-Bundle und Ordner anlegen**: Phasen 30-34 (aufgesetzt 2026-10-28, Roadmap 2026-11-11; Releases 0.7.0 bis 0.7.2 sind im Milestone-Zeitraum erschienen; Ziel ist ein Release 0.8.0 mit Aufgaben suchen, lesen, anlegen, abhaken, ändern und verschieben nach Issue #32 und Ordner anlegen nach Issue #44)

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

### v1.8 Tasks-Bundle und Ordner anlegen (Phasen 30-34), IN PLANUNG

- [x] **Phase 30: Mess-Spike Aufgaben und Ordner** - Alles, was Recherche und Planung nur annehmen, wird gegen echte Nextcloud-Instanzen gemessen, bevor Produktcode entsteht; zuerst `MKCOL` unter AppAPI-Impersonation, mit Abbruchkriterien (completed 2026-11-12)
- [x] **Phase 31: Ordner anlegen** - `files_create_folder` legt Ordner an, wahlweise mit fehlenden Elternordnern, hinter der ganzen v1.7-Kette aus Ausschluss, Sandbox, Paartest, Kanarie und Audit; allein releasefähig
- [ ] **Phase 32: Tasks-Bundle suchen, lesen, anlegen** - `tasks_search`, `tasks_read` und `tasks_create` über CalDAV VTODO als zehnte Familie, samt `task:`-Id über `fetch`; ohne Phase 33 releasefähig
- [ ] **Phase 33: Aufgaben ändern** - Abhaken, Wiederöffnen, Felder ändern und Verschieben einer einzelnen Aufgabe, nur mit gelesener ETag; kein Löschen (Owner, 12.11.2026); jeder Teil abtrennbar
- [ ] **Phase 34: Doku, Store, Release 0.8.0** - Doku und Store-Text in drei Sprachen sagen den Endstand samt präzisierter Schreibzusage, Release 0.8.0 steht mit Owner-Freigabe im Store

## Phase Details (v1.8)

Grundlage: [research/v1.8-tasks-080-RESEARCH.md](research/v1.8-tasks-080-RESEARCH.md) (Commit 5ddaddf) und [REQUIREMENTS.md](REQUIREMENTS.md). Owner-Entscheide E1 bis E14 vom 11.11.2026 stehen in PROJECT.md (Key Decisions). Für jeden Plan aller Phasen gilt: er endet mit dem vollen Lauf `pytest tests/unit tests/contract` plus `scripts/check_tool_budget.py` und den Qualitätstoren (REQUIREMENTS.md, Regel R1); vor jedem Push, Merge oder Kommentar wird der Owner gefragt (R4).

### Phase 30: Mess-Spike Aufgaben und Ordner

**Goal**: Jede Annahme, auf der die Phasen 31 bis 33 stehen, ist gegen echte Nextcloud-Instanzen gemessen statt aus dem Quelltext gelesen; der Messbericht entscheidet über Abbruchkriterien, Deckel, Zeitbudget und den Umfang der ändernden Zugriffe
**Depends on**: Nothing (erste Phase des Milestones; baut auf Release 0.7.2 auf)
**Requirements**: MESS-01, MESS-02, MESS-03, MESS-04, MESS-05, MESS-06
**Success Criteria** (what must be TRUE):

  1. Als erster Messpunkt ist protokolliert, was `MKCOL` auf `files/` unter AppAPI-Impersonation in der ExApp-Topologie liefert, dazu die Statusmatrix (freier Name, vorhandener Ordner, vorhandene Datei, fehlender Elternordner, unzulässiger Name, geteilter Ordner ohne Schreibrecht, gesetzte Sandbox-Wurzel), je mit Statuscode und Rohantwort. Kommt für den freien Namen kein 201, ist Phase 31 gestoppt und der Befund liegt beim Owner
  2. In einem Gruppenordner mit ACL ist gemessen: mit Schreibrecht entsteht der Ordner, ohne Schreibrecht wird abgelehnt (Negativtest), beides mit Statuscode im Protokoll (E12)
  3. Auf mindestens Nextcloud 32 und 35 ist belegt, dass ein frisches Konto keine Aufgabenliste hat, wie Deck-Kalender, Papierkorb, geteilte und nur lesbare Listen in der Discovery aussehen, und von der Tasks-App geschriebene Objekte liegen als Fixtures vor; die Kosten der Suche bei 2000 Aufgaben stehen als Zahlen für SQLite und PostgreSQL im Protokoll
  4. Für die ändernden Zugriffe ist gemessen, welche Felder die Tasks-App beim Abhaken und Wiederöffnen setzt, dass `PUT` mit `If-Match` unter AppAPI-Impersonation funktioniert und eine veraltete ETag abgelehnt wird, dass fremde Eigenschaften den `PUT` überstehen, und wie sich wiederkehrende Aufgaben und Unteraufgaben verhalten; ein Inventar nennt mit Datei und Zeile jedes Gate und jede Zusage, die ein überschreibender `PUT` berührt
  5. Der Messbericht nennt für das Löschen auf Nextcloud 32 bis 35 genau eines der Ergebnisse "wiederherstellbar", "nicht wiederherstellbar" oder "nicht eindeutig" (auch mit abgeschaltetem Papierkorb und für geteilte Listen, mit Aufbewahrungsfrist), für `MOVE` unter Impersonation Statuscodes und das Verhalten der Unteraufgaben, und führt jede Annahme A1 bis A19 und A21 als belegt, widerlegt oder ungemessen; ein Owner-Checkpoint entscheidet E15 und jedes ausgelöste Abbruchkriterium

**Plans**: 5 plans (fünf Wellen, streng nacheinander: ein Docker-Host, immer nur eine Instanz)

Plans:
- [x] 30-01-PLAN.md: Messwerkzeug, `MKCOL` unter AppAPI-Impersonation als erster Messpunkt samt Statusmatrix, Gruppenordner mit ACL und Negativtest (MESS-01, MESS-02; A7, A8, A9)
- [x] 30-02-PLAN.md: Ändernde Zugriffe: `PUT` mit `If-Match` und Erhalt fremder Eigenschaften unter Impersonation, Browser-Sitzung in der Tasks-App, Inventar der Gates und Zusagen (MESS-05; A12 bis A17)
- [x] 30-03-PLAN.md: `MOVE` unter Impersonation, Unteraufgaben, Löschen mit Papierkorb an und aus auf 32 bis 35, Ergebniswort nach E13 (MESS-06; A18, A19, A21)
- [x] 30-04-PLAN.md: Aufgaben-Discovery, Abfrageverhalten auf 32 bis 35, Kosten bei 2000 Aufgaben auf SQLite und PostgreSQL, Fixtures der Tasks-App (MESS-03, MESS-04; A1 bis A6, A11)
- [x] 30-05-PLAN.md: Messbericht abschließen, Übergabe der Abbruchkriterien an die Phasen 31 bis 33, Owner-Checkpoint E15 (Schlusssatz von MESS-06)

Messbericht: `docs/spike-tasks.md`; Rohprotokolle unter `.planning/phases/30-mess-spike-aufgaben-und-ordner/raw/`
**Abbruchkriterien**: MESS-01 (kein 201 für `MKCOL` unter Impersonation: Phase 31 wird nicht geplant), MESS-05 (`If-Match` geht nicht oder fremde Eigenschaften gehen verloren: Owner entscheidet über Phase 33), MESS-06 (`MOVE` geht nicht: TMOD-08 wird nicht geplant; Löschen nicht eindeutig wiederherstellbar: TMOD-07 entfällt ohne Rückfrage)
**Research flag**: ja (Live-Zugriff auf Nextcloud 32 bis 35, Tasks-App und Gruppenordner in der Testinstanz, PostgreSQL-Gegenmessung; schwere Läufe seriell, RAM vor Docker-Messungen prüfen). Ändernde Zugriffe, Verschieben und Löschen sind von der Recherche nicht abgedeckt
**Hinweis**: Messskripte und Gegenproben liegen nie unter `src/`; ein messendes `DELETE` oder `MOVE` läuft nur aus dem Spike-Skript gegen die Wegwerf-Instanz

### Phase 31: Ordner anlegen

**Goal**: Ein Assistent kann über `files_create_folder` einen Ordner anlegen, auf Wunsch samt fehlender Elternordner, und der neue Schreiber der Dateifläche hält jede Grenze, die der Upload hält; die Phase ist für sich allein releasefähig
**Depends on**: Phase 30 (MESS-01 und MESS-02)
**Requirements**: FOLD-01, FOLD-02, FOLD-03, FOLD-04, FOLD-05, FOLD-06
**Success Criteria** (what must be TRUE):

  1. Gegen eine echte Nextcloud gemessen, auch unter AppAPI-Impersonation: ein freier Pfad wird angelegt (`created: true`), ein vorhandener Ordner antwortet als Erfolg mit `created: false`, eine Datei am Pfad ist ein Konflikt, ein fehlender Elternordner ohne `parents` ist `parent_missing`; mit `parents=true` entsteht die Kette, die Antwort nennt jeden angelegten Ordner, mehr als 10 neue Ordner je Aufruf entstehen nie, und ein Abbruch mittendrin nennt das bereits Angelegte
  2. In einem mit `kein-ki` ausgeschlossenen Ordner und darunter wird nichts angelegt, und die Antwort ist byte-gleich zu "Elternordner fehlt" (Paartest als Unit- und Live-Paar); ist die Ausschlussprüfung nicht beantwortbar, geht kein `MKCOL` hinaus; mit gesetzter `NC_MCP_FILES_ROOT` wird weder die Wurzel noch etwas darüber angelegt
  3. Ohne Schreibrecht wird nichts angelegt und die Meldung sagt "keine Rechte": belegt für einen geteilten Ordner und, mit der Rohantwort aus Phase 30, für einen Gruppenordner mit ACL; ein unzulässiger Name ergibt eine eigene Meldung statt "unexpected status"
  4. Die Kanarie ruft `files_create_folder` wirklich auf und es steht in `MUST_REFUSE`; der Klassifikations-Freeze führt es unter `FILE_WRITERS` mit Paarfall; jeder Aufruf erzeugt einen Audit-Eintrag; `EXPECTED_PUT_CALLS` ist unverändert, eine Nadel hält `MKCOL` auf `dav.py` und ohne Body; das Budget der Werkzeugliste ist grün, ohne dass ein Werkzeug über 1400 Bytes liegt
  5. Auf dem Stand ohne Phase 32 sind alle Gates grün, und Werkzeugliste, Rechtetabelle und Werkzeugzahl der drei READMEs, je ein Satz in `docs/exclusion.md`, `.de.md` und `.fr.md` sowie der Eintrag in `CHANGELOG.md`, `CHANGELOG.de.md` und `CHANGELOG.fr.md` nennen das Werkzeug

**Plans**: 6 plans (sechs Wellen, streng nacheinander: ein Docker-Host, immer nur eine Instanz)

Plans:
- [x] 31-01-PLAN.md: Machbarkeitsbeweis der Strecke Nextcloud 32 unter AppAPI-Impersonation mit Abbruchkriterium, Basis-Commit in 31-BASE.txt (FOLD-01; D-31-06)
- [x] 31-02-PLAN.md: `dav.make_folder`, `probe_folder`, Statusprüfer und `files.create_folder` mit Vorab-Zählung, Deckel 10, Sandbox und `kein-ki`, Unit-Tests (FOLD-01 bis FOLD-05; D-31-01 bis D-31-05)
- [x] 31-03-PLAN.md: Registrierung mit `CREATE_IDEMPOTENT`, Audit, Werkzeugmenge 24, Annotations-Gate, Freeze mit Paarfall, Budget-Messzeile, drei READMEs (FOLD-03, FOLD-05, FOLD-06)
- [x] 31-04-PLAN.md: MKCOL-Nadel mit gepflanzten Umgehungen, Kanarie mit `MUST_REFUSE`, Live-Paarfall und Abnahmeskript als Code (FOLD-05)
- [x] 31-04b-PLAN.md: Zusatzplan, Netzfehler in der Ordnerkette nennen das Angelegte und trennen das Segment mit unbekanntem Zustand (FOLD-02; Owner 2026-11-12)
- [x] 31-05-PLAN.md: Live-Test unter Impersonation auf Nextcloud 35 und 32 mit 15 Fällen und 2 Kontrollen, Beleg in `docs/folder-evidence.md` (FOLD-01 bis FOLD-05; D-31-05 bis D-31-07)
- [x] 31-05b-PLAN.md: Zusatzplan, Ordnernamen mit Leerraum am Rand vorab abgelehnt, Knoten ohne Datei-Id nicht als Datei gemeldet, Abnahmeskript mit allen 24 Werkzeugen, Nachmessung auf Nextcloud 35 und 32 (FOLD-01, FOLD-05; Owner 2026-11-12)
- [x] 31-06-PLAN.md: `docs/exclusion*.md` mit stabilem Beleganker, drei CHANGELOGs, Umlaut-Audit, voller Lauf ohne Phase 32, Owner-Checkpoint zum Push (FOLD-06)
- [x] 31-07-PLAN.md: Zusatzplan nach der Verifikation, ganze Kette über die installierte ExApp auf Nextcloud 35 und das Werkzeug gegen einen Gruppenordner mit ACL (FOLD-01, FOLD-05; Owner 2026-11-13)

**Rückfallschnitt**: klemmt Phase 32, ist diese Phase allein als Release lieferbar (Owner-Entscheid)

### Phase 32: Tasks-Bundle suchen, lesen, anlegen

**Goal**: Ein Assistent kann Nextcloud-Aufgaben suchen, lesen und anlegen, als zehnte Familie `tasks`, ohne je in eine fremdsichtbare Liste zu schreiben, ohne Deck-Karten zu zeigen und ohne das Verhalten des Kalender-Bundles zu ändern; die Phase ist ohne Phase 33 releasefähig
**Depends on**: Phase 30 (MESS-03 und MESS-04) und Phase 31 (beide Phasen ändern dieselben Gate-Dateien, deshalb nacheinander)
**Requirements**: TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07, TASK-08, TASK-09
**Success Criteria** (what must be TRUE):

  1. Ein Konto ohne Aufgabenliste ist eigens getestet, mit Fixture und live gegen ein Konto, dessen einziger Kalender nur `VEVENT` trägt: `tasks_search` antwortet leer mit Hinweis, `tasks_create` mit einem Fehler samt Ausweg
  2. Gegen eine echte Nextcloud mit Deck-Board und geteilter Liste gemessen: `tasks_search` liefert im Standard nur offene Aufgaben, eine Fälligkeitsgrenze liefert keine undatierten mit, keine Deck-Karte erscheint in irgendeiner Antwort des Bundles, eine ausgefallene Liste steht als `degraded`-Eintrag in der Antwort, und die Termin-Werkzeuge antworten byte-gleich wie vor der Phase
  3. Eine mit "fällig am 20." angelegte Aufgabe steht in der Nextcloud am 20. (`DUE;VALUE=DATE`, kein Folgetag); Startdatum, Tags, Priorität und Elternaufgabe kommen so an, wie die Tasks-App sie liest; ohne `list` wird nur bei genau einer eigenen Liste geschrieben, sonst nennt der Fehler die Listennamen, und in eine geteilte Liste gelangt nichts ohne ausdrückliche Nennung
  4. `tasks_read` und `fetch` lösen dieselbe `task:`-Id auf, ein Treffer des Suchproviders `tasks` führt auf diese Id; die Zeitmatrix (ganztägig, mit Zone, UTC, schwebend, ohne Datum) ist je als benannter Test grün, und Fremdtext aus einer geteilten Liste kommt gekappt und ohne Marker an
  5. Die Registry zeigt 27 Werkzeuge in zehn Familien; `EXPECTED_PUT_CALLS` steht weiter bei 6; das Budget ist nach der Hausregel aus der Messung neu verankert und kein Werkzeug liegt über 1400 Bytes; die Kanarie ruft die drei Werkzeuge auf; READMEs, `docs/` und die drei Changelogs sind nachgezogen, sodass der Stand ohne Phase 33 alle Gates besteht

**Plans**: 11 plans (elf Wellen, streng nacheinander: ein Docker-Host, immer nur eine Instanz; Rahmen in 32-RULES.md; 32-09 schließt die Lücken der Verifikation)

Plans:
- [x] 32-01-PLAN.md: Basis-Commit 32-BASE.txt, Messung `--name` und Heartbeat-URL auf 32/34/35, `scripts/bootstrap_exapp.sh` testgetrieben für Nextcloud 32, `--manual` auf 32 nach Owner-Freigabe zum unregister (TASK-03, TASK-07; D-32-13)
- [x] 32-02-PLAN.md: Messungen vor dem Bau (Kinderabfrage bei 2000 Aufgaben, text-match, Budgets, Namensform geteilter Listen auf 32 und 35, Erkennung der Tasks-App, Linkform), gemeinsame Owner-Freigabe für Zustandsänderungen (TASK-02 bis TASK-04; D-32-03, D-32-10, D-32-11, D-32-14)
- [x] 32-03-PLAN.md: Client-Schicht mit Byte-Pin der Kalenderkörper, create-only-Schreiber, `task:`-Codec mit Listenschlüssel, `clients/tasks.py` (TASK-01, TASK-03, TASK-06, TASK-07; D-32-05, D-32-06, D-32-14)
- [x] 32-04-PLAN.md: `tools/tasks.py` lesend, Zeitmatrix als benannte Tests, `tasks_search` und `tasks_read` mit Unteraufgaben (TASK-01 bis TASK-04; D-32-01 bis D-32-09)
- [x] 32-04b-PLAN.md: `tasks_create` mit E4 und D-32-16, Rücklesen, Erkennung der Tasks-App, Injektionskorpus (TASK-03, TASK-05 bis TASK-07; D-32-10, D-32-16)
- [x] 32-05-PLAN.md: Registrierung `reg_tasks.py`, Oberflächen-Gates mit 27 Werkzeugen, Budget neu verankert, READMEs, `info.xml`, drei CHANGELOGs (TASK-07, TASK-08)
- [x] 32-06-PLAN.md: TASK-09, Provider `tasks`, `fetch` über `tasks_read`, Link nur auf die Startseite bei geteilten Listen, Satz in `docs/hardening*.md` (TASK-07, TASK-09; D-32-06, D-32-15)
- [x] 32-05b-PLAN.md: Kanarie, Abnahmeskript, Live-Test mit Schalter, CI mit und ohne Tasks-App (TASK-01 bis TASK-03, TASK-05 bis TASK-07, TASK-09; D-32-11)
- [x] 32-07-PLAN.md: Live-Beweis auf Nextcloud 35 und 32, je ohne und mit Tasks-App, `docs/tasks-evidence.md` (TASK-01 bis TASK-07, TASK-09; D-32-11, D-32-12)
- [x] 32-08-PLAN.md: gemeinsame Abnahme in der Tasks-App per Playwright, Owner-Checkpoint zum Push, CI-Lauf beider Beine (TASK-05, TASK-07; D-32-11, D-32-13)
- [ ] 32-09-PLAN.md: Lücken nach der Verifikation (gap closure): Messung der Freigabe eigener Listen und der Provider-subline auf 35 und 32, subline und text ohne Besitzer (D-32-17), hinausgeteilte eigene Liste ohne `list` nicht beschreiben (D-32-18), `fetch` mit Kürzungsvermerk und Schwebe-Kennzeichen (W2), Beschreibung von `query` (W3), nicht gemessene Teile im Beleg (W4), Live-Beweis, Owner-Frage zum Push (TASK-02, TASK-05 bis TASK-07, TASK-09)

**Abtrennbar**: TASK-09 (`task:`-Id über `fetch` und Provider) ist ein eigener Plan und nur per Owner-Entscheid verschiebbar

### Phase 33: Aufgaben ändern

**Goal**: Ein Assistent kann eine einzelne Aufgabe abhaken, wieder öffnen, in den genannten Feldern ändern und in eine andere Liste verschieben, und zwar so, dass nie eine zwischenzeitliche Änderung überschrieben wird und nichts außer den genannten Feldern verloren geht; Löschen gehört nicht zum Umfang (Owner, 12.11.2026, Auswahl "Löschen raus")
**Depends on**: Phase 32, dazu Phase 30 (MESS-05 und MESS-06 samt Owner-Checkpoint E15)
**Requirements**: TMOD-01, TMOD-02, TMOD-03, TMOD-04, TMOD-05, TMOD-06, TMOD-08
**Success Criteria** (what must be TRUE):

  1. Eine über den Connector abgehakte Aufgabe ist in der Nextcloud so gespeichert, wie die Tasks-App sie beim Abhaken schreibt, und lässt sich mit demselben Werkzeug wieder öffnen; eine schon erledigte Aufgabe abzuhaken ist ein Erfolg ohne einen einzigen `PUT`; Unteraufgaben werden dabei mit abgehakt, wie in der Tasks-App
  2. Nach `tasks_update` unterscheidet sich das gespeicherte Objekt genau um die genannten Felder und die gemessenen Pflegefelder: der Rundlauf über die von der Tasks-App geschriebenen Fixtures erhält jede übrige Eigenschaft, `VALARM` und jede unbekannte `X-`Eigenschaft; ein Aufruf ohne Unterschied schreibt nicht
  3. Wird die Aufgabe zwischen Lesen und Schreiben geändert, lehnt der Connector ab und das Objekt ist unverändert; ein zweites Konto mit nur lesender Freigabe kann weder abhaken, ändern noch verschieben (Zwei-Konten-Negativbeweis live, auch unter AppAPI-Impersonation); wiederkehrende Aufgaben und Deck-Karten sind über keines der ändernden Werkzeuge erreichbar
  4. Eine Aufgabe lässt sich in eine ausdrücklich genannte, beschreibbare Liste verschieben, mit gleicher UID und ohne ein belegtes Ziel zu überschreiben; für Unteraufgaben gilt das in Phase 30 Gemessene. Ein Löschen gibt es nicht (Owner, 12.11.2026, Auswahl "Löschen raus")
  5. Jedes ändernde Werkzeug trägt ehrliche Annotationen und erzeugt je Aufruf einen Audit-Eintrag; überschreibender `PUT` und `MOVE` haben je genau eine Aufrufstelle, die das Destruktiv-Gate als eng benannte Ausnahme mit eigener Gegenprobe führt, während jede andere Stelle rot bleibt; das Budget ist aus der Messung des Endstands verankert, und alle Gates sind grün

**Plans**: TBD
**Abtrennbare Teile, je ein eigener Plan**: Abhaken und Wiederöffnen (TMOD-03); Felder ändern (TMOD-04); Verschieben (TMOD-08). 0.8.0 bleibt ohne jeden dieser Teile releasefähig; ein Teil fällt nur per Owner-Entscheid heraus. Das Löschen (TMOD-07) ist per Owner-Entscheid vom 12.11.2026 herausgefallen (Auswahl "Löschen raus", Aufwand gegen Nutzung)
**Research flag**: ja. Die Recherche vom 11.11.2026 deckt ändernde Zugriffe nicht ab; die Planung dieser Phase stützt sich auf den Messbericht aus Phase 30 und braucht eine eigene kurze Recherche zum Erhalt fremder Eigenschaften mit `icalendar`
**Aus Phase 30**: Ergebniswort für das Löschen "wiederherstellbar" (docs/spike-tasks.md Abschnitt 4.5): TMOD-07 wäre planbar gewesen, ist aber per Owner-Entscheid vom 12.11.2026 aus 0.8.0 gestrichen (Auswahl "Löschen raus"); die Messung bleibt als Beleg. Das Abbruchkriterium zu `MOVE` ist nicht ausgelöst: TMOD-08 ist planbar, der Kopf `Overwrite: F` ist Pflicht. Das Abbruchkriterium MESS-05 ist nicht ausgelöst. Owner-Entscheid vom 12.11.2026 (docs/spike-tasks.md Abschnitt 10.4): wiederkehrende Aufgaben bleiben abgelehnt (A15), Unteraufgaben werden beim Abhaken mit abgehakt (A16), Unteraufgaben ziehen beim Verschieben mit (A21; der Teil zum Mitlöschen entfällt mit TMOD-07). Das Erfolgskriterium 1 ist danach nachgezogen (Wortlaut vom Owner am 12.11.2026 freigegeben, "Ok"); was beim Wiederöffnen einer Elternaufgabe mit den Unteraufgaben geschieht, klärt die discuss-phase von Phase 33
**Offene Punkte für die discuss-phase (nicht entschieden)**:

  - E15 entschieden am 12.11.2026: eigener Admin-Schalter für die ändernden Aufgaben-Werkzeuge, ab Werk aus, nach dem Vorbild `NC_MCP_FILES_UPDATE` (Option "Empfehlung aus Abschnitt 10.3 übernehmen"), siehe docs/spike-tasks.md Abschnitt 10. Offen bleibt, welche Werkzeuge der Schalter im Einzelnen umfasst
  - Reicht die im selben Aufruf gelesene ETag, oder gibt das Modell die ETag aus `tasks_read` mit (Präzedenz `files_update`)?
  - Felder leeren (Fälligkeit entfernen, Elternbezug lösen) und der endgültige Name von `tasks_complete`

### Phase 34: Doku, Store, Release 0.8.0

**Goal**: Was 0.8.0 kann und was nicht, steht in drei Sprachen wahr und knapp in READMEs, Doku und Store-Text, die Schreibzusage ist auf das Ausgelieferte präzisiert, und Release 0.8.0 ist mit Owner-Freigabe im Store
**Depends on**: Phase 31, Phase 32, Phase 33 (fällt Phase 33 oder ein Teil davon per Owner-Entscheid heraus, beschreibt diese Phase den tatsächlich gebauten Stand)
**Requirements**: DOC-04, DOC-05, EXAPP-13, EXAPP-14, EXAPP-15
**Success Criteria** (what must be TRUE):

  1. `README.md`, `README.de.md`, `README.fr.md` und `docs/` nennen dieselbe Werkzeug- und Familienzahl wie die Registry, die Rechtetabelle führt jedes neue Werkzeug mit seiner Stufe, `docs/threat-model.md` nennt die Aufgabenfamilie samt Fremdtext aus geteilten Listen, und die Zähl- und Wahrheitstests der Doku sind grün
  2. Die Zusage "create-only, keine destruktiven Writes" ist an jeder Stelle des Inventars aus Phase 30 auf das Ausgelieferte präzisiert (eine einzelne Aufgabe abhaken, wieder öffnen, ändern, verschieben, nur mit gelesener ETag; Löschen als bewusste Grenze benannt), auch in `.planning/PROJECT.md`, und ein Test hält die Aussage gegen die Registry
  3. Der Store-Text liegt in drei Sprachen als kurze Faktenliste vor, der Owner hat den Entwurf vor dem Release gesehen und freigegeben, und erst danach ist der SHA-256-Pin erneuert
  4. Release 0.8.0 ist im Store: `CHANGELOG.md`, `CHANGELOG.de.md` und `CHANGELOG.fr.md` tragen denselben 0.8.0-Block, der Gesamtlauf aller Gates ist lokal und im CI einschließlich `canary-nc35` grün, die Nachweiszeilen des Runbooks sind geschlossen; Push, Tag und Submit sind je mit Owner-Freigabe geschehen
  5. Für #32 und #44 liegen kurze Antwortentwürfe ohne schließende Schlüsselwörter vor; gepostet ist bis zum Store-Release nichts

**Plans**: TBD

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
| 31. Ordner anlegen | v1.8 | 0/6 | Planned | - |
| 32. Tasks-Bundle suchen, lesen, anlegen | v1.8 | 10/10 | Human Needed | - |
| 33. Aufgaben ändern | v1.8 | 0/TBD | Not started | - |
| 34. Doku, Store, Release 0.8.0 | v1.8 | 0/TBD | Not started | - |

## Coverage v1.8

| Requirement | Phase |
|-------------|-------|
| MESS-01 | Phase 30 |
| MESS-02 | Phase 30 |
| MESS-03 | Phase 30 |
| MESS-04 | Phase 30 |
| MESS-05 | Phase 30 |
| MESS-06 | Phase 30 |
| FOLD-01 | Phase 31 |
| FOLD-02 | Phase 31 |
| FOLD-03 | Phase 31 |
| FOLD-04 | Phase 31 |
| FOLD-05 | Phase 31 |
| FOLD-06 | Phase 31 |
| TASK-01 | Phase 32 |
| TASK-02 | Phase 32 |
| TASK-03 | Phase 32 |
| TASK-04 | Phase 32 |
| TASK-05 | Phase 32 |
| TASK-06 | Phase 32 |
| TASK-07 | Phase 32 |
| TASK-08 | Phase 32 |
| TASK-09 | Phase 32 |
| TMOD-01 | Phase 33 |
| TMOD-02 | Phase 33 |
| TMOD-03 | Phase 33 |
| TMOD-04 | Phase 33 |
| TMOD-05 | Phase 33 |
| TMOD-06 | Phase 33 |
| TMOD-07 | Out of Scope (Owner, 12.11.2026) |
| TMOD-08 | Phase 33 |
| DOC-04 | Phase 34 |
| DOC-05 | Phase 34 |
| EXAPP-13 | Phase 34 |
| EXAPP-14 | Phase 34 |
| EXAPP-15 | Phase 34 |

Zugeordnet: 34/34 (Phase 30: 6, Phase 31: 6, Phase 32: 9, Phase 33: 8, Phase 34: 5), keine Waisen, keine Doppelungen. Der Mess-Spike trägt anders als in v1.7 eigene Requirements, weil E12 eine Messung verlangt und Abbruchkriterien an ihm hängen. Jede Annahme aus REQUIREMENTS.md (A1 bis A19, A21) ist einer Phase zur Klärung zugeordnet, bis auf A10 alle Phase 30.

## Next

Aktiver Milestone: v1.8. Phase 30 ist ausgeführt: 30-01 bis 30-05 (11. und 12.11.2026; MESS-01 bis MESS-06 gemessen; die Abbruchkriterien zu MESS-01, MESS-05 und MESS-06 MOVE nicht ausgelöst, Ergebniswort für das Löschen "wiederherstellbar", Inventar A17 liegt vor; jede Annahme A1 bis A19 und A21 trägt im Bericht `docs/spike-tasks.md`, Abschnitt 8, ihren Status). Der Owner hat E15 am 12.11.2026 entschieden ("Empfehlungen übernehmen"): eigener Admin-Schalter für die ändernden Aufgaben-Werkzeuge, ab Werk aus; mit derselben Antwort A15 (wiederkehrende Aufgaben bleiben abgelehnt), A16 (Unteraufgaben beim Abhaken mit abhaken) und A21 (Unteraufgaben ziehen mit und werden mitgelöscht), Bericht Abschnitt 10.4. Am 12.11.2026 hat der Owner das Löschen einer Aufgabe (TMOD-07) aus 0.8.0 gestrichen (Auswahl "Löschen raus"); der Teil "werden mitgelöscht" aus A21 entfällt damit. Nächster Schritt ist die Planung von Phase 31; vor der Planung von Phase 33 ist dort das Erfolgskriterium 1 nach A16 nachzuziehen. Reihenfolge: 30, 31, 32, 33, 34; Phase 31 ist allein releasefähig, Phase 32 ohne Phase 33. Unverändert außerhalb dieses Milestones: files_update-Weiterentwicklung und die F13-Spur (milestones/v1.6-REQUIREMENTS.md).

---
*Roadmap created: 2026-08-14 (granularity: coarse, mode: mvp); v1.0 abgeschlossen: 2026-08-20; v1.1 abgeschlossen: 2026-08-20 (Phase 7 deferred); v1.2 abgeschlossen: 2026-08-25 (Release 0.1.8 live); v1.3 abgeschlossen: 2026-08-26 (Release 0.1.9 live); v1.4 abgeschlossen: 2026-08-28 (Release 0.1.10 live); v1.5 abgeschlossen: 2026-08-31 (Release 0.1.11, openDesk-Spike, Audit-Log; Abschluss nachgetragen 2026-09-18); v1.6 aufgesetzt: 2026-09-18 (Phasen 20-24, 15 Requirements, granularity coarse); v1.6 abgeschlossen: 2026-09-26 (Token-Exchange-Pfad komplett, 15/15 Requirements, kein Release); v1.7 aufgesetzt: 2026-09-26 (Phasen 25-29, 14 Requirements, granularity coarse); v1.7 abgeschlossen: 2026-10-01 (kein-ki-Filter komplett, 14/14 Requirements, kein Release; Release 0.4.0 nach PR #14); v1.8 Roadmap geschrieben: 2026-11-11 (Phasen 30-34, 34 Requirements, granularity coarse; Owner-Entscheide E1 bis E14)*

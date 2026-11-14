# Retrospective: MCP Connector für Nextcloud

Living document, appended at each milestone close.

## Milestone: v1.0 , MVP im Store

**Shipped:** 2026-08-20
**Phases:** 5 | **Plans:** 50 | **Tasks:** 111 | **Timeline:** 2026-08-14 bis 2026-08-20 (7 Tage)

### What Was Built

Ein MCP-only-ExApp für Nextcloud, live im App Store (0.1.0 am 19.08., 0.1.2 am 20.08.):
16 kuratierte, auf Lesen ausgelegte Tools (Dateien, Kalender, Notizen, Deck, Kontakte,
Unified Search, prepare_context), eigener OAuth-2.1-Autorisierungsserver nach
MCP-Authorization-Spec (E2E gegen Claude.ai und ChatGPT bewiesen), Per-User-Verwaltung
mit Pause/Disconnect, Purge-Kommando mit vollständiger Datenräumung, dreisprachige
Store-Texte und siebenteilige Client-Doku.

### What Worked

- Messen statt vermuten: Jede kritische Annahme wurde live gemessen (Discovery-Spike,
  DAV-Impersonation, 401-Ursache, Crash-Loop-Rundlauf). Zwei Vermutungen aus früheren
  Sessions wurden dadurch widerlegt statt fortgeschrieben (401 "wirkt nie", Loopback als
  Cursor-Blocker).
- Gap-Closure-Zyklus: Verifier fand 3 echte Lücken nach Phase 5; der --gaps-Lauf schloss
  sie in einem Tag mit Live-Nachweisen statt Behauptungen.
- Runbooks zahlen sich sofort aus: docs/store-submission.md machte das 0.1.2-Release
  ohne Recherche möglich; der Session-basierte Store-Upload ist jetzt dokumentiert.
- Design-Konstante "kann nichts zerstören" trug durch alles: Architektur-Gate, Tests,
  Store-Text, LinkedIn-Narrativ, FAQ.

### What Was Inefficient

- Worktree-Isolation funktioniert in dieser Umgebung nicht (CWD system32 ist kein Repo);
  alle Executor liefen sequenziell. Bei 16 Plänen in Phase 5 kostete das Wandzeit.
- Plan 05-13 wurde gegen eine ungeprüfte Annahme geplant (Overlay-Cache); die Messung in
  05-12 machte 2 von 3 Tasks obsolet. Messung vor Planung wäre billiger gewesen.
- Der Review-Fund-Backlog (BL-08..BL-13) sammelte sich über drei Phasen, bevor ein
  einziger Abarbeitungstag ihn leerte; kleinere, frühere Batches hätten Re-Reviews gespart.

### Patterns Established

- Executor-Umgebungsblock (cd-Falle, uv --no-sync, Commit-Regeln) als Standard-Prompt.
- Beweistabellen mit Datum+Kommando in Runbooks (store-submission, MEASUREMENTS-Dateien).
- Gemeinsame Härtungs-Helfer statt Duplikate (bounded_body, marks.py, store_opener).
- Owner-Entscheidungen als kompakte Batch-Frage einholen, dann autonom durcharbeiten.

### Key Lessons

- Auto-Modus-Checkpoints: erste Option nie blind wählen, wenn sie physisch unmöglich ist
  (MUCGPT ohne Instanz); Evidenz schlägt Regel.
- Upstream zuerst suchen: der NC-34-UI-Befund war bereits gemeldet UND gefixt (34.0.3);
  das ersparte ein Duplikat-Issue.
- Release-Tags und Milestone-Tags müssen kollisionsfrei sein: release.yml triggert auf
  v*, daher Milestone-Tag milestone-v1.0 statt v1.0.
- Der Store hotlinkt Screenshot-URLs: Bildtausch ohne Release möglich, solange die URL
  stabil bleibt.

### Cost Observations

- Modell-Mix: Executor/Planner opus, Checker/Verifier sonnet; Orchestrierung in einer
  Session mit Sub-Agents (größte Läufe ~200-300k Tokens je Executor).
- Sessions: im Kern 6 Arbeitstage (14.-20.08.), Abschlusstag mit ~20 Commits und Release.

## Milestone: v1.1 , Verwaltungs-Clients und Härtungs-Reste

**Shipped:** 2026-08-20
**Phases:** 1 (Phase 6; Phase 7 deferred) | **Plans:** 11 (10 + 1 Gap-Closure)

### What Was Built

CIMD als DCR-Alternative (live mit Claude Code bewiesen), SSRF-gehärteter Dokumentabruf mit IP-Pinning und Negativkatalog, RFC-8252-7.3-Loopback-Portregel, CIMD als fünfter Admin-Settings-Wert, Cursor-Messbefund mit BL-14-Entscheid, Ein-Klick-Story auf NC 34.0.3 wörtlich wahr, Conference-Demo-Runbook plus Lightning-Talk-Entwurf.

### What Worked

- "Messen statt vermuten" als Phasen-Grundton: die Loopback-Regel wurde VOR dem CIMD-Zweig gebaut, weil die Recherche das echte CIMD-Dokument von Claude Code abgerufen hatte; ohne diese Reihenfolge wäre AUTH-08 unerreichbar gewesen.
- Der Gap-Closure-Zyklus trug zweimal sauber: CLIENT-04 (Requirement ehrlich auf das Gemessene umformuliert statt D-35 aufzuweichen) und Milestone-Audit-Blocker B-1 (Admin-Schalter-Lücke, inline geschlossen).
- Ein Enforcement-Punkt (provider.get_client) zahlte sich aus: die CIMD-Kontrollen mussten nirgends dupliziert werden, und der Integrations-Checker konnte genau das nachrechnen.

### What Was Inefficient

- tests/contract lief bei den Executoren nicht mit (nur tests/unit) , ein roter CI-Lauf (IN-04-Tool-Zahl-Regel), der lokal vermeidbar war. Merksatz: voller Lauf inkl. contract vor jedem Push.
- Doku und Code drifteten am selben Tag: zwei oauth-setup.md-Aussagen wurden durch die eigenen Review-Fixes (a47bb57/bd75cd8) falsch und mussten im Audit nachgezogen werden. Review-Fixes brauchen einen Doku-Sweep im selben Commit-Zug.
- Der einzige CIMD-E2E-Live-Beleg entstand vor den Review-Fixes (W-5) , Live-Rerun steht als Tech-Debt.

### Patterns Established

- MEASUREMENTS-Dateien als Beweisform auch für Fremd-Client-Verhalten (Cursor: drei Kontrollanfragen trennen Ursache von Verdacht).
- Checkpoint-Disziplin bei Fremd-Software: nichts installieren/neustarten, was dem Owner gehört; die Abweisung selbst ist ein gültiger Messbefund.
- Owner-genehmigte Requirement-Umformulierung mit Datum, Urheber, verworfenen Alternativen und Rohbeleg statt stiller Abschwächung.

### Key Lessons

- Ein Client, der die DCR-Antwort nicht zurückliest (Cursor), macht Teilregistrierung wirkungslos , der Fehlschlag wandert nur den Endpoint entlang. Sichtbarkeit + dokumentierter Ausweichweg ist die richtige Antwort, wenn die Sicherheitsentscheidung steht.
- Store-Installationen haben keine Deploy-Env: jeder neue Schalter MUSS in die Admin-Settings-Kette (CONFIG_KEYS + Formular), sonst ist er für Ein-Klick-Nutzer nicht bedienbar (B-1).
- Externe Taktung gehört in eine eigene Phase, die deferred werden kann, ohne den Milestone zu blockieren , genau so geschnitten, genau so gebraucht.

### Cost Observations

- Modell-Mix: Executor/Planner/Researcher/Auditoren opus, Checker/Verifier sonnet; größte Läufe ~200-350k Tokens je Agent.
- Sessions: 1 Arbeitstag (20.08., Milestone-Init bis Abschluss inkl. Audit-Fixes).
- Notable: 1 roter CI-Lauf, 1 API-Abbruch mit sauberem Retry (06-02), 2 menschliche Checkpoints (Cursor-Login, Owner-Entscheide).

## Milestone: v1.2 , Kuratierte Breite

**Shipped:** 2026-08-25
**Phasen:** 4 | **Pläne:** 28

### What Was Built

Talk, Tables und Mail als drei neue Familien (21 Tools gesamt), Mail strikt lesend mit benannter Lethal-Trifecta-Grenze und Admin-Schalter für den einzigen Ausgangskanal; prepare_context mit vier gemessenen Beinen; fetch löst sieben Id-Arten auf; Budget-Gate erstmals aus einer Messung gesenkt (18500 auf 18000); Releases 0.1.4 bis 0.1.8 im Store, 0.1.8 macht den Spendenlink sichtbar.

### What Worked

- Risiko-Reihenfolge statt Attraktivität: der blockierende Mail-Spike (Phase 8) beantwortete die einzige Unbekannte, bevor Phasen 10/11 geplant wurden; der Schnitt hielt unverändert.
- Die "mechanische Checkliste" einer neuen Familie, einmal an Tables etabliert, machte Talk und Mail zu kürzeren Phasen.
- Messen statt behaupten als Phasen-Muster: Nebenwirkungsfreiheit, 1+N-Kosten und Zeitbudgets wurden live gemessen; drei Setzungen wurden Messungen, keine musste geändert werden.
- Owner-Gates an den irreversiblen Stellen (Tag-Push, Store-Upload) funktionierten sauber als Checkpoints, der Rest lief autonom.
- Planzeit-Threat-Register in allen Plänen machte secure-phase zur reinen Verifikation (74/74 ohne Neubau).

### What Was Inefficient

- Die Release-Nummer im ROADMAP-Titel (0.1.6) war zweimal überholt, bevor die Phase startete; vorgezogene Releases müssen die Roadmap sofort mitziehen.
- Ein Planner-Verifikationsschnipsel nannte eine falsche Signatur, ein Plan einen falschen Antwortschlüssel (conversations statt results) , beides fingen die Executor am echten Code ab, kostete aber Aufmerksamkeit.
- Der Runbook-Text und das Build-Skript widersprachen sich bei der Signatur bis nach dem Release (erst eb05a6f räumte auf).

### Patterns Established

- Ein Bein je Quelle in prepare_context: eigenes asyncio.timeout-Budget, eigener degraded-Satz, Tool-Schicht statt Client-Schicht (Gate-Test erzwingt es).
- Jede Kappung schreibt ihren eigenen degraded-Satz; verschluckte Envelope-Kappungen sind Review-Warnings.
- Budget-Gate-Regel: Messung plus 15 Prozent, aufgerundet auf 500, nur mit neuer Messzeile; ein ehrliches "Marke nicht erreicht" ist ein gültiger Ausgang.
- Release-Reihenfolge: Branch-Push vor Tag, Signatur nur über das heruntergeladene Asset, Cache-Verzögerung ist kein 0.1.9-Grund.

### Key Lessons

- Navigations-unread=0 trotz ungelesener Mails: fremde Felder erst messen, dann benutzen , die Postfachliste war der ehrliche Zähler.
- Ein assistententauglicher Suchtreffer braucht beide Hälften: provider_map-Eintrag UND die resolvable-Wahrheit im Bündel (_short war die versteckte zweite Hälfte von TOOL-16).
- tar.gz ist nicht byte-reproduzierbar: 45710 lokal vs 45546 publiziert; jede lokale Signatur ist wertlos für den Store.

### Cost Observations

- Modell-Mix: Executor/Planner/Researcher/Security-Auditor opus, Checker/Verifier/Integration sonnet.
- Sessions: 4 Arbeitstage (21.08. Phasen 8+9, 24.08. Phase 10, 25.08. Phase 11 inkl. Release und Milestone-Abschluss).
- Notable: 1 API-Abbruch (11-01) mit sauberem Continuation-Agent; 2 Owner-Checkpoints (Tag-Freigabe, Store-Sitzung); Store-Upload aus dem Browser-Seitenkontext, HTTP 201 beim ersten Versuch.

## Milestone: v1.3 , Pflege und 0.1.9

**Shipped:** 2026-08-26
**Phasen:** 2 | **Pläne:** 10

### What Was Built

Die vier v1.2-Schulden geschlossen (message_truncated je Ebene eine Bedeutung, Id-Codec als einzige Quelle, AST-Gate gegen Privat-Durchgriffe, drei Security-Nachzieher als Regressionstests); CIMD nach den v1.1-Review-Fixes live nachgemessen statt behauptet (Messweg A mit echtem Client, Gegenprobe mit abgeschaltetem Schalter); Release 0.1.9 im Store mit elf Proof-Zeilen; Enterprise-Fake-Door (ISV-Vorhaben) in READMEs und Store-Beschreibungen; GitHub-Actions auf Node-24-Majors.

### What Worked

- Owner-Anweisungen mitten im Lauf ("ISV-Vorhaben berücksichtigen", "nichts Enterprise-Internes im Repo") ließen sich sauber als CONTEXT-Decisions bzw. Nachtrags-Commits einarbeiten, ohne die Phase neu zu schneiden.
- Die Messung gegen den Kandidaten VOR dem Tag entkoppelte den CIMD-Beweis von der Owner-Freigabe; der leere Diff Quellstand==Tag-Stand machte den Beweis übertragbar.
- Der Review-Fix WR-03 (interne Go-Kriterien aus der öffentlichen Datei) fing einen Fake-Door-Konstruktionsfehler, bevor er die Messung verfälschen konnte; der Owner-Entscheid D-07 zog die Linie dann noch schärfer.
- Der workflow_dispatch-Dry-Run in release.yml erlaubte, die Action-Bumps ohne Release zu validieren.

### What Was Inefficient

- Die "fünf Versionsstellen" der Roadmap waren real sechs (uv.lock) , der Pattern-Mapper fand es, aber die Requirement-Formulierung hätte es tragen sollen.
- Zwei Doku-Fakten überlebten das Review nicht (falsche v1.2-Messzahl in einer Proof-Zeile, falsche Unsichtbarkeits-Begründung im Changelog); Beweisdokumente brauchen dieselbe Faktenprüfung wie Code.
- Nach dem Tag driftet der Repo-Changelog vom signierten Asset (WR-02-Fix) , bekanntes, akzeptiertes Muster, aber jedes Mal eine Audit-Zeile wert.

### Patterns Established

- Fake-Door-Regel: öffentlicher Text nennt nur das Angebot und den Kontakt; Go-Kriterien und Messlogik bleiben außerhalb des Repos (D-07).
- CIMD-/Feature-Beweise gegen den Release-Kandidaten im lokalen Registry fahren, Quellstand-Gleichheit zum Tag per Diff belegen.
- Fremde Actions: exakte Version verifizieren (setup-uv pflegt seit v8 keine floating Major-Tags), Bumps via CI-Push plus Dry-Run validieren, nie im Release-Moment.

### Key Lessons

- ConPTY per ctypes braucht STARTF_USESTDHANDLES mit den Konsolen-Handles, sonst hängt das Kind an der Pseudo-Konsole (Messweg-A-Treiber).
- bootstrap_exapp.sh braucht HP_SHARED_KEY für jeden compose-Aufruf, sonst lügt die Fehlermeldung ("Nextcloud is still not installed").
- Ein Akzeptanzkriterium darf nicht das Muster verbieten, das seine eigene Regel nennen muss (Credential-Grep vs. code_challenge).

### Cost Observations

- Modell-Mix: Executor/Planner/Researcher/Security-Auditor opus, Checker/Verifier/Integration sonnet; Store-Upload-Plan im Catch-all-Agenten (Playwright-Zugriff).
- Sessions: 2 Arbeitstage (25.08. Planung+Execution+Release, 26.08. D-07 + Action-Bumps + Abschluss); 1 Session-Limit-Abbruch des Planners, sauber per Resume fortgesetzt.
- Notable: 1 Owner-Checkpoint (Tag-Freigabe mit Store-Weg-Abfrage), Store-Upload HTTP 201 beim ersten Versuch, Review 0C/3W alle gefixt.

## Milestone: v1.4 , Pflege und 0.1.10

**Shipped:** 2026-08-28
**Phasen:** 2 | **Pläne:** 6

### What Was Built

Die Store-Beschreibung trägt einen kurzen Enterprise-Abschnitt mit dem Kontakt admin@infranode.dev, und die private Outlook-Adresse ist aus dem öffentlichen Manifest verschwunden. Dazu die Doku-Reste aus v1.3 (Übersetzungsfehler, hängende Changelog-Linkdefinition, Ampersand-Kommentar, chronologische Nachweistabelle), die Entscheidung zur Vokabular-Gate-Reichweite gegenüber .planning als begründete Ausnahme mit Halter-Test, und Release 0.1.10 im Store.

### What Worked

- Owner-Eingriffe mitten im Lauf (Enterprise-Text kürzen, Kontaktwechsel, Trifecta-Absatz entschlacken) ließen sich ohne Neuschnitt der Phasen einarbeiten; der Preis war eine Post-Tag-Drift, die aktenkundig gemacht wurde statt sie zu verstecken.
- Der Owner-Checkpoint vor dem Tag hat wieder sauber gehalten: fünf Stunden Wartezeit, kein Tag-Kommando in der Zwischenzeit, Freigabe wörtlich protokolliert.
- Die drei Prüfinstanzen haben unterschiedliche Dinge gefunden, keine war redundant: das Review die falschen Textaussagen, der Security-Auditor zwei ungenaue Beweiszeilen, der Integrationscheck zwei falsch gebuchte FIXED-Markierungen und eine strukturell unerfüllbare Roadmap-Formulierung.

### What Was Inefficient

- Zwei Review-Befunde wurden als FIXED gebucht, obwohl nur ihr halber Auftrag erledigt war (Adresse gewechselt, aber kein Runbook-Nachweis; Changelog korrigiert, aber kein Unreleased-Anker). Erst der Integrationscheck hat es aufgedeckt.
- Drei eigene Beweiszeilen mussten nachkorrigiert werden, weil sie im Moment des Schreibens stimmten und Minuten später nicht mehr. Eine Zeile, die einen Zustand behauptet, braucht entweder eine Zeitgrenze oder einen Nachtrag.
- Das Roadmap-Goal versprach, die Doku-Fixes fahren im Asset mit; zwei der vier betroffenen Dateien sind gar keine Archivmitglieder. Solche Versprechen gegen das Build-Skript prüfen, bevor sie in die Roadmap kommen.

### Patterns Established

- Post-Tag-Drift wird in der Nachweistabelle datiert vermerkt, nie im Asset nachgebessert; eine spätere Zeile darf eine frühere ausdrücklich aufheben.
- Eine Zeitgrenze gehört in jede Zeile, die einen Repo-Zustand behauptet ("true for the state at HH:MMZ only").
- Ausstehende Textänderungen bekommen sofort einen `[Unreleased]`-Abschnitt samt Linkdefinition, damit das Gedächtnis nicht nur in Planungsartefakten lebt.
- Öffentliche Store-Felder brauchen einen Prüfschritt im Runbook: das `authors`-Feld ist zehn Releases lang unbemerkt geblieben.

### Key Lessons

- `0.1.10` sortiert als Zeichenkette vor `0.1.9`. Katalogprüfungen fragen nach Enthaltensein, nie nach Reihenfolge.
- Die Store-Detailseite rendert die Beschreibung clientseitig; als Beleg taugt nur das `translations`-Feld des Katalogeintrags.
- Ein als behoben gebuchter Review-Befund ohne nachgefahrenen Beleg ist schlimmer als ein offener: er verschwindet aus der Wiedervorlage.

### Cost Observations

- Modell-Mix: Executor/Planner/Auditor opus, Checker/Verifier sonnet; ein Fable-Limit-Abbruch mitten im Store-Upload, danach vom Orchestrator selbst beendet.
- Sessions: 1 Arbeitstag (28.08.), Release-Freigabe nach fünf Stunden Checkpoint-Wartezeit.
- Notable: drei Runden secure-phase für einen einzigen Threat (T-15-PT), weil jede Runde einen weiteren ungenauen Halbsatz in derselben Beweiszeile fand.

## Milestone: v1.5 , Vorlauf openDesk (nachgetragen)

**Shipped:** 2026-08-31 (Abschluss nachgetragen 2026-09-18, dieser Eintrag nachgetragen 2026-09-26)
**Phasen:** 4 | **Pläne:** 32

### What Was Built

Release 0.1.11 (gekürzter Trifecta-Absatz, Autorenkontakt admin@infranode.dev), zeitboxierter openDesk-Spike auf OpenProject mit Fragenliste für den ISV-Call, Audit-Log als erster Enterprise-Baustein (hash-verkettet, ab Werk aus, mit Bedienung und Textnachzug).

### Key Lessons

- `/gsd:complete-milestone` nie aufschieben: der Milestone stand 18 Tage als complete in STATE.md, ohne Eintrag, ohne Archiv. Der Nachtrag kostete eine eigene Aufräumrunde beim v1.6-Start.
- Eintrag bewusst schlank, weil die Rohdaten (Sessions, Gap-Runden) beim Nachtrag nicht mehr sauber rekonstruierbar waren; Aussagen stammen aus den Phase-Verifikationen.

## Milestone: v1.6 , F13 Token Exchange Identity Mapper

**Shipped:** 2026-09-26
**Phasen:** 5 | **Pläne:** 22

### What Was Built

Ein zweiter, ab Werk ausgeschalteter Prüfpfad nimmt ein nach RFC 8693 getauschtes Keycloak-Token an und handelt unter dem gemappten Nextcloud-Konto: eine gehärtete Schlüsselsatz-Schicht (Phase 20), ein freistehender JWS-Prüfer (21), Konfigurationskette mit formbasierter Weiche und vor-authentischer Drossel (22), Konto-Mapping mit zwei Profilen und beiden Credential-Wegen (23), Audit-Anschluss, Trockenlauf-Kommando, Zwei-Konten-Negativbeweis und Einrichtungsdoku (24). Alles ohne eine einzige F13-Antwort; das Abhängige blieb Konfiguration mit dokumentierten Defaults.

### What Worked

- Die Milestone-Prämisse "nur entscheidungsunabhängige Teile bauen" hat gehalten: 15/15 Requirements geliefert, während die vier externen F13-Entscheidungen offen blieben und als benannte Andockpunkte dokumentiert sind.
- Messen statt behaupten durchgezogen: Token-Umschlag exakt 8192 Bytes, 36 JWKS-Abrufe je 300 s, 429-Lauf, Zwei-Konten-Beweis mit Apache- und Impersonationslog, 200-dann-401-Widerruf.
- Ein am Checkpoint vorgelegter Zielkonflikt (Rolle von occ oauth2:add-client) wurde als offene F13-Antwort markiert statt geraten; ein Test hält die Markierung.

### What Was Inefficient

- Drei Session-Limit-Unterbrechungen in Phase 23 mussten mit frischen Executors überbrückt werden; RAM-Knappheit der Box zwang Vollläufe an Gate-Punkte.
- Der Plan 24-08 versprach eine Mitigation ("Basic-Header ändert die Identität nicht"), die die eigene Messung widerlegte. Der Befund wurde sauber dokumentiert, aber das Register erst in der secure-phase am Abschlusstag ehrlich gemacht (T-24-32 als akzeptiertes Risiko R-24-05).
- PR #8 wurde nach vier Tagen Funkstille eigenmächtig fertiggestellt und gemergt, gegen die Owner-Ansage. Fachlich sauber, prozessual falsch; daraus wurde eine feste Regel.

### Patterns Established

- Plan-Zeit-Threat-Register über alle Pläne plus secure-phase mit Zeilenbelegen am aktuellen HEAD, nach Rebase erneut belegt statt alte SHAs zu zitieren.
- Externe Abhängigkeiten als markierte, getestete Andockpunkte (Konfiguration mit Default plus Ehrlichkeitsabschnitt in der Doku) statt als Blocker oder Ratespiel.

### Key Lessons

- phase.complete und milestone.complete verfälschen STATE.md weiterhin; nach jedem Lauf von Hand nachziehen (diesmal: stopped_at zeigte auf 22-03).
- Die automatische Accomplishment-Extraktion liest auch Blocking-Hinweise als One-Liner; MILESTONES.md nach milestone.complete immer redigieren.
- Eine gemessene Widerlegung einer geplanten Mitigation ist ein Register-Eintrag, keine Fussnote: Disposition offen lassen und den Owner entscheiden lassen (akzeptieren oder bauen).

### Cost Observations

- Modell-Mix: Executor/Planner/Auditor opus (Owner-Vorgabe; bei Limits frischer Executor), Checker/Verifier sonnet, Orchestrierung fable.
- Sessions: 9 Kalendertage (18.-26.09.), 217 Commits, +40.143/-3.428 Zeilen über 174 Dateien.
- Notable: der Abschlusstag lief komplett in einer Session (Rebase auf PR #8, Gates, secure-phase, Archiv), weil alle Phasen schon verifiziert waren.

## Milestone: v1.7 , Ausschluss-Tag kein-ki

**Shipped:** 2026-10-01
**Phasen:** 5 | **Pläne:** 38 | **Tasks:** 92

### What Was Built

Eine Datei oder ein Ordner mit dem System-Tag `kein-ki` erscheint in keiner Tool-Antwort mehr: Mess-Spike gegen NC 32 bis 35 vor jeder Designentscheidung (Phase 25), policy-freier Tag-Client und request-gebundener Guard mit drei Zuständen (26), Anschluss aller dateitragenden Familien samt Sandbox-Parität für pfadlose Treffer (27), die Grenze als Gate mit Klassifikations-Freeze, Kanarie, byte-gleichen Paaren und AST-Nadeln (28), Prüfkommando `occ mcp_connector:exclusion:check` und dreisprachige Betreiberdoku mit 17 ehrlichen Grenzen (29). Kein Release; der Filter reist mit 0.4.0.

### What Worked

- Erst messen, dann bauen: der Spike entschied Fail-closed-Auslöser, Notes-Weg und Batch-Strategie, bevor eine Zeile Produktcode stand; die PostgreSQL-Gegenmessung verhinderte eine falsche SQLite-getriebene Batch-Entscheidung.
- Die Kanarie über alle 22 Werkzeuge fand einen echten Abfluss (Dateiname über den Suchprovider `talk-conversations`), den kein Unit-Test gesehen hätte; nach D-28-21 ist sie in allen vier Modi grün.
- Byte-Gleichheit als Prüfkriterium (getaggt gegen nicht existent, auch im Ausfall) machte "verrät nichts" zu einem roten oder grünen Test statt einer Behauptung.
- Gemeinsame Owner-Abnahme des Doku-Wortlauts: vier Korrekturen am 01.10., danach freigegeben.

### What Was Inefficient

- Die Wanduhr-Schwelle für prepare_context kostete zwei Lückenpläne (27-09, 27-10) und mehrere Messfenster; am Ende lag schon die Kontrolle mit dem alten Code über der Schwelle, und das Rauschen übertraf die Reserve. Die Abnahme mit Begründung hätte früher kommen können.
- Fünf Tage ohne Push (171 Commits voraus) hielten die CI-gebundenen Nachweise (SBX-01 gegen echten Findling, canary-nc35) bis zum Abschlusstag offen; zwei Verifikationen standen deshalb lange auf human_needed.
- RAM-Knappheit der Box zwang schwere Agenten und Docker-Läufe in Serie; eine RAM-Prüfung vor Messläufen war nur Arbeitsanweisung und musste als AR-29-03 akzeptiert werden.

### Patterns Established

- Live-Harness mit gelesenem Aufräumbeweis je Nebenwirkung (canary_world) als wiederverwendbare Basis für Grenz-Gates.
- Doku-Wahrheitstest: jede Grenzaussage der Betreiberdoku verweist auf einen Befund und wird gegen Code-Konstanten und Rohbelege geprüft.
- Store-Texte per SHA-256-Pin im CI eingefroren, solange ein Feature nicht released ist.

### Key Lessons

- milestone.complete zieht die Accomplishments nur aus der letzten Phase, zählt die Tasks falsch (18 statt 92) und schreibt Gedankenstriche in STATE.md; MILESTONES.md und STATE.md nach jedem Lauf von Hand redigieren.
- audit-open meldet Quick-Tasks als "missing", obwohl SUMMARY-Dateien mit status complete vorliegen; vor einem Abbruch die Datei selbst ansehen.
- Produktdoku, die Befunde unter .planning/phases/ verlinkt, verhindert das Phasenarchiv beim Milestone-Abschluss; für künftige Doku-Befundlinks einen stabilen Ort wählen (z. B. docs/evidence/) oder den Umzug als eigene Aufgabe planen.
- CI-gebundene Must-haves früh pushen oder ausdrücklich als Abschluss-Gate planen, sonst wandern sie als human_needed bis ans Milestone-Ende.

### Cost Observations

- Modell-Mix: Executor/Planner/Auditor opus (Owner-Vorgabe), Checker/Verifier sonnet, Orchestrierung fable.
- Sessions: 6 Kalendertage (26.09. bis 01.10.), 343 Commits, +57.263/-1.733 Zeilen über 264 Dateien.
- Notable: parallel liefen zwei Hotfix-Releases (0.3.1, 0.3.2) und PR #13 außerhalb des Milestones, ohne den Phasenplan zu stören.

## Milestone: v1.8 , Tasks-Bundle und Ordner anlegen

**Shipped:** 2026-11-14 (Release 0.8.0 im Store)
**Phasen:** 5 | **Pläne:** 50 | **Tasks:** 163

### What Was Built

Ein Mess-Spike gegen echte Instanzen vor dem ersten Produktcode (Phase 30), `files_create_folder` hinter der ganzen v1.7-Kette (31), die zehnte Familie `tasks` mit Suchen, Lesen, Anlegen und `task:`-Id über `fetch` (32), Abhaken, Ändern und Verschieben einer einzelnen Aufgabe hinter `NC_MCP_TASKS_UPDATE`, nur mit gelesener ETag (33), präzisierte Schreibzusage, dreisprachiger Store-Text und Release 0.8.0 (34). Kein Löschen: TMOD-07 ist per Owner-Entscheid vom 12.11.2026 gestrichen, obwohl die Messung "wiederherstellbar" ergab.

### What Worked

- Erst messen, dann bauen, wie in v1.7: der Spike belegte `MKCOL` unter Impersonation, `If-Match`, den Erhalt fremder Eigenschaften und `MOVE` mit `Overwrite: F`, bevor ein Werkzeug entstand; kein Abbruchkriterium wurde ausgelöst.
- Live-Läufe auf Nextcloud 35 und 32, je ohne und mit Tasks-App, fanden Fehler, die kein Unit-Test sah: die subline ohne führendes Leerzeichen auf 35 (32-09), ein zu knappes Budget je Liste bei 2000 offenen Aufgaben (32-10), den Kaltstart-Befund `geteilt-namen` (33-11).
- Die Gates aus v1.7 trugen die neuen Schreiber ohne neue Grundlage: Kanarie, Paartests, Klassifikations-Freeze, Destruktiv-Gate mit eng benannten Ausnahmen (`EXPECTED_PUT_CALLS` 7, MOVE-Pin) und Budget nach der Hausregel.

### What Was Inefficient

- Der Umfang wuchs nach der Recherche am selben Tag zweimal (E7, E8 am 11.11.2026) und schrumpfte einen Tag später wieder (E13, 12.11.2026); Messungen für das Löschen liefen, bevor es gestrichen wurde.
- Phase 31 blieb bei der Erstprüfung bei 4/5 (Kriterium 5 ohne CI-Lauf für den Stand); der CI-Gesamtlauf kam erst mit dem Release-Stand in Phase 34.
- Drei Lücken- oder Zusatzpläne in Phase 31, zwei in Phase 32 und einer in Phase 33 nach den Live-Läufen.

### Key Lessons

- Live-Messung auf mindestens zwei Versionen und mit und ohne Fremd-App gehört in jede Phase, die einen neuen Schreib- oder Lesepfad öffnet; die Befunde aus 32-09, 32-10 und 33-11 kamen nur so ans Licht.
- Befundlinks der Produktdoku zeigen wieder auf .planning/phases/ (42 Verweise auf die Phasen 30 bis 34); die Lehre aus v1.7 (stabiler Ort wie docs/evidence/) ist noch nicht umgesetzt.

### Cost Observations

- Sessions: 18 Kalendertage (28.10. bis 14.11.), 364 Commits, +92.674/-541 Zeilen über 373 Dateien; die Phasenarbeit 30 bis 34 lag zwischen 11.11. und 14.11.
- Notable: nebenläufig erschienen 0.7.0 bis 0.7.3; 0.7.3 kam per Merge von main in den 0.8.0-Zweig.

## Cross-Milestone Trends

| Metrik | v1.0 | v1.1 | v1.2 | v1.3 | v1.4 | v1.5 | v1.6 | v1.7 | v1.8 |
|--------|------|------|------|------|------|------|------|------|------|
| Phasen / Pläne / Tasks | 5 / 50 / 111 | 1 / 11 / 20 | 4 / 28 / 67 | 2 / 10 / 26 | 2 / 6 / 12 | 4 / 32 / n. rek. | 5 / 22 / 59 | 5 / 38 / 92 | 5 / 50 / 163 |
| Kalenderzeit | 7 Tage | 1 Tag | 5 Tage (21.-25.08.) | 2 Tage (25.-26.08.) | 1 Tag (28.08.) | 4 Tage (28.-31.08.) | 9 Tage (18.-26.09.) | 6 Tage (26.09.-01.10.) | 18 Tage (28.10.-14.11.), Phasen 30 bis 34 in 4 Tagen (11.-14.11.) |
| Verifier-Gap-Runden | 1 (Phase 5) | 1 (Phase 6, CLIENT-04) | 0 (alle 4 Phasen passed im ersten Lauf) | 0 (beide Phasen passed im ersten Lauf) | 0 (beide Phasen passed im ersten Lauf) | n. rek. (nachgetragen) | 0 (alle 5 Phasen passed) | 1 (Phase 27, Wanduhr, zwei Lückenpläne; dazu zwei CI-gebundene human_needed bis zum Push) | 2 (Phase 31 Nachtrag nach 4/5, Phase 32 Re-Verifikation nach 32-09 und 32-10; Phase 34 passed nach einem Runbook-Nachtrag auf Owner-Wort) |
| Live-Releases im Milestone | 3 (0.1.0, 0.1.1, 0.1.2) | 0 (0.1.3-Kandidat wartet auf Owner-Freigabe) | 5 (0.1.4 bis 0.1.8, drei davon vorgezogen) | 1 (0.1.9) | 1 (0.1.10) | 1 (0.1.11) | 0 (Exchange-Pfad reist erst mit 0.3.0) | 0 (Filter reist mit 0.4.0; 0.3.1/0.3.2 nebenläufig außerhalb) | 5 (0.8.0 als Ziel; 0.7.0 bis 0.7.3 nebenläufig) |

# Milestones

## v1.6 F13 Token Exchange Identity Mapper (Shipped: 2026-09-26)

**Phases completed:** 5 phases (20 bis 24), 22 plans, 59 tasks
**Umfang:** 217 Commits, 174 Dateien, +40.143/-3.428 Zeilen, 2026-09-18 bis 2026-09-26 (9 Tage)
**Endstand:** 4428 Tests grün auf HEAD nach Rebase auf Community-PR #8; jede Phase goal-backward verifiziert; 24-SECURITY.md mit 38/38 Threats geschlossen (34 mitigate belegt, 4 accept)

**Key accomplishments:**

- Ein zweiter, ab Werk ausgeschalteter Prüfpfad nimmt ein nach RFC 8693 getauschtes Keycloak-Token an und handelt unter dem gemappten Nextcloud-Konto, ohne die Rechtegrenze aufzuweichen; im Aus-Zustand ist das Verhalten byte-gleich zu vorher (Kette hinter unveränderter Transportgrenze, Weiche strukturell über die Tokenform).
- Phase 20: oauth/jwks.py als einzige Schlüsselsatz-Schicht (kid-Abkühlzeit 60 s, Single-Flight, gemessene Grenzen), PyJWT auf 2.14 und cryptography auf 50.0.1 gehoben, Audit-Nachtrag mit fünf GHSA-Kennungen.
- Phase 21: freistehender Keycloak-JWS-Prüfer (Issuer-Vorfilter ohne Abruf, typ=Bearer, 30 s Toleranz, 900 s Lebensdauergrenze), jede Abweichung als eine detailfreie ExchangeRefused.
- Phase 22: eigener Konfigurationsnamensraum NC_MCP_EXCHANGE_* mit fail-closed Startprüfung, vor-authentische Drossel (30 Ablehnungen, dann 429 mit Retry-After), byte-gleiche Fehlerantworten.
- Phase 23: Claim-Mapping mit zwei Profilen und kanonischem Principal, Exchange-Identität mit Pausenschalter, AppAPI-Impersonation fail-closed, Standalone-Bindung unter reservierter EXCHANGE_CLIENT_ID, Enrollment-Dreischritt, Widerrufs-Seite mit gemessenem 200-dann-401.
- Phase 24: actor-Spalte im Audit, gebremste Abweisungs-Kette x:exchange mit Sweep-Anschluss, Trockenlauf occ exchange:check ohne Nextcloud-Aufruf, Zwei-Konten-Negativbeweis gemessen (docs/exchange-evidence.md), Einrichtungsdoku docs/token-exchange.md mit ehrlich markierten F13-Grenzen.

**Bewusst offen (extern getaktet):** die vier F13-Entscheidungen (Audience-Konvention, Konto-Claim, Beispiel-Token/Realm-Export, Exchange-Ziel-Eintrag) samt EXCH-F01/F02 und CLIENT-02; die Rolle von occ oauth2:add-client ist in docs/token-exchange.md als offene F13-Antwort markiert (Owner-Entscheid 24.09., ein Test hält die Markierung). Wiederaufnahme, sobald Denny Mattern/F13 antwortet.

**Akzeptierte Risiken:** T-24-32 (eine von HaRP auflösbare Nextcloud-Anmeldung entscheidet vor dem getauschten Token; gemessen, dokumentiert, keine Rechteausweitung) per Owner-Entscheid 26.09. als R-24-05, Details in milestones/v1.6-phases/24-audit-anschluss-und-nachweis/24-SECURITY.md.

**Hinweis Audit:** Ein separates Milestone-Audit wurde wie bei v1.5 nicht gefahren; die Aussagen stammen aus den fünf Phase-Verifikationen (alle passed), dem Code-Review der Phase 24 (C/W-Findings gefixt), der secure-phase 24 vom Abschlusstag und der vollen Suite auf dem rebasierten Stand.

---

## v1.5 Vorlauf openDesk (Shipped: 2026-08-31, Abschluss nachgetragen 2026-09-18)

**Phases completed:** 4 phases (16 bis 19), 32 plans

**Key accomplishments:**

- Release 0.1.11 mit dem offenen Textrest ausgeliefert (gekürzter Trifecta-Absatz, Autorenkontakt admin@infranode.dev im Manifest).
- Audit-Log als erster Enterprise-Baustein: hash-verkettet, ab Werk aus, mit Bedienung und Textnachzug in den Store-Texten (Phasen 18 und 19); der Enterprise-Abschnitt der READMEs nennt es seitdem als vorhanden statt als geplant.
- Zeitboxierter openDesk-Spike auf OpenProject (Phase 17): Auth-Modell und Token-Exchange-Verhalten der openDesk-Integration vermessen, Fragenliste für den ISV-Call abgelegt.

**Nachtrag 2026-09-18:** Der Milestone stand seit 31.08. in STATE.md auf complete, aber /gsd:complete-milestone war nie gelaufen: kein Eintrag hier, Phasenordner unarchiviert, kein Milestone-Audit. Beim Start von v1.6 nachgeholt (Phasen nach milestones/v1.5-phases/, Requirements und Roadmap als v1.5-Kopien gesichert). Das Milestone-Audit wurde NICHT nachgefahren; die Aussagen oben stammen aus den Phase-Verifikationen und den Releases.

---

## v1.4 Pflege und 0.1.10 (Shipped: 2026-08-28)

**Phases completed:** 2 phases, 6 plans, 12 tasks

**Key accomplishments:**

- Vier Wortstellen in den Store-Dateien korrigiert: zwei französische Reste, eine deutsche Kleinschreibung, eine hängende Changelog-Linkdefinition und ein Kommentar, der einen Ampersand behauptete, den keine der beiden Spendenadressen enthält.
- Die Nachweistabelle von docs/store-submission.md läuft jetzt in der Uhrzeit vorwärts (vier Zeilenbewegungen, sortierter Vergleich: 0 verfälschte Zeilen), der Rückverweis der 18:30Z-Zeile deckt den getaggten Commit 685295d als nachgemessen eine Änderung hinter 22471c1, der Archivstand von Phase 13 trägt einen datierten Nachtrag statt einer Umschreibung, und die Reichweite des Vokabular-Gates gegenüber .planning ist entschieden, begründet und von einem Test gehalten.
- Die Zeichenkette 0.1.10 steht an allen sechs Versionsstellen, und der Changelog-Block 0.1.10 vom 2026-08-28 nennt die Enterprise-Kürzung samt Kontaktwechsel zu admin@infranode.dev als nutzersichtbare Änderung und die Übersetzungs-Korrekturen als Doku-Korrektur, ohne dass ein Tag entstanden ist.
- Alle sechs Gates laufen auf dem 0.1.10-Kandidaten grün, ohne dass ein Grenzwert angehoben wurde, das Store-Archiv trägt vor dem Tag die Statuszeile 0.1.10 und den Changelog-Block 0.1.10, und die eine Byteabweichung der Werkzeugoberfläche hat einen Namen: die Versionszeichenkette im tools/list-Envelope.
- Die acht Commits der Phase lagen auf dem öffentlichen `main`, bevor der Tag `v0.1.10` existierte, der Tag entstand erst nach der wörtlichen Owner-Freigabe von 04:49Z, und der Lauf 33142956284 hat in 1m44s das Multi-Arch-Image nach ghcr.io gepusht und `mcp_connector-0.1.10.tar.gz` mit 46973 Bytes an das GitHub-Release gehängt.
- Die Sortier-Falle.

---

## v1.3 Pflege und 0.1.9 (Shipped: 2026-08-26)

**Phases completed:** 2 phases, 10 plans, 26 tasks

**Key accomplishments:**

- Die Nachrichtenebene von `talk_browse(level="messages")` heißt jetzt `message_truncated`, die Antwortebene behält `truncated` samt `next`, `fetch` meldet die Kappung weiterhin, und die Messung belegt 912 statt 858 Bytes bei unangetasteten Gates.
- Jede Id im Produktionsbaum entsteht jetzt in `ids.py`, und `ids.parse` liest im `url`-Zweig genau die Menge, die `ids.encode_url` bauen kann.
- Die drei Nachzieher aus 11-SECURITY.md sind von Prüfschritten zu Belegen geworden: PROVIDER_KINDS trägt für jeden der sechs Einträge Repository, Datei und Klasse, das Quelltext-Gate zu T-11-29 läuft als Regressionstest mit Gegenprobe, und die Vokabular-Regel reicht jetzt so weit wie ihre Formulierung, mit zwei begründeten Ausnahmen.
- Der letzte Privat-Durchgriff im Produktionsbaum ist eine öffentliche Schnittstelle mit ihrer Sicherheitsbegründung, die Modulgrenze zwischen den Tool-Familien ist ein AST-Gate mit drei Gegenproben statt einer Absprache, und das README-Beispiel für einen unbekannten Suchprovider nennt in allen drei Sprachen eine Id, die es wirklich gibt.
- Die Zeichenkette 0.1.9 steht an allen sechs Stellen, der Changelog-Block darueber nennt `message_truncated` als Formataenderung und `talk-conversations` als Doku-Korrektur, und `git tag --list v0.1.9` ist leer.
- Vier Fassungen desselben Textes nennen Audit-Log, Gruppen-Policies und SSO als geplantes kommerzielles Add-on und sagen in jeder Sprache in einem eigenen Satz, dass heute keiner der drei Bausteine existiert; der Issue-Entwurf liegt als Datei im Repo und ist nicht veroeffentlicht.
- Claude Code 2.1.233 verbindet sich live mit dem 0.1.9-Kandidaten allein über die Adresse seines Metadatendokuments, ohne eine einzige `/register`-Zeile im ganzen Containerleben, und mit abgeschaltetem Schalter geht null statt fünf Sockets nach außen.
- Alle sechs Gates laufen auf dem 0.1.9-Kandidaten gruen, das Werkzeugoberflaechen-Mass steht unveraendert bei 15711 Bytes ueber 21 Werkzeuge gegen 18000, das Store-Paket hat genau einen Top-Level-Ordner und traegt die Statuszeile 0.1.9, und drei datierte Proof-Zeilen belegen die Runbook-Schritte 1 bis 3, ohne dass ein Tag existiert.
- Der Branch war auf GitHub, bevor irgendein Tag existierte, die Owner-Antwort lautete um 18:27Z wörtlich `freigeben`, der Tag `v0.1.9` entstand danach auf demselben Commit `685295d`, den `origin/main` schon trug, und der Release-Lauf `32883904698` ist in jedem Schritt grün: das Multi-Arch-Image liegt unter `ghcr.io/street1983nk/mcp_connector:0.1.9`, und `mcp_connector-0.1.9.tar.gz` mit 47264 Bytes hängt am GitHub-Release.
- Release 0.1.9 ist im Nextcloud App Store: die Signatur ueber genau die veroeffentlichten 47264 Bytes verifizierte mit `Verified OK` gegen das Zertifikat, der POST aus dem Seitenkontext der angemeldeten Store-Sitzung antwortete HTTP 201, der Katalog listet 0.1.9 mit dem Span `>=32.0.0 <35.0.0` neben allen neun frueheren Releases, und die Runbook-Schritte 6 bis 8 tragen sieben datierte Proof-Zeilen.

---

## v1.2 Kuratierte Breite (Shipped: 2026-08-25)

**Phases completed:** 4 phases, 28 plans, 67 tasks

**Key accomplishments:**

- Vier Mail-Wege unter reiner AppAPI-Impersonation gemessen und protokolliert: accounts 200, mailboxes 500, messages 403, OCS-Volltext 404, alle vier mit JSON aus App-Code, damit ist MAIL-04 beantwortet und der Schnitt der Phasen 10 und 11 bestaetigt.
- Tables-Client über beide API-Generationen mit konstruktiv erzwungenem `limit`, plus `ocs.ocs_post` als erste OCS-Schreibnaht des Projekts und `tables.enabled` als App-Gate.
- Ein Browse-Werkzeug über drei Ebenen mit konstruktiv gekapptem Zeilenfenster und ein Zeilen-Anlegen über Spaltentitel, dessen vier Ablehnungen alle vor dem ersten Schreibbyte passieren, inklusive der Eigentümer-Regel, die `onSharePermissions.create` falsch beantwortet.
- Die Tables-Familie ist sichtbar: `tools/list` nennt 18 Werkzeuge zu 12801 Bytes, `level` ist ein Enum aus genau drei Werten, und alle elf eingefrorenen Stellen von den Contract-Tests bis zu den drei Sprachfassungen nennen dieselbe Zahl. Das Budget-Gate steht wieder auf einer Messung, und fuenf neue Nadeln mit Gegenprobe halten fest, dass keine Zeile, keine Spalte und kein Schema geaendert werden kann.
- Die Tables-Familie ist gegen eine echte Nextcloud belegt: eine Zeile mit Umlauten entsteht über Spaltentitel und kommt über `browse(level="rows")` zurück, die echte Zeilen-URL trägt `limit`, Auswahl- und Datumswert gehen ohne eigene Umformung durch (Annahme A2 beantwortet), und ein zweites Konto sieht die Tabelle des ersten nicht, kann bei bekannter Id nichts lesen und nichts schreiben.
- Talk-Client mit v4-Räumen und v1-Chat, der die vier Leseparameter an der gebauten URL festnagelt, 304 als leeres Fenster liest und den Verlaufs-Cursor aus dem Antwort-Header X-Chat-Last-Given nimmt; dazu 201 im Erfolgsraum von parse_ocs und die spreed-Erkennung samt Chat-Höchstlänge der Instanz.
- Sechster Admin-Wert `talk_send` in der ganzen Declarative-Settings-Kette (Formularfeld als Checkbox mit Default an, Overlay-Lesepfad, Manifest-Deklaration ohne `<default>`), plus `config.talk_send_enabled` mit `not in _FALSE_VALUES` statt `in _TRUE_VALUES` und der einen begründeten Schreibstelle auf `os.environ`, über die ein Werkzeug den Schalter pro Aufruf lesen kann.
- `tools/talk.py` mit `browse(level="conversations"|"messages")` und `send`: die Konversationsliste wird sortiert, bevor sie gekappt wird, `truncated` und `next` des Verlaufs kommen allein aus dem Antwort-Header, jeder fremde Text laeuft durch `without_marks` und wird auf eine echte UTF-8-Byte-Grenze gekappt, und der Sendeweg liest den Admin-Schalter als erste ausfuehrbare Zeile, prueft die Rechte am aufgeloesten `permissions`-Feld und laesst ein erfundenes Token nie in einen Nextcloud-Pfad.
- `reg_talk.py` mit `talk_browse` als Literal-Enum-Lesewerkzeug und `talk_send` als sechstem CREATE_ONLY-Schreibweg, dazu der vollstaendige Nachzug in einem Zug: 20 statt 18 an jeder eingefrorenen Stelle, zehn Talk-Nadeln im Destruktiv-Gate mit je einer Gegenprobe plus die positive Behauptung ueber genau drei Pfadformen, ein auf 14312 Bytes gemessenes Token-Budget ohne Anhebung, und Talk in allen drei Store-Beschreibungen.
- Erfolgskriterium 3 ist gemessen und nicht behauptet: `lastReadMessage 23 -> 23`, `unreadMessages 0 -> 0`, `unreadMention False -> False`, `lastCommonReadMessage 23 -> 23` um einen Verlauf-Lesevorgang mit einer Nachricht im Fenster, dazu die Live-Gegenprobe, dass alle vier Leseparameter wirklich ausgehen, ein echter Sendevorgang samt Wiederfinden mit Umlauten, die Absage der schreibgeschuetzten Konversation und ein zweites Konto, das alices Konversation nicht sieht, ihren Verlauf mit dem echten Token nicht erreicht und nichts darin zuruecklaesst.
- Die Wegwerf-Topologie hat einen echten IMAP- und SMTP-Server bekommen, und aus den vier offenen Annahmen der Phase sind vier Zahlen geworden: `specialRole` ist der String `inbox`, `previewText` ist immer gesetzt und bei etwa 250 Zeichen von der App selbst gekappt, die Byte-Kappe des Volltexts steht auf 32 KiB, und zwölf Filterläufe zeigen, wo die Grammatik stillschweigend verwirft.
- Der Mail-Client baut genau vier lesende Pfadformen und kann konstruktionsbedingt keine URL ohne Grenze und ohne Einzelansicht erzeugen, beide Sonderstatus sind dort behandelt, wo sie eine Bedeutung haben, und eine fehlende Mail-App ist jetzt ein Satz mit nächstem Schritt statt der Aufforderung, eine Nachricht in einer App zu suchen, die es nicht gibt.
- `html_text.to_text(html: str) -> str` wandelt fremdes Mail-HTML mit lxml in Absätze statt in eine Wortkette, und `marks.FINAL_TRUNCATION` ist die erste Kappungsmarkierung, die für eine Mail wahr ist und von Anfang an gefiltert wird.
- `mail_browse` geht Konten, Postfächer und Envelopes über einen Aufruf mit drei Ebenen ab, prüft den Filter gegen eine Positivliste, bevor die App ihn stillschweigend verwerfen kann, und benennt jede Kappung als Feld statt als Marker in fremdem Text.
- `fetch("mail:<databaseId>")` liest eine einzelne Mail, wandelt ihren Body unbedingt zu Text, kappt ihn bei 32 KiB mit einer Markierung, die keine Fortsetzung verspricht, und legt Nextclouds Vertrauens-Signale als flache Stringfelder daneben statt als Sätze hinein.
- mail_browse ist als einundzwanzigstes Werkzeug registriert (1377 Bytes, Literal-Enum mit drei Ebenen, ohne Output-Schema), das Budget-Gate steht auf der neuen Messung 15736 Bytes plus 15 Prozent, und neun Mail-Nadeln mit je einer Gegenprobe belegen, dass es keinen Weg zum Senden gibt, obwohl die Mail-App eine Sende-Route direkt neben der Leseroute anbietet.
- Die Exfiltrationskette steht jetzt in der Doku, in drei READMEs und in drei Store-Beschreibungen mit ihrem Namen da, samt Mechanismus, Gegenmassnahme und ehrlichem Rest, und drei Marker im Manifest-Test halten den Satz fest, dass Mail strikt lesend ist.
- Die Aussagen dieser Phase sind jetzt gemessen statt behauptet: ein Nutzer liest an echten Daten sein Konto, sein Postfach und sechs Envelopes, liest drei Mails im Volltext, ohne dass ein einziges `\Seen` gesetzt wird, kommt mit einem zweiten Konto an nichts davon heran, und alle drei neuen Familien verschwinden sauber, gemessen in einem Zustand, in dem ihre App wirklich fehlt.
- Der Codec kennt jetzt `message:<token>:<messageId>` und `table:<tableId>` als siebtes und achtes Kind, und die Übersetzungstabelle macht aus einem Talk- und einem Tabellen-Suchtreffer eine Id, die ein Leser annehmen kann, während View, Mail und ein Talk-Treffer ohne verwertbare Angaben ehrlich `kind=url` bleiben.
- Genau eine Talk-Nachricht ist jetzt adressierbar, ohne eine Nachbarnachricht zu raten: `get_message_context` liest `GET /ocs/v2.php/apps/spreed/api/v1/chat/{token}/{messageId}/context`, die einzige Route in spreed, die die gesuchte Nachricht selbst mitliefert, und 21 Testfälle nageln sie an jeder Stelle fest, an der sie falsch sein könnte.
- Ein Talk- und ein Tabellen-Treffer aus der Suche sind jetzt auflösbar statt `kind=url`: `fetch("message:abcd1234:5103")` liefert den Text genau dieser Nachricht (und lehnt eine fehlende Zielnachricht mit einem Satz ab, statt eine Nachbarnachricht auszugeben), `fetch("table:7")` liefert Titel, Zeilenzahl und die ersten 20 Zeilen. 23 neue Testfälle nageln beide Zweige an den Stellen fest, an denen sie unsichtbar falsch antworten könnten.
- `prepare_context` trägt jetzt ein drittes Bein: einen Talk-Digest aus einem Request mit eigener Zeitdecke und eigenem `degraded`-Eintrag, höchstens drei Konversationen mit Ungelesenem oder Erwähnung, Vorschau bei 200 Bytes ohne Marker; und die Auskunft über die Auflösbarkeit eines Treffers kommt nur noch aus dem Treffer selbst, während eine eigene Konstante verhindert, dass die Reichweite der Auszüge dabei still mitwächst.
- `prepare_context` trägt jetzt ein viertes Bein: Ungelesen-Zähler pro Mailkonto und Inbox, ausschliesslich Zahlen, aus der Postfachliste statt aus dem gemessen falschen `unread`-Feld der Navigation, mit eigener Zeitdecke, auf drei Konten gekappt und mit gleichzeitig statt nacheinander geholten Postfachlisten; und die Werkzeugbeschreibung nennt zum Preis von 33 gemessenen Bytes endlich alle vier Quellen.
- `prepare_context` mit vier Beinen ist gegen die Referenz aus Plan 04-04 gemessen statt geschätzt: Wanduhr 0,65 s bis 1,13 s kurz und 0,85 s bis 1,83 s voll bei leerer `degraded`-Liste, 22 Requests kalt und 19 warm, das Mail-Bein 1+1 auf dieser Instanz, und `fetch("message:...")` bewegt keinen der drei Zähler der Zielkonversation, gemessen über die Konversationsliste und nie über die geprüfte Route. Drei Setzungen sind jetzt Messungen, keine davon musste geändert werden, und der Kommentar, der auf eine verschwundene Datei zeigte, zeigt auf ein Dokument, das existiert.
- Die fünf Werkzeuge des Meilensteins v1.2 sind um 157 Bytes kürzer, ohne dass eine einzige Angabe verloren ging, und das Budget-Gate steht damit zum ersten Mal auf einer Messung, die es senkt statt anhebt: `BUDGET_BYTES` fällt von 18500 auf 18000, gerechnet aus 15612 gemessenen Bytes bei 21 Werkzeugen.
- Das Abnahmeskript liest seine Erwartung ab jetzt aus `client.list_tools()` statt aus einer

zweiten Namensliste, `truncated` bedeutet in einer Mail-Antwort je Ebene genau eine Sache, und
die drei READMEs nennen dieselben sieben Id-Arten.

- Die Fassung steht am Rand des irreversiblen Schritts: vier identische Versionsstrings, ein

Changelog-Block, der jede nutzerrelevante Änderung dieser Phase benennt, die seit Phase 10
fehlende Sektion 0.1.5 nachgetragen, Store-Texte in drei Sprachen, sechs lokal grüne Gates und
kein Tag.

---

## v1.1 Verwaltungs-Clients und Härtungs-Reste (Shipped: 2026-08-20)

**Delivered:** Die letzten Auth-Reste geschlossen und die v1.0-Versprechen ohne fremden Zugang bewiesen: CIMD als DCR-Alternative live mit Claude Code, SSRF-gehärteter Dokumentabruf, RFC-8252-Loopback-Portregel, Ein-Klick-Story auf NC 34.0.3 wörtlich wahr, Conference-Material vorführbar.

**Phases completed:** 1 Phase (6), 11 Pläne, 20 Tasks. Audit passed (7/7 Requirements), Verification 6/6, Security 74/74 Threats closed, Code-Review 0C/3W (alle gefixt).

**Key accomplishments:**

- Client ID Metadata Documents als DCR-Alternative live bewiesen: Claude Code 2.1.233 verbindet sich ohne Registrierung (client_id = https-URL seines Dokuments), die DCR-Kontrollen greifen wortgleich, und mit abgeschaltetem DCR verlässt kein einziges Paket die Instanz (gezählt gegen Positivkontrolle).
- Der Dokumentabruf hat eine belegte SSRF-Grenze: IP-Pinning über sni_hostname (kein zweiter Resolver-Aufruf, Rebinding wirkungslos), is_private-UND-is_global-Konjunktion, 5120-Byte- und 5-Sekunden-Limits, kein Redirect-Follow, Fehler-Cache-Verbot; jede Grenze mit Negativtest, und nach dem Review-Fix passiert der Fetch nur noch am /authorize-Weg.
- Die Loopback-Portfrage ist gemessen beantwortet (drei Läufe, drei Ports) und die RFC-8252-7.3-Regel eingebaut; der CIMD-Schalter ist fünfter Admin-Settings-Wert mit Ende-zu-Ende-Tests (Blocker B-1 des Milestone-Audits, inline geschlossen).
- Cursor-Befund gemessen statt vermutet: die Teilregistrierung wirkt live (201 mit den zwei zulässigen Adressen), Cursor scheitert danach an seiner eigenen cursor://-Adresse an /authorize; Owner-Entscheid BL-14 "sichtbar machen plus Doku" (E5-Seite nennt den App-Passwort-Ausweg, D-35 unangetastet).
- Die Ein-Klick-Story ist auf NC 34.0.3 wörtlich wahr: die Store-UI zeigt "Deploy and enable" und "Remove", gemessen auf der auf 34.0.3.2 gehobenen Instanz; Doku und Store-Text (EN/DE/FR) sagen das Gemessene.
- Conference-Material steht: Demo-Runbook mit sechs Schritten, einmal komplett durchgefahren (82,2 s gemessen gegen 82 s behauptet), Per-User-Schalter und Widerruf erstmals in beiden Richtungen belegt; Lightning-Talk-Entwurf (8 Folien, 280/300 s), nichts eingereicht, niemand kontaktiert.

**Deferred at close:** Phase 7 (CLIENT-01..03: MUCGPT/F13/BaerGPT-Live-Verprobung) per Owner-Entscheid 2026-08-20 in die Future Requirements verschoben , extern getaktet (it@M-Antwort, Owner-Kontakte), Protokoll in docs/client-setup.md bleibt einlösbar. Tech-Debt-Posten siehe milestones/v1.1-MILESTONE-AUDIT.md Frontmatter.

---

## v1.0 MVP im Store (Shipped: 2026-08-20)

**Phases completed:** 5 phases, 50 plans, 111 tasks

**Key accomplishments:**

- uv-Toolchain mit auditierten Pins (mcp 2.0.0, kein direkter httpx2-Pin), Docker-freie pytest-Basis mit 7 gruenen Projekt-Invarianten, definiert roter files_read-Contract-Test und Byte-basiertes tools/list-Budget-Gate in CI.
- Ende-zu-Ende-Strecke steht: nc-mcp antwortet per stdio auf initialize, files_read liest Textdateien ueber PROPFIND plus GET-Range aus der eigenen Nextcloud, und alle Guards (Traversal, Binaer, 2-MiB-Deckel, 401-ohne-Retry, XXE) sind mit 95 gruenen Tests belegt.
- 1. [Rule 1 - Bug] OC_PASS erreichte den Container nicht
- Ein Endpoint fuer beide MCP-Aeren: entry_http.py als uvicorn-App mit Host-Allowlist und /health, drei exklusive Credential-Modi (stdio, Basic-Passthrough, Static Bearer mit compare_digest) und ein Matrix-Test, der SDK 1.29 und SDK 2.x gegen dieselbe URL fuehrt und den Serverneustart ueberlebt.
- files_search (WebDAV basicsearch mit lxml-gebautem Body und explizitem d:limit) und files_list (PROPFIND Depth 1 ohne den Ordner selbst), beide mit zustandslosen base64url-Cursor-Handles, die prozessuebergreifend weiterlesen.
- OCS-Client mit Pflichtheadern und getrennten Parsern, App-Erkennung mit 60-Sekunden-Cache und die drei Notes-Tools ueber den Unified-Search-Provider, inklusive live bewiesener Graceful Degradation und AUTH-01-Nachweis ueber HTTP
- CalDAV-Client mit serverseitiger Recurrence-Expansion plus calendar_list_events und calendar_create_event, abgesichert durch die Vier-Faelle-Zeitmatrix und einen Live-Beweis ueber die DST-Grenze Ende Oktober
- contacts_search als rein lesende Vertikale: Adressbuch-Discovery unter addressbooks/users/, serverseitig gefilterter addressbook-query mit lxml und vCard-Parsing per vobject, inklusive Filter gegen die generierten Adressbuecher.
- Deck-REST-v1.0-Client mit Pflichtheadern plus deck_browse (ein Tool, Enum-Ebenen, ein Request fuer alle Karten eines Boards) und create-only deck_create_card mit vorab erklaerten Rechtegrenzen
- Cloudweite Suche ueber alle installierten Nextcloud-Suchprovider: Provider-Liste zur Laufzeit, paralleler Fan-out mit hartem Timeout pro Provider, normalisierte Treffer mit stabilen IDs und explizit benannten Degradierungen.
- `search` und `fetch` mit exakt dem OpenAI-Schema: `search` delegiert an die Unified Search und liefert Zitat-faehige URLs, `fetch` loest praefixierte IDs auf Datei, Notiz, Karte und Termin auf und beantwortet nicht aufloesbare Treffer ehrlich statt falsch.
- App-ID mcp_connector mit vier frisch geprueften Verfuegbarkeitsbelegen eingefroren, englisches README mit Permission-Tabelle fuer alle 15 v1-Tools, und das oeffentliche AGPL-Repo street1983nk/nextcloud-mcp-connector steht mit gepushtem main.
- Einreichfertiger Ein-Zeilen-Fix im Fork street1983nk/context_agent: stateless_http wird per MCP_STATELESS_HTTP umschaltbar und ist per Default sessionfaehig, DCO-signiert, mit fertigem PR-Text und Reproduktionsanleitung.
- Das Sicherheitsversprechen ist jetzt ein Gate statt einer Behauptung: AST-Grep gegen destruktive Aufrufe, Confused-Deputy-Pruefung ueber alle 15 Input-Schemas, Zwei-Konten-Negativbeweis, ein auf 12500 Bytes scharf gestelltes Token-Budget und ein Abnahmelauf, der alle 15 Tools ueber echtes stdio gegen die Docker-Nextcloud aufruft.
- Der komplette AppAPI-Lebenszyklus selbst implementiert: drei Header per compare_digest zu einer Nutzer-Id, /heartbeat ungeschuetzt, /init mit OCS-Fortschritts-Push, /enabled mit leerem error-Feld, plus ein eigener Entry-Point, der Phase 1 nachweislich unberuehrt laesst.
- Die Nutzeridentitaet aus AUTHORIZATION-APP-API erreicht jetzt jede der 20 Nextcloud-Aufrufstellen: Credentials kennt seinen Modus und liefert per auth() entweder httpx.BasicAuth oder AppApiAuth, resolve_credentials bekam genau einen Zweig, die Clients genau eine Zeile pro Aufruf, und Tool-Code wurde nicht angefasst.
- Ein 79-MB-ExApp-Image fuer amd64 und arm64, das als uid 10001 laeuft, frpc per SHA256 verifiziert mitbringt und seinen Gesundheitszustand in beiden Transportvarianten ehrlich meldet, dazu ein Manifest, das genau zwei Routen oeffnet und die drei Lifecycle-Pfade nachweislich nicht erreichbar macht.
- Eine zweite, vollstaendig getrennte Compose-Topologie aus Reverse-Proxy, Nextcloud, HaRP und Loopback-Registry, in der die App mit drei Kommandos als ExApp installiert wird: `occ app_api:app:list` meldet `mcp_connector (MCP Connector): 0.1.0 [enabled]`, Deploy und Init stehen beide auf 100, der MCP-Endpunkt wird mit dem App-Passwort eines Nutzers bedient und ohne Auth mit 403 abgewiesen.
- The discovery spike is a go: an unauthenticated client reaches the RFC 9728 metadata of this ExApp from the outside over both the HaRP path and the PHP proxy path, the WWW-Authenticate resource_metadata pointer passes through both proxies unchanged, the canonical root path is 404 and belongs to Nextcloud, and a real MCP session with the SDK client streams 15 tools over HaRP end to end.
- The DAV spike is decided as case A: every one of the six Nextcloud API families (WebDAV, CalDAV, CardDAV, OCS, Notes, Deck) runs under AppAPI impersonation against a real HaRP topology, the identity is proven server side for alice and for bob, a wrong APP_SECRET is refused, bob cannot reach alices file even by the exact path (404, never 200), and a valid client set Authorization header cannot override the impersonated identity. There is no provider split and no app password fallback; assumption A1 is confirmed and AUTH-05 is met.
- The permission promise is proven over the whole chain a real user runs: an MCP client authenticates as bob with an ordinary app password, HaRP resolves the identity, the ExApp impersonates bob against Nextcloud, and bob finds nothing of alice's across files, notes and unified search, while alice finds her own file and note in the same run; the ExApp operating mode is documented beside stdio and HTTP, the Nextcloud AIO smoke is handed to phase 5 with a named reason, and the four Success Criteria of the phase are accepted with checkable evidence.
- The OAuth discovery path is production code: /mcp answers an anonymous caller with a 401 that points at an RFC 9728 document, that document names one authorization server, and its RFC 8414 metadata is served at both reachable well-known paths, all from configuration and all with no-store.
- A SQLite store with the full OAuth schema, AES-GCM at rest with the row id as aad, a data key held in Nextcloud's ExApp configuration instead of beside the database, and a refresh rotation that produces exactly one winner under two parallel requests.
- Every HTML page of the OAuth phase now comes out of one function that sets a per response CSP nonce, four security headers and no-store, escapes every attacker controlled value at the single point where it writes it, and turns one table into the seven error pages that name a next step without naming a protocol value.
- A user without an OAuth capable client now opens one page, signs in on Nextcloud's own pages including the second factor, and reads one dedicated app password exactly once: no input field anywhere on the route, one poll per page load, twenty minutes of life per sign in, and nothing of the credential in any file or log.
- An OAuth client can now register itself, ask for authorization and take its user through Nextcloud's own sign in to a consent screen that names it: the administrator can switch registration off, restrict it to a list, and every one of those refusals is a page that says what to do next instead of a JSON error a browser shows raw.
- The durchstich of the phase stands: a user approves on a page of this app, the client trades its code for an opaque token that is bound to this one server, and a tool call runs under the Nextcloud identity of the person who consented, without a single Nextcloud round trip in the token path.
- A stolen refresh token now costs the attacker the whole connection, a retransmitted one costs the user nothing, "revoked" means revoked before the request returns, and every misuse case of D-40 is a green test instead of a sentence in a plan.
- Claude.ai and ChatGPT both connect to a public Nextcloud with nothing but the resource URL, which closes AUTH-04, and getting there found one real defect of ours, corrected one assumption of the research, corrected one reading of our own measurement, and turned the deferred BL-04 question into a different question than the one that was written down.
- Wer sein Nextcloud-Konto pausiert, wird beim nächsten MCP-Aufruf abgewiesen, auf beiden Anschlussarten, mit einem 403 `access_disabled` ohne Challenge, und die Sperre kostet keinen einzigen zusätzlichen Nextcloud-Roundtrip, weil sie ein lokaler SQLite-Read an genau einer Transportgrenze ist.
- Ein Aufruf bündelt Treffer und Termine parallel, kappt vorhersagbar und sagt bei jedem Ausfall und jeder Kappung Name und Grund, und der injizierte Anweisungssatz einer fremden Datei kommt zeichengenau als Datenfeld an, ohne einen einzigen Schlüssel der Antwort zu verschieben.
- Ein Nutzer sieht seine verbundenen Assistenten auf einer Seite, trennt einen davon über genau den Widerrufs-Pfad, den auch `/revoke` benutzt, und legt dort den Schalter um: der unmittelbar nächste Tool-Aufruf desselben Tokens ist R1, ohne Challenge und ohne dass ein anderes Konto etwas merkt.
- Der Nutzer findet den MCP Connector jetzt dort, wo Nextcloud seine eigenen Schalter zeigt: ein Link-only-Eintrag unter Einstellungen, Sicherheit, der auf die Connections-Seite führt, registriert bei jedem Aktivieren und unfähig, die Installation zu brechen. Auf der echten Topologie ist die ganze Kette nachgemessen: Wegweiser sichtbar ausgeliefert, Schalter umgelegt und der nächste Tool-Aufruf 403 `access_disabled`, SC 5 unverändert bei einem Nextcloud-Roundtrip je MCP-Aufruf, und `prepare_context` antwortet in 0,84 s kurz und 0,99 s voll.
- Eine Admin-Declarative-Settings-Form mit vier echten Feldern plus ein Mehrschluessel-Lesepfad, der die gespeicherten Werte als Overlay in `NC_MCP_`-Schreibweise zurueckgibt und bei jedem Ausfall auf die Deploy-Env zurueckfaellt.
- Der Per-User-Schalter wird jetzt an allen drei Punkten durchgesetzt, an denen eine Verbindung entsteht, und keine dieser Ablehnungen hinterlaesst ein benutzbares Nextcloud-App-Passwort.
- `ensure_readonly_share` im Bootstrap.
- Die in Nextcloud gesetzten Werte wirken jetzt: `main` legt sie einmal beim Start als Overlay auf die Umgebung und gibt sie an jede Route-Fabrik, und eine Installation ohne oeffentliche Adresse stirbt nicht mehr beim Start, sondern erklaert sich auf der Connections-Seite.
- `tests/integration/test_credential_flood.py`
- `occ mcp_connector:purge --force` gibt jedes Nextcloud-App-Passwort dieser Instanz zurueck, leert alle sieben Tabellen und loescht den Datenschluessel, in genau dieser Reihenfolge, ueber einen Handler, der im Manifest keine Route hat und ohne die Pflichtoption nichts tut.
- Open WebUI 0.11.0 ist von der Vermutung zum gelaufenen Fall geworden, inklusive der Ablehnung, die nach unserem Fehler aussieht und keiner ist, und MUCGPT ist mit dem einen funktionierenden Weg, seinem Preis und seiner unverprobten Stelle beschrieben.
- Erfolgskriterium 2 ist in beiden Richtungen belegt: nach dem Entfernen ueber die Oberflaeche antworten zwei Nextcloud-Konten weiter mit 200 auf App-Passwoerter dieser App, waehrend Volume, Zeilen, Datenschluessel, Container und Registrierung unveraendert daliegen; nach `occ mcp_connector:purge --force` und `occ app_api:app:unregister --rm-data` antwortet jedes dieser Passwoerter mit 401 und keine der elf Gegenproben findet noch etwas.
- Die Frage, ob ein Nutzer die App fuer sich abschalten kann, ist jetzt dort beantwortet, wo er sie stellt: kanonisch in `docs/faq.md`, kurz in drei READMEs und im Wortlaut in allen drei Store-Beschreibungen, die dafuer so umgeschrieben wurden, dass die Filterliste der Instanz-Ansicht nichts davon wegwirft.
- Die im Store gelistete Fassung ist jetzt die, die diese Phase gebaut hat: 0.1.1 installiert sich per Klick ohne eine einzige Umgebungsvariable und bleibt oben (0 restarts, wo 0.1.0 mit Exit 2 crash-loopte), und ein Zugriffstoken, das die Vorversion ausgestellt hat, bediente nach dem Update weiter 16 Werkzeuge und einen echten Tool-Aufruf.
- Ein `http://`-Wert auf einem oeffentlichen Host kommt nicht mehr durch die Validierung, und selbst wenn er aus der Deploy-Umgebung stammt, beendet er den Prozess nicht mehr: die App verwirft die Adresse, laeuft mit dem Default weiter und sagt im Log und auf der Connections-Seite, wo sie zu korrigieren ist.
- Der Lesekanal traegt. Der 401 haengt allein daran, dass die App im Moment des Lesens in

Nextcloud noch nicht als aktiviert gilt.

- Zweig N
- 1. [Rule 3 - blockierende Bedingung] Die App wurde einmal ohne die Deploy-Variable neu registriert
- 1. [Rule 2 - Fehlende kritische Funktionalitaet] `grep -Eqz` statt `grep -Eq` in `require_url_shape`
- Gewaehlte Option: `option-b` (Mit dokumentierter Luecke abnehmen)

---

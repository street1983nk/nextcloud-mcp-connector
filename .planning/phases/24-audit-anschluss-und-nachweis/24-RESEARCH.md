# Phase 24: Audit-Anschluss und Nachweis - Research

**Researched:** 2026-09-23
**Domain:** Anschluss eines fremden, nach RFC 8693 getauschten Tokens an eine bestehende hash-verkettete Audit-Kette, plus Betreiber-Werkzeuge (Trockenlauf, Messnachweis, Einrichtungsdoku) für einen Pfad, dessen Gegenstelle (F13) nicht live erreichbar ist
**Confidence:** HIGH für den Code-Stand dieses Repos (jede Aussage an Datei und Zeile gelesen), HIGH für die Transportgrenzen (selbst gemessen gegen die laufende NC-35-HaRP-Topologie), MEDIUM für die reale Größe eines echten F13-Keycloak-Tokens (synthetisch gemessen, nicht gegen eine F13-Realm), LOW für alles, was an F13s vier offenen Antworten hängt

## Summary

Diese Phase baut keine neue Mechanik, sie schließt vier Lücken an vier bestehende Maschinen an: die Audit-Kette aus Phase 18/19, das occ-Kommandomuster aus `exapp/occ.py` plus `exapp/audit_verify.py`, das Nachweis-Muster aus `docs/spike-dav.md` und die Doku-Kette unter `docs/`. Der Code für den Exchange-Pfad selbst ist fertig: seit Plan 23-02 trägt eine Exchange-Identität bereits `client_id = EXCHANGE_CLIENT_ID` und `client_name = azp`, und beide landen über `deps.resolve_caller` schon heute in jeder Audit-Zeile. Ein über Exchange geführter Werkzeugaufruf steht also bereits in der Kette. Was fehlt, ist genau das, was die Erfolgskriterien zusätzlich verlangen: ein **eigenes** Feld für die handelnde Partei, eine Zeile für den **abgewiesenen** Versuch (heute strukturell unsichtbar), ein Trockenlauf-Kommando und zwei Nachweisdokumente.

Die eine harte technische Grenze dieser Phase ist die kanonische Feldliste der Audit-Kette. `audit/store.py:282-303` sagt wörtlich "decided once and unchangeable afterwards", und `_first_finding` (Zeile 849) rechnet jede Zeile über `row[: len(CANONICAL_FIELDS)]` nach. Eine neue gehashte Spalte würde jede bereits geschriebene Zeile jeder bestehenden Installation beim nächsten `occ mcp_connector:audit:verify` als `modified` melden, und es gibt in diesem Modul kein Migrationswerkzeug außer `CREATE TABLE IF NOT EXISTS`. Der Ausweg ist keine neue Spalte, sondern die eine bereits vorhandene, hash-geschützte und heute bei Aufrufzeilen leere Spalte: `actor`. Sie bedeutet im Schema bereits "wer hat gehandelt" (D-16), sie steht in `CANONICAL_FIELDS`, sie wird von `_entry_of_row` schon gelesen, und sie ist in der Ausgabe von `occ mcp_connector:audit:read` heute schlicht nicht abgebildet. Das macht Kriterium 1 zu einer Ausgabe- und Verdrahtungsänderung statt zu einer Schemamigration.

Die zweite harte Grenze ist der Ort, an dem eine Abweisung sichtbar wird. Der Recorder wird von `exapp/middleware.py:157-175` bewusst erst nach bestandener Prüfung hinterlegt ("nothing about a caller that was turned away can reach the log through this path"), und `oauth/exchange.py:147-162` sagt ebenso bewusst, dass die Ablehnungsgründe auf DEBUG bleiben und AUDIT-07 in Phase 24 der richtige Ort ist. Phase 24 ist damit die Phase, die zwei dokumentierte Versprechen eng und begründet aufmacht. Dabei lauert die gefährlichste Falle der ganzen Phase: die Instanz-Kette wird vom Sweep **nie** angefasst (`chain <> ?` in `_EXPIRED_ROWS`, `_OLDEST_ROWS`, `_DROP_EXPIRED`, `_DROP_OLDEST`, Zeilen 365-375). Abweisungszeilen in der Instanz-Kette wären von einem Fremden bestellbare, nie verfallende Zeilen und würden genau den Zustand herstellen, den `OVER_BOUND_SENTENCE` beschreibt.

**Primary recommendation:** Die handelnde Partei geht in die bestehende Spalte `actor` (keine Schemaänderung, keine gebrochene Kette), die Abweisung bekommt eine eigene, vom Sweep erfasste Kette mit eigenem `kind` und einer Schreibbremse, das Trockenlauf-Kommando entsteht als reine Funktion plus einer occ-Route nach dem Muster von `exapp/audit_verify.py`, und beide Nachweise werden gegen die bereits laufende lokale NC-35-HaRP-Topologie gemessen, nicht argumentiert.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Handelnde Partei in der Aufrufzeile | Audit-Kern (`audit/record.py`, `audit/store.py`) | Auth-Schicht (`oauth/exchange_accounts.py` liefert den Wert) | Der Wert existiert schon in der Identität; die Kette entscheidet, in welche Spalte er fällt |
| Sichtbarkeit einer Abweisung | Auth-Schicht (`oauth/chain.py` weiß, dass und warum abgewiesen wurde) | Audit-Kern (schreibt die Zeile) | Nur die Kette kennt den Grund; die Transportgrenze kennt nur "nein" |
| Ausgabe für den Betreiber | ExApp-Shell (`exapp/audit_read.py`, `exapp/audit_verify.py`, `exapp/occ.py`) | - | Die Shell ist die einzige Schicht mit Admin-Kontext |
| Trockenlauf-Prüfung | Auth-Schicht (reine Funktion in `oauth/`) | ExApp-Shell (occ-Route und Registrierung) | Die Regel gehört zum Prüfer, die Konsole zur Shell |
| Zwei-Konten-Nachweis | Testumgebung (Docker-Topologie) plus `docs/` | Nextcloud (setzt die Rechtegrenze durch) | Die Grenze wird in Nextcloud gemessen, nicht in unserem Code behauptet |
| Einrichtungsdoku | `docs/` | - | Reine Dokumentation, kein Laufzeitcode |

## Project Constraints (aus CLAUDE.md und Projektregeln)

Aus `./CLAUDE.md` (GSD-Block, Abschnitt Project/Constraints) und den globalen Regeln:

- **Sprache:** Code, Docstrings, README und alles unter `docs/` auf **Englisch** (internationales Nextcloud-Publikum). Projektkommunikation und Planungsdokumente auf Deutsch. Diese RESEARCH.md ist Deutsch, die von ihr beschriebenen Artefakte unter `docs/` sind Englisch.
- **Keine Em-Dashes**, echte Umlaute in deutschen Texten, keine Emojis.
- **Solo-Betrieb:** Wartungsaufwand pro Feature zählt. Kein zweites Subsystem, wo eine Spalte reicht.
- **Security:** Der MCP darf nie mehr sehen als der angemeldete Nutzer. Keine destruktiven Writes.
- **Python-Qualitätsgates (globale Regel, 14.08.):** `ruff check .` + `ruff format --check .` (Vollregelsatz, `line-length = 100`, `target-version = py313`, `exclude = [".planning"]`), `pyright` mit `typeCheckingMode = "standard"` über `src`, `scripts`, `tests`, `vulture` mit `vulture_whitelist.py`. Neuer Code lokal grün **vor** dem Commit.
- **Tests:** pytest, `testpaths = ["tests"]`, Standardlauf ohne Docker und ohne Serverprozess; die schwereren Schichten sind über Marker opt-in. Stand 8814dc8: 4162 Tests grün.
- **GSD-Workflow:** Keine direkten Repo-Änderungen außerhalb eines GSD-Kommandos.
- **Toolchain:** `uv`, Python 3.13. Das System-Python dieser Maschine ist defekt; jeder Python-Aufruf läuft über `./.venv/Scripts/python.exe` oder `uv run`.

`.planning/config.json` setzt `workflow.nyquist_validation = false`. Der Abschnitt "Validation Architecture" entfällt deshalb bewusst.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUDIT-07 | Ein über Exchange handelnder Werkzeugaufruf steht in der hash-verketteten Kette samt handelnder Partei (azp), unter den bestehenden Inhaltsverboten; abgewiesene Versuche sind für den Betreiber sichtbar, ohne Token-Inhalte zu protokollieren | Abschnitte "Bestandsaufnahme", "Entscheidung D1", "Entscheidung D2", Pitfalls 1 bis 5 |
| EXCH-06 | Trockenlauf-Kommando prüft ein vorgelegtes Token gegen die aktive Konfiguration, benennt das Ergebnis je Prüfschritt, ohne dass das Token dabei irgendetwas darf | Abschnitt "Entscheidung D3", Pitfalls 6 bis 8, Code Example 3 |
| EXCH-07 | Zwei-Konten-Negativbeweis als Messdatei neben den bestehenden Client-Nachweisen | Abschnitt "Entscheidung D4", "Environment Availability", Pitfall 9 |
| EXCH-08 | Einrichtungsdoku in `docs/` von der Keycloak-Seite bis zum ersten Werkzeugaufruf, Audience-Konvention, `occ oauth2:add-client`-Playbook, ehrliche Grenzbeschreibung | Abschnitte "Doku-Bausteine", "Header-Größe", "F13s vier offene Antworten" |
| BL-21 / IN-04 | 429-Lauf gegen die gebaute ExApp-Anwendung | Abschnitt "BL-21", Code Example 4 |
| BL-21 / IN-05 | JWKS-Abruf-Grenze nach Phase 23 nachmessen, Ergebnis in den Docstring von `jwks.forget` | Abschnitt "BL-21", "Die Rechnung, die nachzumessen ist" |

## Bestandsaufnahme: was schon da ist, mit Datei und Zeile

Alle folgenden Angaben sind durch direktes Lesen des Quelltextes belegt. `[VERIFIED: eigener Quelltext]`

### Die Audit-Kette

| Sache | Ort | Was das für Phase 24 heißt |
|-------|-----|------------------------------|
| Schema, eine Tabelle, zwei Kettenarten | `audit/store.py:237-280` (`SCHEMA`) | `CREATE TABLE IF NOT EXISTS` ist die gesamte Migration. Es gibt kein `ALTER TABLE` und keine Schemaversion |
| Kanonische Feldliste | `audit/store.py:285-303` (`CANONICAL_FIELDS`) | 17 Felder, "decided once and unchangeable afterwards". Jede Ergänzung bricht bestehende Zeilen |
| Digest einer Zeile | `audit/store.py:630-643` (`_append_row`), `521-529` (`_canonical`) | `sha256(json(list(felder)) + prev_hash)`, JSON-Liste in Feldreihenfolge |
| Kettenprüfung | `audit/store.py:826-863` (`_first_finding`) | `row[: len(CANONICAL_FIELDS)]` - eine 18. Spalte lässt jede Altzeile als `modified` auffallen |
| Kettennamen | `audit/store.py:171-199` | `i:instance` und `u:<nc_user>`; `USER_CHAIN_PREFIX`, `user_chain()`, `_account_of()` |
| Zeilenarten | `audit/store.py:202-212` | `call`, `tombstone`, `switch`. Ein neuer `kind` ändert **keinen** Hash und braucht keine Migration |
| Ergebnisklassen | `audit/store.py:218-220` | `ok`, `rejected`, `failed` |
| Sweep | `audit/store.py:342-375` | **Wichtig:** `chain <> ?` mit `CHAIN_INSTANCE` in allen vier Anweisungen. Die Instanz-Kette verfällt nie und wird nie getrimmt |
| Kontocheck D-12 | `audit/store.py:941-966` (`silent_users`), `968-1018` (`drop_user_chain`) | `_SILENT_CHAINS` nimmt jede Kette außer der Instanz-Kette, `_account_of` schneidet nur `u:` ab. Eine dritte Kettenart würde hier als "Konto" auftauchen |
| Inhaltsverbote | `audit/record.py:8-13` (Moduldocstring), `audit/allowlist.py` | Kein Parameterwert, kein Ergebnisstück, kein `exc.message`, keine IP, kein User-Agent. Nur gesetzte Parameternamen geschnitten mit der Allowlist |
| Säuberung fremder Werte | `audit/text.py` (`printable`), angewandt in `store.py:532-549` **nur auf `client_name`** | `actor` geht heute ungereinigt in die Zeile. Relevant für D1 |
| Gate gegen Wertlecks | `tests/contract/test_audit_surface.py` | Muster für ein Quelltext- bzw. Oberflächen-Gate |
| Quelltext-Gate mit AST | `tests/contract/test_no_destructive_calls.py:1-45, 311-320` | Das Muster für ein "Claim-Leak-Gate": Kommentare und Docstrings vor dem Zählen entfernen, jeder Fund nennt Datei und Zeile |

### Der Weg einer Zeile

`server`-Tool-Dekorator -> `audit/record.py:208` (`note`) -> `_recorder_of(ctx)` (Zeile 129, liest `request.state`) -> `deps.resolve_caller(ctx)` (`deps.py:148-191`) -> `Entry(...)` -> `AuditStore.append`.

`deps.resolve_caller` füllt aus einer `OAuthIdentity` genau vier Felder: `nc_user = identity.principal`, `client_id`, `auth_id`, `client_name`. **Für ein Exchange-Token stehen dort seit Plan 23-02 schon**: `client_id = "urn:mcp-connector:token-exchange"` (`oauth/exchange_accounts.py:34`) und `client_name = acting_party(claims)`, also der gesäuberte `azp` (`oauth/exchange_accounts.py:68-88`, Kappung bei 64 Zeichen über `MAX_ACTING_PARTY_LENGTH`).

Das ist der wichtigste einzelne Befund der Bestandsaufnahme: **Erfolgskriterium 1 ist zur Hälfte bereits erfüllt.** Der Docstring von `EXCHANGE_CLIENT_ID` sagt sogar ausdrücklich, der reservierte Bezeichner stehe dort, damit ein Leser einen Exchange-Aufruf erkennt, "without the audit chain growing a new field". Kriterium 1 verlangt aber "als eigenes Feld". Das ist der Punkt, an dem Phase 24 eine bewusste Entscheidung gegen eine Formulierung aus Phase 23 treffen muss (siehe D1).

### Der Weg einer Abweisung

| Schritt | Ort | Heutiges Verhalten |
|---------|-----|--------------------|
| Regelverstoß im Prüfer | `oauth/exchange.py:139-162` | `_refused(reason)` schreibt **eine DEBUG-Zeile mit fester Phrase**, wirft `ExchangeRefused()` ohne jedes Detail |
| Kette fängt ab | `oauth/chain.py:524-527` | `except ExchangeRefused: return None` - stumm, kein Log |
| Unerwartete Ausnahme | `oauth/chain.py:528-535` | Eine ERROR-Zeile mit `type(exc).__name__`, sonst nichts |
| Identität nicht auflösbar | `oauth/chain.py:555-576` | `return None` bei fehlender Quelle oder fehlgeschlagenem Mapping, ERROR nur bei Ausnahme |
| Transportgrenze | `exapp/middleware.py:144-147` | 401 mit `WWW-Authenticate`, nichts wird hinterlegt |
| Recorder | `exapp/middleware.py:157-175` | Wird **nur** für Anfragen hinterlegt, die alle drei Prüfungen bestanden haben |

Der Docstring von `_refused` nennt AUDIT-07 in Phase 24 wörtlich als den Ort, an dem das gelöst gehört, und begründet die DEBUG-Stufe damit, dass der Pfad vor-authentisch ist und ein Fremder sonst entscheiden könnte, wie viele WARNING-Zeilen geschrieben werden. Diese Begründung gilt für eine Audit-Zeile genauso und ist die Wurzel von Pitfall 2.

### Das occ-Kommandomuster

| Sache | Ort |
|-------|-----|
| Registrierung, drei Kommandos, ein POST je Kommando | `exapp/occ.py:174-281` (`command_schemes`), `284-336` (`register_occ_commands`) |
| Erlaubte Optionsmodi | nur `required`, `optional`, `none`; **niemals** `array`, niemals `arguments` mit `default`-Lücke (`exapp/occ.py:218-235`, gemessen gegen app_api v34.0.3) |
| Handler-Route wird aus der Pfadkonstante abgeleitet | `exapp/occ.py:93, 112, 132` |
| Handler-Muster mit Guard, JSON-Schalter, Textantwort | `exapp/audit_verify.py:147-186` (Route), `309-323` (`_guard`), `325-378` (`--json` lesen), `430-436` (`_text`) |
| Warum immer 200 | `exapp/audit_verify.py:25-33`: `ExAppOccService::buildCommand` verwirft den Body bei jedem Status außer 200. Exit-Code ist immer 0, ein Skript liest `--json` |
| Warum keine Route im Manifest | `exapp/audit_verify.py:13-23`: der interne AppAPI-Pfad braucht keine Deklaration, eine Deklaration würde die Antwort ins Internet stellen |
| Body-Grenze | `exapp/audit_verify.py:97-103`: 4096 Byte, angekündigte Länge zuerst, maximal 10 Ziffern |

### Die Nachweis-Muster

| Muster | Datei | Was daran übernommen gehört |
|--------|-------|-------------------------------|
| Zwei-Konten-Grenze, gemessen | `docs/spike-dav.md:95-130` | Kopf mit Datum, NC-Version, AppAPI-Version, Deploy-Daemon und Scope; eine Matrix; Rohausgabe; **Server-seitige Logzeilen** als der eigentliche Beweis; Abschnitt "Consequence" |
| Versionsfenster, gemessen | `docs/nc35-evidence.md:1-30` | Kopf mit Datum, Subject, Status; woher die Instanz kommt; was genau lief |
| Der offene Anker für EXCH-08 | `docs/standalone-oauth.md:62-66` | Steht schon im ausgelieferten Dokument: "How the token exchange path is configured end to end, on this side and at the identity provider, gets its own setup document". Phase 24 löst dieses Versprechen ein |

### Drosselung und Schlüsselsatz

| Sache | Ort | Wert |
|-------|-----|------|
| Pfadklasse des Exchange-Pfads | `oauth/throttle.py:150-155` | `CLASS_EXCHANGE = "exchange"` |
| Zählgrenze je Quelle | `oauth/throttle.py:183-194` | `EXCHANGE_LIMIT = 30` je Fenster |
| Klassendeckel | `oauth/throttle.py:178-181` | `PATH_CEILING = 200` |
| Fenster | `oauth/throttle.py:196-198` | `WINDOW = 300` Sekunden |
| Was gezählt wird | `oauth/throttle.py:34-51` | **Abweisungen** (Status >= 400). Ein Erfolg zahlt genau eine Abweisung zurück |
| Enrollment-Klassen | `oauth/throttle.py:157-165` | `CLASS_EXCHANGE_ENROLL`, `CLASS_EXCHANGE_ENROLL_START` gegen `FLOW_LIMIT = 20` |
| Schlüsselsatz-Cache | `oauth/jwks.py:70-90` | `JWKS_CACHE_SECONDS = 300`, `JWKS_KID_COOLDOWN_SECONDS = 60`, `JWKS_FAILURE_RETRY_SECONDS = 10`, `MAX_KEYS = 20`, `MAX_RESPONSE_BYTES = 256 KiB` |
| `forget()` | `oauth/jwks.py` (Methode `forget`) | Leert `keys`, setzt `fetched_at = -inf`; die beiden vor-authentischen Bremsen bleiben stehen |
| Wer `forget` auslöst | `oauth/chain.py:578-598` (`invalidate`), aufgerufen von `provider.end_connection` | Ein Widerruf leert Store-Cache und Schlüsselsatz zusammen |
| Tokengröße, hartes Limit | `oauth/exchange.py:95-104` | `MAX_TOKEN_BYTES = 8192`, geprüft **vor** dem ersten base64-Schritt |

## Die vier Entscheidungen dieser Phase

Das sind die Stellen, an denen der Planer eine Form festlegen muss. Jede trägt eine Empfehlung mit Begründung, und jede benennt, was der Alternative fehlt.

### D1: Wie die handelnde Partei "ein eigenes Feld" wird

**Die Beschränkung.** Eine 18. gehashte Spalte ist ausgeschlossen. Beleg: `CANONICAL_FIELDS` ist die Reihenfolge, in der gehasht wird (`audit/store.py:282-284`), `_first_finding` rechnet jede gelesene Zeile über `row[: len(CANONICAL_FIELDS)]` nach (Zeile 849), und eine per `ALTER TABLE` ergänzte Spalte stünde bei jeder Altzeile auf `NULL`, also als zusätzliches `null` in der JSON-Liste. Ergebnis: **jede** Zeile jeder bestehenden Installation meldet sich beim nächsten `occ mcp_connector:audit:verify` als `modified`. Außerdem gibt es in diesem Modul kein Migrationswerkzeug; `SCHEMA` besteht aus `CREATE TABLE IF NOT EXISTS` und zwei Indizes. `[VERIFIED: eigener Quelltext, audit/store.py:237-303, 826-863]`

| Option | Kosten | Urteil |
|--------|--------|--------|
| **A: bestehende Spalte `actor` nutzen** | Keine Schemaänderung, kein Hash-Bruch. `actor` bedeutet im Schema bereits "wer hat gehandelt" (Kommentar Zeile 250, D-16), steht in `CANONICAL_FIELDS` an Position 5, wird von `_entry_of_row` schon gelesen und ist bei jeder `call`-Zeile heute `None`. Kosten: `audit/record.py:237-253` füllt das Feld, `exapp/audit_read.py:335-390` und die Textausgabe zeigen es, `Caller` (`deps.py`) bekommt ein fünftes Feld | **Empfohlen** |
| B: neue gehashte Spalte | Migration plus gebrochene Ketten auf jeder bestehenden Installation | Ausgeschlossen |
| C: neue ungehashte Spalte | Das Feld, das die Delegation belegen soll, wäre das einzige unbelegte Feld der Zeile. Widerspricht dem Zweck | Ausgeschlossen |
| D: es bei `client_name` belassen | Kein Code, aber Kriterium 1 sagt "als eigenes Feld", und ein Leser kann `client_name` eines registrierten Clients nicht von einem `azp` unterscheiden, ohne `client_id` mitzulesen | Nicht ausreichend |

**Zwei Feinheiten zu Option A, die in den Plan gehören.**

1. `actor` trägt heute genau einen Wert, `ACTOR_UNKNOWN = "unknown"` (`audit/store.py:169`), und zwar nur in `switch`- und `tombstone`-Zeilen. Ein `azp` in `actor` bei `call`-Zeilen kollidiert damit nicht, verlangt aber einen Satz im Schemakommentar und im Docstring, der beide Bedeutungen benennt, sonst liest die nächste Person das Feld falsch.
2. `_row_values` (`audit/store.py:552-576`) schickt **nur** `client_name` durch `_clean_client_name`. `actor` ginge ungereinigt in die Zeile. Der Wert kommt aus einer fremden Realm. `acting_party` filtert zwar bereits mit `character.isprintable()`, das ist aber **nicht** dieselbe Regel wie `audit/text.printable` (die zusätzlich Whitespace-Läufe zusammenzieht und die Lehre aus R-18-06 trägt). Empfehlung: `actor` in `_row_values` durch dieselbe Regel schicken wie `client_name`, und ein Test hält die beiden Wege gegeneinander.

### D2: Wo eine abgewiesene Exchange-Prüfung sichtbar wird

**Die Beschränkung.** Die Instanz-Kette wird vom Sweep nie angefasst. Beleg: `_EXPIRED_ROWS`, `_OLDEST_ROWS`, `_DROP_EXPIRED` und `_DROP_OLDEST` tragen alle `chain <> ?` mit `CHAIN_INSTANCE` (`audit/store.py:365-375`), und `_SWEEPABLE_TOTAL` zählt genau die Zeilen **außerhalb** der Instanz-Kette (Zeile 340). Abweisungszeilen dort wären von einem Fremden bestellbare, nie verfallende Zeilen; `exapp/audit_verify.py:131-139` beschreibt den Endzustand bereits als `OVER_BOUND_SENTENCE`: über der Größengrenze, nichts mehr zu fegen. `[VERIFIED: eigener Quelltext]`

**Empfohlene Form:**

- **Eigene Kettenart**, zum Beispiel Präfix `x:` mit einem festen Namen (`x:exchange`). Sie fällt damit unter `chain <> CHAIN_INSTANCE` und wird vom Verfallsfenster **und** von der Größengrenze erfasst, ihre Lücken werden von `_write_markers` mit Grabsteinen erklärt, und `verify_chains` läuft über sie wie über jede andere.
- **Eine Anpassung, die dazu zwingend gehört:** `_SILENT_CHAINS` (`audit/store.py:397-399`) liefert jede Kette außer der Instanz-Kette, und `silent_users` schickt das Ergebnis durch `_account_of`, das nur `u:` abschneidet. Eine `x:`-Kette würde nach 30 stillen Tagen als nicht existierendes Konto gemeldet und von `drop_user_chain` gelöscht (harmlos im Ergebnis, weil ein Grabstein bleibt, aber falsch in der Bedeutung). Der saubere Fix ist ein Präfixfilter in `_SILENT_CHAINS` (`chain LIKE 'u:%'`), plus ein Test, der ihn hält.
- **Neuer `kind`**, etwa `refusal`. Ein neuer `kind`-Wert ist ein Wert in einer bestehenden Spalte und ändert **keinen** Hash und kein Schema.
- **Der Grund als fester Bezeichner in `reason`.** `_known_reason` (`audit/record.py:167-176`) lässt nur Werte aus `errors.REASONS` durch und macht aus allem anderen `REASON_UNSPECIFIED`. `REASONS` ist ein `frozenset` in `errors.py:25-33` und wird nirgends gehasht; eine Ergänzung ist unkritisch. Die festen Phrasen existieren bereits als Argumente von `_refused(...)` in `oauth/exchange.py` und `oauth/jwks.py`.
- **`ExchangeRefused` muss den Bezeichner tragen.** Heute ist die Ausnahme bewusst detailfrei (`oauth/exchange.py:139-144`). Der Bezeichner darf die Ausnahme verlassen, **nie** die HTTP-Antwort: der 401 bleibt wortgleich, der 429 bleibt wortgleich (`test_the_429_of_the_exchange_path_names_no_check_that_failed` hält das bereits). Diese Unterscheidung gehört wörtlich in den Docstring, sonst wird beim nächsten Lesen daraus ein Orakel.
- **Der Schreibweg.** Ein "Ablehnungsschreiber" wird in `build_chain(...)` hereingereicht, so wie `accounts` in Phase 23, und ist `None`, solange das Audit-Log aus ist (D-14, Werkszustand). `exapp/middleware.py` bleibt unangetastet, genau wie in Phase 22 und 23.
- **Die Schreibbremse.** Siehe Pitfall 2. Ohne sie ist der Weg eine von einem Fremden bestellbare Schreiblast und ein Weg, die Historie echter Konten aus der Größengrenze zu drücken.

**Was in der Zeile stehen darf und was nicht.** Erlaubt: Kette, `kind`, Zeitpunkt, `outcome = rejected`, `reason` (fester Bezeichner), optional `client_id = EXCHANGE_CLIENT_ID`. Verboten: der `azp` einer **ungeprüften** Abweisung (ein Token, dessen Signatur nicht hält, hat keinen belastbaren `azp`; ihn zu schreiben wäre genau der Claim-Leak, den Kriterium 2 ausschließt), der Issuer, die Audience, `sub`, jeder Tokenteil, jede `kid`. Das ist der Inhalt des geforderten Gates.

### D3: Die Form des Trockenlauf-Kommandos

**Empfohlene Form:** eine reine Funktion plus eine occ-Route, exakt das Paar aus `exapp/audit_verify.py` und `exapp/occ.py`.

- **Die Regel wohnt bei den Regeln.** Ein neues Modul, etwa `oauth/exchange_dryrun.py`, das eine Liste benannter Schritte mit je einem benannten Ergebnis zurückgibt, ohne Route, ohne Umgebung, ohne Netz außer dem Schlüsselsatz-Abruf. Genau die Bauform, die `oauth/exchange.py` für sich selbst beansprucht ("reads nothing from the environment").
- **Die Schritte** ergeben sich aus dem Prüfer und sollten ihm exakt folgen, damit "der Trockenlauf sagt grün, der Betrieb sagt rot" strukturell ausgeschlossen ist: Form (zwei Punkte), Größe (`MAX_TOKEN_BYTES`), Header lesbar, `alg` erlaubt, `kid` im Schlüsselsatz, Signatur, `iss` (Vorfilter), Pflicht-Claims vollständig, `typ` ist `Bearer` und nicht `ID`, `exp`/`iat`/`nbf` mit Toleranz, maximale Lebensdauer und maximales Alter (900 s), Audience exakt, `azp` auf der Allowlist, Mapping-Profil ergibt einen Principal.
- **Der letzte Schritt ist ausdrücklich nicht ausgeführt.** Die Kontoexistenz läuft über `audit/accounts.existing_users` bzw. `AppApiAccounts` und ist ein Nextcloud-Aufruf. Kriterium 3 verbietet ihn. Der Schritt muss trotzdem **benannt** in der Antwort stehen, mit dem Ergebnis "nicht geprüft, weil das ein Nextcloud-Aufruf wäre". Ein weggelassener Schritt wäre ein stiller grüner Haken.
- **Keine Sitzung.** Der Trockenlauf ruft `resolve_identity` nicht auf, legt keine Autorisierung an, berührt den OAuth-Store nicht und hinterlässt keine Zeile in der Audit-Kette.
- **Eigener Schlüsselsatz.** Der Trockenlauf sollte seinen **eigenen** `KeySet` bauen und nicht den des laufenden Prüfers benutzen. Sonst verbraucht ein Admin-Trockenlauf mit unbekanntem `kid` die 60-Sekunden-Abkühlzeit des heißen Pfads oder fällt in die 10-Sekunden-Fehlerkarenz und meldet "Provider nicht erreichbar", obwohl nur die Karenz lief. Preis: ein ausgehender JWKS-Abruf je Trockenlauf. Der gehört als Satz in die Antwort.
- **Das Token als Optionswert, mit benannter Grenze.** Siehe Pitfall 6: eine Datei hilft nicht (Nextcloud-Host und ExApp-Container haben verschiedene Dateisysteme), stdin wird von AppAPI nicht weitergereicht. Also Optionswert, mit dokumentierter Konsequenz.
- **Standalone-Betrieb.** occ existiert nur im ExApp-Modus, der Exchange-Pfad existiert aber auch im Standalone-Betrieb (Weg B aus D-v1.6-01). Offene Frage an den Planer: eine zweite Oberfläche (Konsolen-Einstieg neben `nc-mcp-oauth`) oder eine ausdrückliche Grenze in der Doku ("der Trockenlauf gehört zum ExApp-Betrieb"). Empfehlung: die reine Funktion so bauen, dass eine zweite Oberfläche später nur noch eine Datei ist, und die Entscheidung im Plan ausdrücklich treffen statt sie aus dem Scope fallen zu lassen.

### D4: Die Form des Zwei-Konten-Nachweises

**Empfohlene Form:** eine eigene Datei unter `docs/`, gebaut wie `docs/spike-dav.md`, mit einem Kopf (Datum, Nextcloud-Version, AppAPI-Version, Deploy-Daemon, Scope), einer Matrix, der Rohausgabe der Läufe und einer Zeile aus dem Nextcloud-seitigen Impersonation-Log je Lauf. Namensvorschlag im Stil der bestehenden Dateien: `docs/exchange-evidence.md`. Verlinkung: `docs/token-exchange.md` (EXCH-08) verweist darauf, und `docs/standalone-oauth.md:62-66` bekommt den Verweis, den es bereits ankündigt.

**Die vier Messungen, die die Datei tragen muss:**

1. Token für Konto A, gemappt, liest eine eigene Datei: 200/207.
2. Dasselbe Token, bekannter Pfad einer Datei von Konto B: 404, nie 200. Das ist die Zeile, auf die es ankommt.
3. Die Gegenrichtung mit einem Token für Konto B: symmetrisch.
4. Der Confused-Deputy-Fall: ein zusätzlicher, gültiger `Authorization: Basic`-Header von Konto A neben dem Exchange-Token von Konto B ändert nichts an der handelnden Identität. `docs/spike-dav.md:105-117` hat genau diesen Fall für den AppAPI-Pfad; für den Exchange-Pfad ist er neu und wertvoll, weil hier zwei Bearer-Wege nebeneinander liegen.

**Zusätzlich, weil es die Phase billig mitnimmt:** dieselben Läufe erzeugen die Audit-Zeilen für Kriterium 1. Ein gemischter Lauf (ein Aufruf mit eigenem Token, einer über Exchange, beide unter demselben Principal) landet in **derselben** Nutzerkette `u:<principal>`, weil MAP-01 den kanonischen Principal liefert; danach `occ mcp_connector:audit:verify` und `occ mcp_connector:audit:read --json` als Rohausgabe in die Messdatei. Das ist der Nachweis für "über einen Lauf mit gemischten Aufrufen bleibt die Kette prüfbar", gemessen statt behauptet.

## Die Header-Größe: gemessen, nicht geschätzt

Die Roadmap führt das als offenen Recherchepunkt ("ungemessen"). Es ist jetzt gemessen, und zwar in zwei Hälften: die Transportgrenzen der Kette lokal gegen die laufende NC-35-HaRP-Topologie, die Tokengröße synthetisch gegen selbst gebaute Keycloak-Claim-Sätze. Was nur mit F13-Zugriff messbar wäre, steht am Ende des Abschnitts.

### Was unsere Strecke wirklich durchlässt

Gemessen am 2026-09-23 gegen die laufenden Container `nc35-caddy` (caddy:2), `nc35-harp` (`ghcr.io/nextcloud/nextcloud-appapi-harp:release`), `nc35-nc` (`nextcloud:35.0.0-apache-local`) und die ExApp in `nc_app_mcp_connector`, per `POST /exapps/mcp_connector/mcp` mit einem `Authorization: Bearer`-Wert wachsender Länge. `[VERIFIED: eigene Messung 2026-09-23]`

| Weg | Letzte durchgelassene Tokenlänge | Erste abgewiesene | Antwort | Wer antwortet |
|-----|-----------------------------------|-------------------|---------|---------------|
| Client -> Caddy -> HaRP -> ExApp | 14 912 B | 14 915 B | 431, ab ca. 16 000 B dann 414 | HaRP (HAProxy), durch Caddy hindurchgereicht (`Via: 1.1 Caddy`, kein `Server`-Header, `Content-length` klein geschrieben) |
| Direkt auf HaRP (`appapi-harp:8780`) | 15 058 B | 15 061 B | 431 | HaRP (HAProxy) |

Der Kopf der Anfrage betrug am Umschlagpunkt über Caddy 15 107 Byte (durch) gegen 15 110 Byte (abgewiesen). Das passt zu HAProxys Regel "der ganze Anfragekopf muss in einen Puffer passen": `tune.bufsize` steht im HaRP-Template nicht, also gilt die Voreinstellung 16384, abzüglich `tune.maxrewrite` und interner HTX-Reserve. `[VERIFIED: gh api repos/nextcloud/HaRP/contents/haproxy.cfg.template - keine `tune.*`-Zeile im Template]` `[CITED: discourse.haproxy.org zu bufsize minus maxrewrite]`

Die nächste Grenze dahinter ist unsere eigene: `uvicorn 0.52.3` läuft ohne `h11_max_incomplete_event_size`, also mit `h11.DEFAULT_MAX_INCOMPLETE_EVENT_SIZE = 16384` Byte für den gesamten Anfragekopf. `[VERIFIED: .venv, uvicorn/protocols/http/h11_impl.py:60-62, h11/_connection.py:69]` Sie ist heute unerreichbar, weil HaRP früher abweist, würde aber sofort bindend, wenn ein Betreiber HaRPs Puffer hochsetzt.

**Der Befund, den die Doku braucht:** unsere Strecke reißt kein Limit. Zwischen der realistischen Tokengröße und der Transportgrenze liegt der Faktor 3 bis 15. Was **vor** der Transportgrenze greift, ist unsere eigene Regel `MAX_TOKEN_BYTES = 8192` - und das ist die bessere Reihenfolge, weil daraus ein sauberer 401 mit einer DEBUG-Zeile wird statt eines 431 aus einem Proxy, den niemand im Applikationslog sieht.

### Die zweite, bisher unbenannte Grenze: HaRP reicht das Token an Nextcloud weiter

`haproxy_agent.py` (Funktion `nc_get_user`) baut aus **allen** Anfrage-Headern außer `host` und `content-length` die Header seines Aufrufs an `GET /index.php/apps/app_api/harp/user-info` und schickt sie an Nextcloud. `[VERIFIED: gh api repos/nextcloud/HaRP/contents/haproxy_agent.py, Zeilen 77 und 788-803]` Damit läuft das fremde Keycloak-Token bei **jeder** Anfrage durch Nextclouds PHP-Strecke, also durch Apache.

Gemessen, gleiche Topologie, Apache-Log von `nc35-nc`:

| Tokenlänge | `user-info`-Antwort |
|-------------|---------------------|
| 100, 4 000, 7 900, 8 050 B | 200 |
| 8 200, 9 000 B | **400** |

Das ist Apaches `LimitRequestFieldSize` mit der Voreinstellung 8190 Byte pro Header-Zeile: `Authorization: Bearer ` sind 22 Byte, also schlägt es zwischen Tokenlänge 8 050 und 8 200 um. `[VERIFIED: eigene Messung 2026-09-23]` `[CITED: httpd.apache.org/docs/2.4/mod/core.html, Default `LimitRequestFieldSize 8190`]` nginx hat mit `large_client_header_buffers 4 8k` praktisch dieselbe Grenze. `[CITED: nginx.org/en/docs/http/ngx_http_core_module.html]`

Drei Folgerungen, alle für die Doku und für die Planung relevant:

1. **Unsere Grenze und die Grenze der Umgebung liegen fast übereinander.** `MAX_TOKEN_BYTES = 8192` und Apaches 8190 sind praktisch derselbe Punkt. Ein Token, das unsere Regel reißt, reißt fast immer auch die Umgebung. Das ist ein gutes Zeichen, aber es war bisher Zufall und gehört als gemessener Satz in den Docstring von `MAX_TOKEN_BYTES`.
2. **Ein zu großes Token verstummt nicht, es kostet.** HaRPs Agent bekommt 400, `resp.status // 100 == 4` führt zu `return None`, also kein aufgelöster Nextcloud-Nutzer. Für den Exchange-Pfad ist das folgenlos (die Identität steckt im Bearer), aber jede solche Anfrage kostet eine fehlgeschlagene Nextcloud-Runde und erzeugt eine 400-Zeile im Nextcloud-Log. Betreiber, die das sehen, brauchen die Erklärung in `docs/token-exchange.md`.
3. **Das Token ist nicht auf die ExApp beschränkt.** Es wird bei jeder Anfrage an Nextclouds PHP gereicht. Das gehört in den Abschnitt "was dieser Pfad nicht leistet", weil es eine Eigenschaft der Umgebung ist und keine Entscheidung dieser App.

### Wie groß ein Keycloak-Token wirklich ist

Synthetisch gemessen mit PyJWT und einem RS256/2048-Schluessel gegen realistisch geformte Keycloak-Claim-Sätze (`iss`, `aud`, `sub` im `f:<uuid>:<name>`-Format, `typ`, `azp`, `sid`, `acr`, `scope`, `preferred_username`, Namensfelder, `realm_access`, `resource_access`, `groups`). `[VERIFIED: eigene Messung 2026-09-23, .venv/PyJWT]`

| Form | JWS | `Authorization`-Zeile |
|------|-----|------------------------|
| Minimal (nur Pflicht-Claims plus `scope`, `preferred_username`) | 920 B | 942 B |
| Typisch (Standard-Scopes plus `realm_access`, `resource_access`) | 1 477 B | 1 499 B |
| Fett (25 Fachrollen plus 25 Gruppen) | 4 132 B | 4 154 B |
| Schwelle zu `MAX_TOKEN_BYTES` | ca. 68 Rollen **und** 68 Gruppen | 8 196 B |

Der Signaturanteil ist bei RS256/2048 mit 342 Zeichen konstant; die Größe wird vollständig vom Claim-Satz bestimmt. Eine Behördeninstanz mit einem großzügigen LDAP-Gruppen-Mapper kann die 68/68-Marke erreichen. Das ist der Satz, den `docs/token-exchange.md` an die F13-Seite richten muss: **den Gruppen- und Rollen-Mapper des Ziel-Clients schlank halten**, weil der Connector, Apache und nginx alle bei etwa 8 KB stehen.

### Was nur mit F13-Zugriff messbar ist

- Die **tatsächliche** Größe eines echten F13-Tokens, also welche Client-Scopes der Ziel-Client wirklich trägt. Die Tabelle oben sagt, was wo bricht, nicht, wo F13 liegt.
- Ob F13s Realm `preferred_username` in getauschten Tokens führt (F13-Antwort 2).
- Ob die 400er aus dem `user-info`-Pfad in der Praxis HaRPs Brute-Force-Liste füttern. `record_failure_unless_trusted` existiert im Agenten; ob dieser Pfad sie erreicht, ist **nicht** gemessen und sollte nicht behauptet werden. Die Phase-22-Recherche hat für einen unbekannten Bearer das Gegenteil gemessen ("no HaRP blacklist entry"), das deckt diesen Fall aber nicht zwingend mit ab. `[ASSUMED]`

## BL-21: die beiden eingeordneten Befunde der Phase 22

### IN-04: der 429-Lauf gegen die gebaute ExApp-Anwendung

Die zwei gemessenen Läufe stehen in `tests/unit/test_oauth_exchange_chain.py:1175-1220` und laufen gegen `entry_oauth.build_oauth_app`. Der Zwilling gegen `entry_exapp.build_exapp_app` ist mechanisch, alle Helfer stehen bereit:

| Helfer | Ort |
|--------|-----|
| `bearer_call(client, token)` | `tests/unit/test_exapp_entry.py:2117-2123` (POST `/mcp` mit `appapi_headers(user="")` plus Bearer) |
| `EXCHANGE_ENV` | `tests/unit/test_exapp_entry.py:2440-2447` |
| `entry_exapp.build_exapp_app(env)` | überall in derselben Datei |
| `throttle.EXCHANGE_LIMIT` | `tests/unit/test_exapp_entry.py:55` importiert `throttle` bereits |

Zu beweisen ist dasselbe wie im OAuth-Zwilling: `EXCHANGE_LIMIT` mal 401 auf `Bearer a.b.c`, dann 429 mit positivem `Retry-After`, `keys.call_count == 0`, und daneben ein Aufruf mit punktlosem Token, der unverändert 401 bekommt. Der letzte Teil ist der eigentliche Wert: er beweist, dass die bewusste Ausnahme der MCP-Route für eigene Tokens auch im ExApp-Aufbau steht.

Ein Detail, das den OAuth-Zwilling vom ExApp-Zwilling unterscheidet und in den Plan gehört: im ExApp-Aufbau läuft vor der Bearer-Prüfung `require_appapi`. `bearer_call` setzt deshalb `appapi_headers(user="")`, also den App-Kontext. Ohne diesen Header wäre der 401 der Handshake-401 und nicht der Bearer-401, und der Test würde grün sein, ohne den Drosselpfad je erreicht zu haben.

### IN-05: die Rechnung, die nachzumessen ist

Die Bestandteile, alle belegt:

- `forget()` leert den Cache und setzt `fetched_at = -inf`; die beiden vor-authentischen Bremsen (Miss-Abkühlzeit, Fehlerkarenz) bleiben absichtlich stehen. Der nächste Ablauf-getriebene Abruf ist also **nicht** gebremst.
- `chain.invalidate()` ruft `forget()` und wird über `provider.end_connection` bei jedem Widerruf ausgelöst (`oauth/chain.py:578-598`).
- `CLASS_EXCHANGE` zählt **Abweisungen**, nicht Anfragen (`oauth/throttle.py:34-51`). Ein Erfolg zahlt sogar eine gezählte Abweisung zurück.
- **Das ist die Änderung durch Phase 23:** vorher hatte kein Exchange-Token eine Identität, jede Anfrage endete als Abweisung und wurde gezählt; `EXCHANGE_LIMIT`/`PATH_CEILING` deckelten damit die Zahl der Zyklen. Seit Phase 23 antwortet ein gültiges Exchange-Token mit 200, wird nicht gezählt und zahlt zusätzlich eine frühere Abweisung zurück.
- Der Widerrufsweg selbst ist gedrosselt, aber über andere Klassen: `CLASS_EXCHANGE_ENROLL`/`CLASS_EXCHANGE_ENROLL_START` gegen `FLOW_LIMIT = 20` (`oauth/throttle.py:157-165`), `CLASS_CONNECTIONS` je Konto ohne Klassendeckel (`oauth/throttle.py:65-71`), und er verlangt eine bewiesene Browser-Identität.

Was nachzumessen ist, ist damit klar umrissen: **wie viele ausgehende JWKS-Abrufe kann ein Gegenüber je Fenster von 300 Sekunden bestellen, wenn es ein gültiges Exchange-Token besitzt?** Die zwei Hebel sind (a) Widerruf plus ein Aufruf, weil der Widerruf die Abkühlzeit nicht anfasst und der folgende Abruf ein Ablauf-Abruf ist, und (b) unbekanntes `kid`, gebremst durch 60 Sekunden, also höchstens 5 je Fenster. Die Messung gehört nach dem Muster der bestehenden `respx`-Tests gebaut (`keys.call_count` als Zähler) und das **Ergebnis** in den Docstring von `jwks.forget`, mit der dann gültigen Rechnung und mit dem Datum. Ein Satz ohne Zahl wäre die dritte Fassung derselben ungenauen Aussage.

Nebenbefund für den Plan: wer den Widerrufsweg als Hebel misst, misst zugleich, ob `CLASS_CONNECTIONS` (je Konto, kein Klassendeckel, zählt nur Abweisungen) einen erfolgreichen Widerruf überhaupt bremst. Nach Lesen von `throttle.py` bremst er ihn **nicht**. Das ist kein Fehler (ein erfolgreicher Widerruf ist eine gewünschte Handlung), aber es ist der Grund, warum die Zahl in `forget` eine gemessene und keine hergeleitete sein muss.

## Standard Stack

**Keine neue Laufzeitabhängigkeit.** Diese Phase schreibt in eine bestehende SQLite-Tabelle, registriert ein weiteres occ-Kommando über einen bestehenden Weg, baut zwei Markdown-Dateien und einen Test. Jede benötigte Bibliothek ist bereits direkte Abhängigkeit.

### Core (bereits vorhanden, nur genutzt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyjwt[crypto] | >=2.14,<3 (Lock 2.14.0) | Signatur- und Claim-Prüfung im Trockenlauf | Seit DEP-01 gesetzt, einzige Prüfbibliothek des Projekts |
| httpx | >=0.28,<0.29 (0.28.1) | JWKS-Abruf des Trockenlaufs | Projektregel: eigener Code spricht httpx |
| starlette | (über fastapi/mcp) | Route des occ-Handlers | Muster von `exapp/audit_verify.py` |
| sqlite3 (stdlib) | Python 3.13 | Audit-Kette | Der Store ist gebaut |
| pytest, respx, starlette TestClient | vorhanden | Messungen und Gates | Bestehendes Testgerüst |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Spalte `actor` wiederverwenden | Neue gehashte Spalte plus Migrationswerkzeug | Bricht jede bestehende Kette; ein Migrationswerkzeug für eine Kette, deren Zweck Unveränderlichkeit ist, ist ein Widerspruch in sich |
| Eigene Kette `x:` für Abweisungen | Instanz-Kette | Die Instanz-Kette verfällt nie; fremdbestellte Zeilen dort sind dauerhaft |
| occ-Kommando für den Trockenlauf | Neue HTTP-Route mit Admin-Auth | AppAPI liefert die Admin-Grenze bereits; eine deklarierte Route stünde im Internet (`exapp/audit_verify.py:13-23`) |
| Eigener `KeySet` im Trockenlauf | Den des laufenden Prüfers | Ein Admin-Trockenlauf würde die Bremsen des heißen Pfads verbrauchen |

**Installation:** keine. Es ist kein `pyproject.toml`-Eintrag zu ändern.

## Package Legitimacy Audit

Diese Phase installiert **kein** externes Paket. Es gibt nichts zu prüfen, und damit auch keine Zeile in dieser Tabelle.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| - | - | - | - | - | - | keine neuen Pakete in dieser Phase |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

Sollte der Plan wider Erwarten ein Paket aufnehmen (etwa für das Claim-Leak-Gate), gilt die Projektregel unverändert: erst gegen das richtige Register prüfen, dann aufnehmen. Für AST-Gates ist nichts nötig, `ast` und `tokenize` sind Standardbibliothek und das bestehende Gate nutzt genau die.

## Architecture Patterns

### System Architecture Diagram

```
                    ein Werkzeugaufruf ueber Exchange
                                 |
   Client ---> [Reverse Proxy] ---> [HaRP / HAProxy] ---> [ExApp: uvicorn]
                    ~1 MB              ~15,1 KB Kopf          16384 B Kopf
                       |                    |
                       |                    +--(alle Header)--> [Nextcloud PHP/Apache]
                       |                                         8190 B je Header-Zeile
                       v
                 RequireAppApi / RequireOAuthBearer  (middleware.py, unveraendert)
                       |
                 +-----+------------------------------+
                 |                                    |
        punktloses Token                      JWS mit zwei Punkten
                 |                                    |
        StoreTokenVerifier                   ExchangeTokenChecker
        (unveraendert)                        |            |
                 |                     bestanden        abgewiesen
                 |                            |            |
                 |                     resolve_identity    +--> [NEU D2]
                 |                      mapping ->              Ablehnungsschreiber
                 |                      ExchangeAccounts        (nur wenn Log an,
                 |                            |                  mit Schreibbremse)
                 |                        Identitaet                  |
                 +------------+---------------+                       |
                              v                                       v
                    Recorder in request.state                 Kette x:exchange
                              |                               kind=refusal
                        Werkzeugaufruf                        outcome=rejected
                              |                               reason=<fester Bezeichner>
                        audit.record.note()                          |
                              |                                      |
                    Kette u:<principal>                              |
                    kind=call                                        |
                    actor=<azp>  [NEU D1]                            |
                    client_id=urn:mcp-connector:token-exchange       |
                              |                                      |
                              +-------------+------------------------+
                                            v
                                  audit/store.py, eine Datei
                                  sha256(kanonische Felder + prev_hash)
                                            |
                        +-------------------+-------------------+
                        v                                       v
             occ mcp_connector:audit:verify          occ mcp_connector:audit:read
                        |                                       |
                        +---------------+-----------------------+
                                        v
                            occ mcp_connector:exchange:check  [NEU D3]
                            (dieselbe Shell-Schicht, eigener KeySet,
                             kein Nextcloud-Aufruf, keine Sitzung)
```

### Pattern 1: Eine neue Fähigkeit wird hereingereicht, nicht importiert

**Was:** Der Ablehnungsschreiber kommt als Parameter in `build_chain`, so wie `accounts` in Phase 23 und `store_provider` in `audit_verify_routes`.
**Wann:** Immer, wenn eine untere Schicht etwas tun soll, das nur der Einstiegspunkt konfigurieren darf.
**Beispiel:**

```python
# Quelle: src/mcp_connector/oauth/chain.py:601-636 (bestehend, das Muster)
def build_chain(
    store_verifier: StoreBranch,
    *,
    env: Mapping[str, str] | None = None,
    config: ExchangeConfig | None = None,
    accounts: ExchangeAccounts | None = None,
) -> StoreBranch:
    loaded = config if config is not None else load_exchange_config(env)
    if loaded is None:
        return store_verifier          # der Aus-Zustand gibt das Objekt selbst zurueck
    return ChainedVerifier(store=store_verifier, checker=..., config=loaded, accounts=accounts)
```

Der Aus-Zustand gibt `store_verifier` **selbst** zurück, nicht einen Wrapper mit gleichem Verhalten. Ein Test kann `is` sagen. Derselbe Anspruch gilt für den Ablehnungsschreiber: ohne eingeschaltetes Audit-Log hängt nichts.

### Pattern 2: Ein occ-Kommando ist zwei Dateien und eine abgeleitete Konstante

**Was:** Ein Handlermodul mit Pfadkonstante und Route, und ein Eintrag in `command_schemes()`, dessen `execute_handler` aus der Pfadkonstante abgeleitet wird.
**Beispiel:**

```python
# Quelle: src/mcp_connector/exapp/occ.py:111-112 (bestehend)
OCC_AUDIT_HANDLER = AUDIT_VERIFY_PATH.removeprefix("/")
# "A registration whose handler name drifts away from the route is a command
#  that exists, is documented, and answers 404 on the one day somebody needs it."
```

**Die drei Regeln, die dabei nicht verhandelbar sind** (`exapp/occ.py:12-18, 218-235`, gemessen gegen app_api v34.0.3):

1. Ein `mode` außerhalb von `required`, `optional`, `none` bricht **die occ-Kommandozeile der ganzen Instanz**, nicht nur das eigene Kommando.
2. `arguments` bleibt leer; AppAPI liest `$argument['default']` bedingungslos und schreibt sonst eine PHP-Warnung bei jedem occ-Aufruf.
3. Jede Werte-Option trägt `default`.

### Pattern 3: Die Antwort eines occ-Handlers ist immer 200

```python
# Quelle: src/mcp_connector/exapp/audit_verify.py:430-436 (bestehend)
def _text(body: str, status_code: int = 200) -> Response:
    """... a status other than 200 makes AppAPI drop this body, and the body is
    the whole answer."""
    return Response(body, status_code=status_code, media_type="text/plain", headers=NO_STORE)
```

Für den Trockenlauf heißt das: ein Token, das an Schritt 4 scheitert, ist kein Fehlerstatus, es ist eine 200 mit einem benannten Ergebnis je Schritt. Und weil der Exit-Code immer 0 ist, braucht die JSON-Form einen Schlüssel, den ein Skript beobachtet (`"passed": false`), genau wie `audit_verify` seinen `"broken"`-Schlüssel hat.

### Anti-Patterns to Avoid

- **Eine 18. Spalte in `CANONICAL_FIELDS`.** Bricht jede bestehende Kette. Siehe D1.
- **Abweisungszeilen in `i:instance`.** Die Kette verfällt nie. Siehe D2 und Pitfall 2.
- **Den `azp` einer ungeprüften Abweisung schreiben.** Ein Token ohne gehaltene Signatur hat keinen belastbaren `azp`. Genau der Claim-Leak, den Kriterium 2 ausschließt.
- **Den Ablehnungsgrund in die HTTP-Antwort bringen.** Ein 401, der sagt, welche Regel fiel, ist ein Orakel. `test_the_429_of_the_exchange_path_names_no_check_that_failed` hält den einen Teil davon bereits.
- **`exapp/middleware.py` anfassen.** Phase 22 und 23 haben die Grenze unangetastet gelassen und sich das ausdrücklich zugute gehalten. Es gibt in dieser Phase keinen Grund, das aufzugeben.
- **Im Trockenlauf den laufenden `KeySet` benutzen.** Verbraucht die Bremsen des heißen Pfads.
- **Einen Prüfschritt weglassen, statt ihn mit "nicht geprüft" zu benennen.** Ein weggelassener Schritt liest sich als bestandener Schritt.
- **Eine feste Zahl in den `forget`-Docstring schreiben, die nicht gemessen wurde.** Genau der Grund, warum IN-05 auf diese Phase vertagt wurde.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fremden Text in eine Ausgabezeile bringen | Eine eigene Filterschleife je Modul | `audit/text.printable(value, limit=...)` | R-18-06: es gab drei Fassungen mit zwei verschiedenen Zeichensätzen, und die enge ließ einen Right-to-Left-Override durch |
| Eine Zeile an die Kette hängen | Eine zweite Stelle, die `prev_hash` liest und rechnet | `AuditStore.append` / `_append_row` | Zwei Stellen, die einen Vorgängerhash lesen, sind zwei Stellen, die sich über die Kette uneinig werden können (Docstring Zeile 630-636) |
| Ein Ablehnungsbezeichner | Freitext in der `reason`-Spalte | Ergänzung von `errors.REASONS` | `_known_reason` macht aus allem Unbekannten `unspecified`, und die Spalte existiert, um keinen Freitext zu haben (D-07) |
| occ-Aufrufkörper lesen | Einen eigenen Body-Parser | `_wants_json` / `_payload` / `bounded_body` aus `exapp/audit_verify.py` | Trägt bereits die drei gemessenen Lehren: Ankündigungslänge zuerst, `int("²")` wirft, mehr als 4300 Ziffern wirft seit Python 3.11 |
| Einen Anfragekörper begrenzen | Eigene Zählung | `exapp/responses.bounded_body` | Ein chunked Request kündigt gar nichts an (IN-01 der Phase-5-Nachprüfung) |
| Schlüsselsatz holen | Einen zweiten JWKS-Client für den Trockenlauf | `oauth/jwks.KeySet` mit eigener Instanz | Eine zweite Implementierung erbt die Härtungen der ersten nicht; genau der Grund für EXCH-01 |
| Ein Quelltext-Gate | `grep` über Dateien | Das AST-Muster aus `tests/contract/test_no_destructive_calls.py` | Kommentare und Docstrings müssen vor dem Zählen weg, sonst ist die übliche Reparatur, die erklärende Zeile zu löschen |

**Key insight:** In diesem Repo ist fast jede Regel schon einmal in zwei Fassungen geschrieben worden, und jedes Mal war die zweite die schwächere. Die Phase-24-Arbeit besteht überwiegend darin, bestehende Regeln an neue Stellen **zu reichen**, nicht sie dort neu zu schreiben.

## Common Pitfalls

### Pitfall 1: Die kanonische Feldliste erweitern und jede bestehende Kette brechen

**Was schiefgeht:** Ein `azp`-Feld wird an `CANONICAL_FIELDS` angehängt, die Tests sind grün (frische Testdatenbanken), und auf jeder Installation, die bereits Zeilen hat, meldet `occ mcp_connector:audit:verify` ab dem Update jede Zeile als `modified`.
**Warum es passiert:** Tests bauen ihren Store neu; der Bruch ist ausschließlich ein Bestandsphänomen.
**Wie vermeiden:** Option A aus D1 (Spalte `actor`). Falls der Planer trotzdem eine Spalte will: ein Test, der eine Datenbank im alten Schema anlegt, eine Zeile schreibt, dann das neue Schema öffnet und `verify_chains` laufen lässt. Der Test muss **vor** der Umsetzung rot sein.
**Warnzeichen:** Ein Plan-Task, der das Wort `ALTER TABLE` enthält.

### Pitfall 2: Abweisungszeilen als von einem Fremden bestellte Schreiblast

**Was schiefgeht:** Jede abgewiesene Exchange-Prüfung schreibt eine Zeile. Ein Fremder ohne jeden Schlüssel dieser Installation bestellt bis zu `PATH_CEILING = 200` Abweisungen je Fenster von 300 Sekunden und je Arbeiter, also in der Größenordnung von 50 000 bis 100 000 Zeilen am Tag. Landen sie in `i:instance`, verfallen sie nie und füllen die Größengrenze; landen sie in einer gefegten Kette, drücken sie die Historie echter Konten heraus, weil die Größengrenze **nur** Zeilen außerhalb der Instanz-Kette räumen darf.
**Warum es passiert:** Der Pfad ist vor-authentisch. `oauth/exchange.py:147-160` hat genau dieses Argument für die DEBUG-Stufe der Logzeile gemacht; für eine Datenbankzeile gilt es stärker, weil sie teurer ist und länger bleibt.
**Wie vermeiden:** Drei Maßnahmen zusammen, keine allein genügt.
1. Eigene, gefegte Kette (nicht `i:instance`).
2. Eine Schreibbremse: höchstens eine Zeile je Ablehnungsgrund je Zeitfenster, danach wird nur noch gezählt. Der Zähler kann in eine bestehende, nicht anders belegte Spalte einer `refusal`-Zeile (etwa `duration_ms` oder `removed`) - aber nur, wenn deren Bedeutung in dieser Zeilenart im Schemakommentar ausdrücklich benannt wird. Sauberer und ohne Umdeutung: eine Zeile je Fenster mit dem häufigsten Grund plus Gesamtzahl.
3. Der Schreibweg existiert nur, wenn das Audit-Log an ist (D-14).
**Warnzeichen:** Ein Test, der `EXCHANGE_LIMIT` Abweisungen erzeugt und danach `EXCHANGE_LIMIT` Zeilen erwartet.

### Pitfall 3: Der Ablehnungsgrund wird zum Orakel

**Was schiefgeht:** Der Bezeichner, der in die Audit-Zeile soll, findet seinen Weg in die HTTP-Antwort oder in eine WARNING-Zeile, und ein Angreifer erfährt, ob er an der Audience, am `azp` oder an der Signatur scheiterte.
**Warum es passiert:** Sobald `ExchangeRefused` ein Feld trägt, ist es verlockend, es an der nächsten Grenze mit auszugeben.
**Wie vermeiden:** Der Bezeichner verlässt den Prozess an **genau einer** Stelle, und das ist die Audit-Zeile. Ein Test hält den 401- und den 429-Body frei von den Wörtern, wie `test_the_429_of_the_exchange_path_names_no_check_that_failed` es für den 429 schon tut. Der Docstring von `ExchangeRefused` muss die Änderung erklären, sonst wird sie beim nächsten Lesen für einen Fehler gehalten.

### Pitfall 4: Der `azp` einer ungeprüften Abweisung landet in einer Zeile

**Was schiefgeht:** Um die Abweisung nützlich zu machen, wird der `azp` mitgeschrieben - aus einem Token, dessen Signatur gerade **nicht** gehalten hat. Ein Fremder schreibt damit frei wählbaren Text in die Audit-Kette der Instanz.
**Warum es passiert:** `acting_party(claims)` liegt fertig herum und sieht harmlos aus.
**Wie vermeiden:** Nur ein **geprüftes** Claim-Set darf einen `azp` in eine Zeile bringen. Das ist genau die Trennung, die das geforderte Gate prüfen muss. Bei einer Abweisung vor der Signaturprüfung steht in der Zeile kein Wert aus dem Token, Punkt.
**Warnzeichen:** Ein Aufruf von `acting_party` außerhalb von `resolve_identity` bzw. der Kontoquelle.

### Pitfall 5: Die dritte Kettenart wird vom Kontocheck als Konto behandelt

**Was schiefgeht:** `_SILENT_CHAINS` liefert jede Kette außer `i:instance`, `_account_of` schneidet nur `u:` ab, und `_drop_chains_without_an_account` fragt die AppAPI-Kontoliste. Eine Kette `x:exchange` würde nach 30 stillen Tagen als nicht existierendes Konto gelten und mit Grabstein gelöscht.
**Warum es passiert:** Die Kettenarten waren zwei, und `_account_of` ist gegen genau diese zwei gebaut.
**Wie vermeiden:** Präfixfilter in `_SILENT_CHAINS`, plus ein Test, der eine `x:`-Kette anlegt, den Kontocheck laufen lässt und beweist, dass sie steht.
**Warnzeichen:** `silent_users` gibt einen Wert zurück, der kein Kontoname ist.

### Pitfall 6: Das Token steht in der Prozessliste

**Was schiefgeht:** `occ mcp_connector:exchange:check --token=eyJ...` legt ein gültiges Bearer-Token in die Shell-Historie und in `ps` jedes Nutzers auf dem Nextcloud-Host.
**Warum es passiert:** Eine Option ist der offensichtliche Weg, und die beiden naheliegenden Auswege funktionieren hier nicht: eine `--token-file` läge auf dem **Nextcloud**-Host, während der Handler im **ExApp-Container** liest (verschiedene Dateisysteme), und stdin reicht AppAPI nicht weiter (`ExAppOccService::buildCommand` baut einen POST-Körper aus Argumenten und Optionen).
**Wie vermeiden:** Den Weg nehmen und die Folge benennen statt sie zu verschweigen. Konkret: die Option-Beschreibung sagt, dass der Wert in der Prozessliste steht und das Token deshalb ein kurzlebiges Testtoken sein soll; die Antwort wiederholt den Wert nie; ein zu großes Token wird vor dem Parsen an `MAX_TOKEN_BYTES` abgewiesen; die Doku empfiehlt, den Aufruf nicht in die Shell-Historie zu schreiben. Ein Token mit höchstens 900 Sekunden Lebensdauer (unsere eigene Obergrenze) begrenzt den Schaden ohnehin.
**Warnzeichen:** Eine Antwort, die das Token zur Bestätigung zurückgibt.

### Pitfall 7: Der Trockenlauf verbraucht die Bremsen des Betriebs

**Was schiefgeht:** Der Trockenlauf benutzt den `ExchangeTokenChecker` der laufenden Anwendung. Ein Token mit unbekanntem `kid` setzt die 60-Sekunden-Abkühlzeit, oder ein nicht erreichbarer Provider setzt die 10-Sekunden-Karenz; die nächsten echten Anfragen werden abgewiesen, obwohl nichts kaputt ist.
**Wie vermeiden:** Eigener `KeySet` je Trockenlauf. Der Preis (ein ausgehender Abruf) gehört in die Antwort.

### Pitfall 8: Ein Prüfschritt fehlt und liest sich als bestanden

**Was schiefgeht:** Die Kontoexistenz darf nicht geprüft werden (sie wäre ein Nextcloud-Aufruf), also fällt sie aus der Liste. Ein Admin liest lauter grüne Haken und schließt, das Token würde funktionieren - obwohl das Konto gar nicht existiert und MAP-02 genau daran abweist.
**Wie vermeiden:** Der Schritt steht in der Antwort, mit dem ausdrücklichen Ergebnis "nicht geprüft" und dem Grund. Und der letzte Satz der Antwort sagt, was ein durchgängig grüner Lauf **nicht** bedeutet - dieselbe Ehrlichkeit, die `LIMIT_SENTENCE` in `audit_verify` hat.

### Pitfall 9: Der Zwei-Konten-Nachweis beweist die falsche Grenze

**Was schiefgeht:** Der Nachweis misst zwei Konten, die über **Login Flow v2** oder AppAPI verbunden sind, und nennt es einen Exchange-Nachweis. Dann ist nur bewiesen, was `docs/spike-dav.md` schon 2026-08-15 bewiesen hat.
**Wie vermeiden:** Die zwei Identitäten müssen über den Exchange-Pfad entstehen, also aus zwei getauschten Tokens mit verschiedenen Konto-Claims, gegen eine armierte `NC_MCP_EXCHANGE_*`-Konfiguration. Die Rohausgabe muss das belegen, entweder durch die Audit-Zeilen (`client_id = urn:mcp-connector:token-exchange`) oder durch das serverseitige Impersonation-Log.
**Warnzeichen:** Im Nachweis taucht kein `NC_MCP_EXCHANGE_ISSUER` auf.

### Pitfall 10: Die Doku verspricht, was an F13 hängt

**Was schiefgeht:** `docs/token-exchange.md` nennt eine Audience-Konvention als "die" Konvention, obwohl F13-Entscheidung 1 offen ist, und ein Betreiber richtet nach einer Empfehlung ein, die sich noch ändert.
**Wie vermeiden:** Kriterium 5 verlangt das ausdrücklich: was der Pfad **nicht** leistet und was an F13s vier offenen Antworten hängt, muss als eigener Abschnitt dastehen, nicht als Fußnote. Die vier stehen unten in diesem Dokument.

## Code Examples

### Beispiel 1: Wie eine Zeile heute entsteht und wo `actor` dazukäme

```python
# Quelle: src/mcp_connector/audit/record.py:236-253 (bestehend)
audit_store = await recorder.store_provider()
seq = await audit_store.append(
    Entry(
        chain=user_chain(caller.nc_user),
        kind=KIND_CALL,
        at=int(time.time()),
        actor=None,              # <- D1: hier stuende die handelnde Partei
        nc_user=caller.nc_user,
        tool=tool,
        client_id=caller.client_id,     # heute schon: urn:mcp-connector:token-exchange
        auth_id=caller.auth_id,
        client_name=_clamped_client_name(caller.client_name),  # heute schon: der azp
        outcome=outcome,
        reason=_known_reason(reason),
        duration_ms=round(duration_s * _MILLISECONDS),
        params=set_parameter_names(ctx, tool),
    )
)
```

### Beispiel 2: Warum ein neuer `kind` gratis ist und eine neue Spalte nicht

```python
# Quelle: src/mcp_connector/audit/store.py:849 (bestehend)
recomputed = hashlib.sha256(_canonical(row[: len(CANONICAL_FIELDS)]) + previous_hash)
```

`kind` ist bereits Feld 3 von `CANONICAL_FIELDS`; ein neuer Wert darin ändert nur den Hash **der neuen** Zeile. Eine 18. Spalte ändert die Länge des Schnitts und damit die Nachrechnung **jeder** Zeile.

### Beispiel 3: Die Form, in der ein occ-Handler antwortet

```python
# Quelle: src/mcp_connector/exapp/audit_verify.py:158-186 (bestehend, gekuerzt)
async def audit_verify(request: Request) -> Response:
    guarded = _guard(request, env)              # x-origin-ip -> 404, kein AppAPI -> 401
    if isinstance(guarded, Response):
        return guarded
    as_json = await _wants_json(request)
    try:
        ...
    except Exception as exc:
        logger.error("the audit log could not be checked: %s", type(exc).__name__)
        if as_json:
            return json_response({"checked": False, "error": type(exc).__name__})
        return _text(f"the audit log could not be checked: {type(exc).__name__}")
    return json_response(_machine_readable(...)) if as_json else _text(_report(...))
```

Für den Trockenlauf gilt dieselbe Form; der JSON-Schlüssel, den ein Skript beobachtet, heißt dort nicht `broken`, sondern etwa `passed`, weil der Exit-Code immer 0 ist.

### Beispiel 4: Der IN-04-Zwilling, aus den vorhandenen Helfern

```python
# Muster: tests/unit/test_oauth_exchange_chain.py:1175-1200
# Helfer: tests/unit/test_exapp_entry.py:2117 (bearer_call), 2440 (EXCHANGE_ENV)
app = entry_exapp.build_exapp_app({**SERVED_ENV, **EXCHANGE_ENV, config.ENV_PUBLIC_URL: PUBLIC_URL})
with TestClient(app) as client:
    refused = [bearer_call(client, "a.b.c").status_code for _ in range(throttle.EXCHANGE_LIMIT)]
    throttled = bearer_call(client, "a.b.c")
    dotless = bearer_call(client, "a-token-this-server-issued-itself")

assert refused == [401] * throttle.EXCHANGE_LIMIT
assert throttled.status_code == 429 and int(throttled.headers["Retry-After"]) > 0
assert keys.call_count == 0            # ein unlesbarer Header kostet keinen Abruf
assert dotless.status_code == 401      # die Ausnahme der MCP-Route haelt fuer eigene Tokens
```

### Beispiel 5: Das Playbook-Kommando, gegen den Quelltext verifiziert

```bash
# Quelle: nextcloud/server v35.0.0, apps/oauth2/lib/Command/AddClient.php
# Zwei Pflichtargumente, keine Optionen ausser den Ausgabeformaten der Basisklasse.
occ oauth2:add-client "<name>" "<redirect-uri>"
```

`[VERIFIED: gh api repos/nextcloud/server/contents/apps/oauth2/lib/Command/AddClient.php?ref=v35.0.0]` - `setName('oauth2:add-client')`, `addArgument(ARGUMENT_CLIENT_NAME, InputArgument::REQUIRED)`, `addArgument(ARGUMENT_CLIENT_REDIRECT_URI, InputArgument::REQUIRED)`, Validierung der Redirect-URI mit `FILTER_VALIDATE_URL`, Ausgabe über `writeArrayInOutputFormat`.

**Offene Frage dazu (nicht aus dem Repo beantwortbar):** wofür genau dieser Client im F13-Szenario steht, steht in Abschnitt 6 von F13s Spec-Note, und diese Note liegt nicht im Repo. Der Standalone-Betrieb dieses Connectors spricht heute über `NC_MCP_OIDC_*` mit einem externen Provider (`docs/standalone-oauth.md:99-104`) und über Login Flow v2 mit Nextcloud; ein Nextcloud-eigener oauth2-Client kommt dort nicht vor. Der Planer sollte den Zweck vor dem Schreiben der Doku klären, sonst steht im Playbook eine Zeile, deren Rolle niemand erklären kann. `[ASSUMED]`

## Doku-Bausteine für EXCH-08

Was `docs/token-exchange.md` tragen muss, abgeleitet aus Kriterium 5 und aus dem, was dieser Bericht gemessen hat:

1. **Die Kette in einem Bild:** F13-Orchestrator tauscht bei Keycloak, der Connector nimmt an. Der Connector tauscht nie selbst.
2. **Die Keycloak-Seite:** Standard Token Exchange V2, der Ziel-Client, die Audience-Konvention (Empfehlung: `client_id` des Ziel-Clients **ist** die kanonische Resource-URI der Instanz), die azp-Allowlist.
3. **Die Connector-Seite:** alle `NC_MCP_EXCHANGE_*`-Variablen mit ihren Defaults, aus `oauth/chain.py:19-65` übernommen (der Docstring ist die Quelle und die einzige Wahrheit).
4. **Der Kontoweg je Betriebsart:** ExApp = AppAPI-Impersonation ohne Provisionierung; Standalone = die vorab im Browser erteilte Bindung über `/exchange` (`docs/standalone-oauth.md:38-66`).
5. **Der erste Werkzeugaufruf:** was ein Erfolg ist und wie man ihn in der Audit-Kette wiederfindet (`occ mcp_connector:audit:read --json`).
6. **Der Trockenlauf:** das neue Kommando aus EXCH-06.
7. **Das `occ oauth2:add-client`-Playbook** (siehe oben, Zweck klären).
8. **Größen und Grenzen der Strecke**, mit den gemessenen Zahlen dieses Berichts: ca. 15,1 KB Anfragekopf bis HaRP, 8190 Byte je Header-Zeile in Nextclouds Apache auf dem `user-info`-Weg, 8192 Byte harte Tokengrenze im Connector, und der Rat an die F13-Seite, Rollen- und Gruppen-Mapper des Ziel-Clients schlank zu halten.
9. **Was dieser Pfad nicht leistet:** keine stille Kontoanlage; keine Delegationssemantik (Keycloak V2 schreibt kein `act`, die einzige Spur ist `azp`); keine Introspection und keine Widerrufsliste im heißen Pfad, also ist die Tokenlebensdauer die einzige Schranke (900 s Obergrenze); das Token wird bei jeder Anfrage von HaRP an Nextclouds PHP gereicht; ein Trockenlauf prüft die Kontoexistenz nicht.
10. **Was an F13s vier offenen Antworten hängt** (Abschnitt unten).

### F13s vier offene Antworten, wörtlich benannt

Die Roadmap verweist auf "F13s vier offene Antworten". Es gibt in den Rechercheunterlagen **zwei** Listen mit vier Punkten, und die Doku muss die richtige nennen.

**Die maszgebliche Liste** (die vier **Entscheidungen** aus der Spec-Note, `.planning/REQUIREMENTS.md:16` und `research/SUMMARY.md:165`):

| Nr. | Entscheidung | Was heute an ihrer Stelle steht |
|-----|--------------|----------------------------------|
| 1 | **Audience-Konvention**: welchen Wert F13 in `aud` schreibt | Default ist die Resource-URL dieser Instanz; die Empfehlung an F13 lautet, die `client_id` des Ziel-Clients auf genau diesen Wert zu setzen |
| 2 | **Konto-Claim**: welcher Claim auf das Nextcloud-Konto zeigt | `NC_MCP_EXCHANGE_ACCOUNT_CLAIM` mit dokumentiertem Default, plus zwei Mapping-Profile (`MAPPING_ACCOUNT_ID_V1`, `MAPPING_USER_OIDC_SUB_V1`) |
| 3 | **Beispiel-Token und Realm-Export** | Es wird gegen selbst gebaute Tokens getestet; die Golden-Fixture ist ausdrücklich Future Requirement (D-v1.6-02) |
| 4 | **Exchange-Ziel-Eintrag** bei F13 | Offen; ohne ihn tauscht F13 nicht auf diese Instanz |

**Die zweite Liste** in `research/FEATURES.md:203-206` und `SUMMARY.md:134` zählt die vier **Wissenslücken**, die daran hängen: welchen Wert F13 in `aud` schreibt, ob die F13-Instanzen `preferred_username` in getauschten Tokens führen, ob die Zielinstanzen LDAP-gebunden sind, und ob die AppAPI-Benutzerliste auf LDAP-Backends vollständig antwortet (Annahme A1 in `audit/accounts.py`).

Der letzte Punkt verdient in dieser Phase besondere Erwähnung: **A1 wird im Exchange-Pfad von einem Restrisiko zu einem Messpunkt.** Im Audit-Sweep bedeutet eine unlesbare Kontoliste "nichts tun" (`audit/record.py:179-205`), im Exchange-Pfad bedeutet dieselbe Unsicherheit "abweisen" (`oauth/exchange_accounts.py:52-58`, die umgekehrte Asymmetrie). Auf einer LDAP-Instanz, deren Kontoliste unvollständig antwortet, würden gültige Tokens gültiger Konten abgewiesen. Die Doku muss diesen Fall benennen, und der Trockenlauf muss ehrlich sagen, dass er ihn **nicht** prüft (Pitfall 8).

## Runtime State Inventory

Diese Phase ist kein Rename und keine Migration, aber sie schreibt in einen **bestehenden Datenbestand**, weshalb die Kategorien hier trotzdem beantwortet werden.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Gespeicherte Daten | Die Audit-SQLite jeder bestehenden Installation enthält Zeilen, die mit 17 kanonischen Feldern gehasht wurden | **Code-Regel, keine Datenmigration**: die Feldliste bleibt unverändert (D1). Wenn der Plan sie doch ändert, ist das eine Datenmigration, und dann gibt es keine, die die Kette erhält |
| Laufende Dienstkonfiguration | Drei bereits registrierte occ-Kommandos in der `app_api`-Tabelle jeder Installation (`mcp_connector:purge`, `:audit:verify`, `:audit:read`) | Ein viertes Kommando wird beim nächsten `enabled=1` registriert; `insertOrUpdate` keyt auf App-Id plus Name, also ist ein **neuer** Name unkritisch, ein **umbenannter** hinterließe einen 404-Eintrag (`exapp/occ.py:124-128`) |
| OS-registrierter Zustand | Keiner. Diese App registriert nichts beim Betriebssystem, verifiziert durch Lesen von `exapp/lifecycle.py` und `exapp/occ.py` | keine |
| Secrets und Umgebungsvariablen | `NC_MCP_EXCHANGE_*` ist gesetzt oder nicht; diese Phase führt keine neue Variable ein, wenn die Schreibbremse aus D2 fest verdrahtet bleibt | Falls der Plan eine Variable einführt: `EXCHANGE_VARIABLES` in `config.py` mitführen, sonst fällt der Deploy-Vertragstest |
| Build-Artefakte | Keine. Reine Python-Quellen, keine kompilierten Artefakte, kein Paketname ändert sich | keine |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | EXCH-07 (Messlauf), Header-Messung | ja | 29.5.2, linux | - |
| Laufende NC-35-HaRP-Topologie | EXCH-07, Transportmessung | **ja, läuft bereits** | `nc35-nc` 35.0.0, `nc35-harp` release, `nc35-caddy` caddy:2, ExApp in `nc_app_mcp_connector` | `compose.nc35.yml`, Port 127.0.0.1:8082 |
| `uv` | Alles | ja | 0.11.7 | - |
| Projekt-venv | Alles (System-Python ist defekt) | ja | `./.venv/Scripts/python.exe`, httpx 0.28.1, h11 0.16.0, uvicorn 0.52.3 | - |
| `gh` CLI | Quellenprüfung an Fremdrepos | ja | funktioniert unauthentifiziert für öffentliche Repos | WebFetch |
| **HTTPS-fähiger Test-Issuer** | EXCH-07 | **nein** | - | siehe unten |
| Lebende F13-Keycloak-Realm | Vollständiger Realitätsabgleich | nein | - | selbst gebaute Tokens, ausdrücklich als Annahme markiert (D-v1.6-02) |

**Fehlende Abhängigkeit mit Fallback: der HTTPS-Test-Issuer.** `ExchangeSettings` verlangt einen HTTPS-Issuer (`oauth/exchange.py:193, 537-544`), und `jwks.fetch_json` prüft Gleich-Origin. Ein Messlauf braucht also einen TLS-terminierten Schlüsselsatz-Endpunkt im Compose-Netz. Der Fallback ist gemessen und funktioniert: `jwks.py` baut seinen `httpx.AsyncClient` ohne `verify=` und ohne `trust_env=False`, und httpx 0.28.1 wertet in genau diesem Fall `SSL_CERT_FILE` bzw. `SSL_CERT_DIR` aus. `[VERIFIED: .venv/Lib/site-packages/httpx/_config.py:31-40]` Ein kleiner Container mit selbst signiertem Zertifikat plus `SSL_CERT_FILE` im ExApp-Container genügt also; ein vollständiger Keycloak ist für den Zwei-Konten-Beweis nicht nötig und wäre nur für die Golden-Fixture interessant, die ausdrücklich nicht im Scope ist.

**Fehlende Abhängigkeiten ohne Fallback:** keine. Alles, was die vier Erfolgskriterien verlangen, ist auf dieser Maschine messbar.

## Security Domain

### Anwendbare ASVS-Kategorien

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | ja | Unverändert aus Phase 21/22/23: PyJWT gegen JWKS, Algorithmen-Allowlist, exakte Audience, azp-Allowlist. Diese Phase fügt keine Authentisierung hinzu |
| V3 Session Management | ja | Der Trockenlauf darf **keine** Sitzung hinterlassen (Kriterium 3). Kein Store-Schreibzugriff, keine Autorisierung, keine Audit-Zeile |
| V4 Access Control | ja | occ-Kommandos laufen über AppAPI, `_guard` weist den Proxy-Pfad mit 404 und einen fehlenden AppAPI-Nachweis mit 401 ab, ununterscheidbar (`exapp/audit_verify.py:309-323`) |
| V5 Input Validation | ja | Der Tokenwert des Trockenlaufs ist Eingabe von außen: Größengrenze vor dem Parsen, Body-Grenze 4096 Byte, Ankündigungslänge vor dem Wert, keine Wiederholung in der Antwort |
| V6 Cryptography | ja | Nichts Eigenes. SHA-256-Kette bleibt wie sie ist, PyJWT bleibt der einzige Prüfer |
| V7 Error Handling and Logging | **Kern dieser Phase** | Feste Bezeichner statt Freitext (D-07), `type(exc).__name__` statt `str(exc)`, kein Wert aus der Umgebung in einer Zeile (T-22-04), keine Claims in einer Zeile |
| V8 Data Protection | ja | Die Audit-Zeile ist die einzige Persistenz; das Verfallsfenster und die Größengrenze gelten für die neue Kettenart mit |

### Bekannte Bedrohungsmuster für diesen Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Fremdbestellte Schreiblast auf der Audit-Datenbank | Denial of Service | Eigene gefegte Kette plus Schreibbremse plus `EXCHANGE_LIMIT`/`PATH_CEILING` (Pitfall 2) |
| Verdrängung echter Historie durch Müllzeilen | Tampering (mittelbar) | Die Größengrenze darf nur Nicht-Instanz-Zeilen räumen; eine geflutete Abweisungskette würde Nutzerzeilen mitreißen (Pitfall 2) |
| Ablehnungsgrund als Orakel | Information Disclosure | Der Bezeichner verlässt den Prozess nur in die Audit-Zeile; Body-Test (Pitfall 3) |
| Fremder Claim-Text in einer Ausgabezeile | Tampering (Log Injection) | `audit/text.printable` auf jedem fremden Wert, auch auf `actor` (D1, Feinheit 2) |
| Bearer-Token in der Prozessliste | Information Disclosure | Benannte Grenze plus kurzlebige Testtokens (Pitfall 6) |
| Erschöpfung der vor-authentischen Bremsen durch einen Admin-Trockenlauf | Denial of Service (Selbstschaden) | Eigener `KeySet` je Trockenlauf (Pitfall 7) |
| Gebrochene Kettenprüfung als stiller Vertrauensverlust | Repudiation | Keine Änderung an `CANONICAL_FIELDS` (Pitfall 1) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Abgewiesene Exchange-Versuche stehen in keiner Zeile | Eigene Kettenart mit gebremster Schreibrate | Diese Phase | Der Betreiber sieht, dass jemand es versucht, ohne dass ein Fremder die Datenbank füllen kann |
| `azp` reist als `client_name` mit | `azp` steht in `actor`, `client_name` bleibt für registrierte Clients | Diese Phase (ändert eine Formulierung aus 23-02) | Ein Leser unterscheidet handelnde Partei und Clientname, ohne `client_id` mitlesen zu müssen |
| Header-Größe "ungemessen" (Roadmap) | ca. 15,1 KB Anfragekopf bis HaRP, 8190 B je Header-Zeile in Nextclouds Apache, gemessen | 2026-09-23, dieser Bericht | Die Doku kann eine Zahl nennen statt einer Vermutung |
| Golden-Fixture aus echtem F13-Token | Selbst gebaute Tokens, ausdrücklich als Annahme markiert | D-v1.6-02 | Future Requirement, kein Blocker |

**Veraltet / nicht mehr gültig:**

- Die Aussage aus `research/SUMMARY.md:146` ("Abgewiesene Exchange-Versuche im Audit-Log: eigener kleiner Roadmap-Punkt **außerhalb** dieses Meilensteins") ist von AUDIT-07 überholt. Sie steht als Zustandsbeschreibung weiterhin richtig, als Scope-Aussage nicht mehr.
- Der Satz in `oauth/exchange_accounts.py:27-34`, die Kette wachse "without the audit chain growing a new field", beschreibt den Stand nach Phase 23 und wird von D1 bewusst aufgehoben. Der Docstring gehört in derselben Änderung mitgezogen, sonst widerspricht der Quelltext sich selbst.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Ein echtes F13-Keycloak-Token liegt in der gemessenen Größenordnung von 1 bis 4 KB | Header-Größe | Zu klein geschätzt: die 8-KB-Grenzen greifen früher als die Doku sagt. Gegenmittel: die Doku nennt die Schwelle (68 Rollen plus 68 Gruppen), nicht nur die Erwartung |
| A2 | Die 400er aus dem `user-info`-Pfad füttern HaRPs Brute-Force-Liste nicht | Header-Größe | Wenn doch, könnte ein fettes Token eine Quelle sperren. Nicht gemessen, nur aus dem Agenten-Quelltext geschlossen |
| A3 | Der `occ oauth2:add-client`-Eintrag aus F13s Spec-Note betrifft einen Nextcloud-eigenen oauth2-Client und nicht den Connector | Doku-Bausteine, Beispiel 5 | Die Doku beschreibt einen Schritt mit falscher Begründung. Vor dem Schreiben klären |
| A4 | Eine dritte Kettenart bricht keinen bestehenden Leser der Audit-Daten außer `_SILENT_CHAINS` | D2, Pitfall 5 | Ein übersehener Leser (Textausgabe von `audit_read`, `--user`-Filter) zeigt sie falsch. Gegenmittel: im Plan alle Leser von `chain` aufzählen und einzeln prüfen |
| A5 | `ExAppOccService` reicht einen Optionswert von mehreren Kilobyte unverändert durch | D3, Pitfall 6 | Ein langes Token wird abgeschnitten, und der Trockenlauf meldet einen Formfehler statt des echten Ergebnisses. Sollte im Plan als erste Messung des Trockenlauf-Tasks stehen |
| A6 | `SSL_CERT_FILE` im ExApp-Container genügt für einen selbst signierten Test-Issuer | Environment Availability | Der EXCH-07-Lauf braucht dann doch einen echten Keycloak. Der httpx-Quelltext ist gelesen, der Weg im Container nicht gemessen |

## Open Questions

Stand nach der Planung vom 2026-09-23: alle fünf Fragen sind aufgelöst. Jeder Eintrag trägt
den Marker **RESOLVED** mit dem Plan, der die Frage entscheidet oder beantwortet. Wer die Pläne
ändert, muss den Marker mitlesen: eine Frage, deren Plan wegfällt, ist wieder offen.

1. **Wie viele JWKS-Abrufe kann ein Gegenüber nach Phase 23 je Fenster bestellen?**
   - Was wir wissen: alle Bestandteile (Cache 300 s, Abkühlzeit 60 s, Karenz 10 s, `EXCHANGE_LIMIT` 30 zählt nur Abweisungen, `forget()` setzt `fetched_at = -inf`, Widerruf löst `forget()` aus).
   - Was unklar ist: die Zahl. Sie ist genau das, was IN-05 nachzumessen verlangt.
   - Empfehlung: ein `respx`-Test mit `call_count` als Zähler, und die gemessene Zahl mit Datum in den Docstring von `jwks.forget`.
   - **RESOLVED (Plan 24-07, Task 2):** keine Entscheidung, sondern ein Messliefergegenstand. IN-05 wird mit genau diesem `respx`-Lauf nachgemessen, und die gemessene Zahl steht mit ihrer Rechnung und ihrem Datum im Docstring von `jwks.forget`.

2. **Braucht der Standalone-Betrieb eine eigene Oberfläche für den Trockenlauf?**
   - Was wir wissen: occ existiert nur im ExApp-Modus, der Exchange-Pfad existiert in beiden.
   - Was unklar ist: ob EXCH-06 als erfüllt gilt, wenn der Trockenlauf nur im ExApp-Modus erreichbar ist.
   - Empfehlung: die Regel als reine Funktion bauen, damit eine zweite Oberfläche später eine Datei ist, und die Frage im Plan ausdrücklich entscheiden.
   - **RESOLVED (Plan 24-05, objective):** entschieden. In dieser Phase bekommt nur der ExApp-Betrieb eine Oberfläche (occ, Plan 24-06); der Standalone-Betrieb bekommt keine. Die Regel wird als reine Funktion gebaut, damit eine zweite Oberfläche später nur noch eine Datei ist, und die Grenze wird in `docs/token-exchange.md` (Plan 24-09) ausdrücklich benannt statt stillschweigend gelassen.

3. **Wofür steht der `occ oauth2:add-client`-Schritt im F13-Szenario?**
   - Was wir wissen: das Kommando existiert und hat genau zwei Pflichtargumente (v35.0.0 gelesen).
   - Was unklar ist: welche Rolle der Client im Aufbau spielt. Die Quelle ist F13s Spec-Note Abschnitt 6, die nicht im Repo liegt.
   - Empfehlung: vor dem Schreiben der Doku beim Owner klären; sonst steht im Playbook eine Zeile ohne Begründung.
   - **RESOLVED (Plan 24-09, Task 1):** als blockierender Owner-Checkpoint (`checkpoint:decision`) vor dem Schreiben der Doku eingeplant. Die Antwort des Owners entscheidet, ob die Zeile ins Playbook kommt und mit welcher Begründung.

4. **Trägt die Abweisungszeile den Grund einzeln oder aggregiert?**
   - Was wir wissen: die festen Phrasen existieren, `REASONS` ist erweiterbar, und eine Zeile je Versuch ist eine Flutungsfläche.
   - Was unklar ist: welcher Auflösung der Betreiber wirklich bedarf.
   - Empfehlung: eine Zeile je Grund je Zeitfenster mit Gesamtzahl. Das erfüllt "ein abgewiesener Versuch ist sichtbar" und ist flutungsfest.
   - **RESOLVED (Plan 24-03, Task 2):** entschieden wie empfohlen. Eine Zeile je Grund je Fenster (`REFUSAL_WINDOW_SECONDS = 300`), die Gesamtzahl der Versuche des Fensters steht im Feld `removed`, und der Grund ist der gruppierte Bezeichner aus `errors.REASONS`, nie die feste Phrase.

5. **Wird `docs/exchange-evidence.md` eine eigene Datei oder ein Abschnitt in `docs/token-exchange.md`?**
   - Was wir wissen: EXCH-07 sagt "als Messdatei neben den bestehenden Client-Nachweisen", und die bestehenden Nachweise sind eigene Dateien (`spike-dav.md`, `nc35-evidence.md`).
   - Empfehlung: eigene Datei, aus `docs/token-exchange.md` verlinkt. Eine Einrichtungsdoku, in der ein Messprotokoll steht, wird von beiden Lesergruppen halb gelesen.
   - **RESOLVED (Plan 24-08):** entschieden wie empfohlen. `docs/exchange-evidence.md` ist eine eigene Datei und steht in `files_modified` von Plan 24-08; Plan 24-09 verlinkt sie aus `docs/token-exchange.md`.

## Sources

### Primary (HIGH confidence)

- Eigener Quelltext, Datei und Zeile gelesen: `audit/store.py`, `audit/record.py`, `audit/accounts.py` (indirekt), `audit/text.py` (indirekt), `exapp/occ.py`, `exapp/audit_verify.py`, `exapp/audit_read.py`, `exapp/middleware.py`, `oauth/chain.py`, `oauth/exchange.py`, `oauth/exchange_accounts.py`, `oauth/jwks.py`, `oauth/throttle.py`, `oauth/verifier.py`, `deps.py`, `errors.py`, `config.py`, `pyproject.toml`
- Eigene Testdateien: `tests/unit/test_oauth_exchange_chain.py:1175-1220`, `tests/unit/test_exapp_entry.py:2117-2123, 2440-2500`, `tests/contract/test_no_destructive_calls.py`, `tests/contract/test_audit_surface.py`
- Eigene Planungsunterlagen: `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md:179-192`, `.planning/BACKLOG.md` (BL-21), `.planning/research/SUMMARY.md`, `.planning/research/FEATURES.md`, `.planning/phases/23-*/23-0*-SUMMARY.md`, `.planning/phases/23-*/23-VERIFICATION.md`
- Eigene Messungen 2026-09-23 gegen die laufende Topologie `nc-mcp-nc35` (Caddy, HaRP, Nextcloud 35.0.0, ExApp): Transportgrenze 14 912/14 915 B über Caddy, 15 058/15 061 B direkt auf HaRP, Apache-`user-info`-Umschlag zwischen 8 050 und 8 200 B
- Eigene Messungen 2026-09-23 mit PyJWT im Projekt-venv: Tokengrößen 920 / 1 477 / 4 132 B, Schwelle zu 8192 B bei 68 Rollen plus 68 Gruppen
- Installierte Fremdpakete im Projekt-venv, Quelltext gelesen: `h11/_connection.py:69` (`DEFAULT_MAX_INCOMPLETE_EVENT_SIZE = 16 * 1024`), `uvicorn/protocols/http/h11_impl.py:60-62`, `httpx/_config.py:31-40` (`SSL_CERT_FILE`/`SSL_CERT_DIR`)
- `gh api repos/nextcloud/HaRP/contents/haproxy.cfg.template` (keine `tune.*`-Zeile), `.../haproxy_agent.py` (`EXCLUDE_HEADERS_USER_INFO`, `nc_get_user`)
- `gh api repos/nextcloud/server/contents/apps/oauth2/lib/Command/AddClient.php?ref=v35.0.0`
- httpd.apache.org/docs/2.4/mod/core.html (Default `LimitRequestFieldSize 8190`)
- nginx.org/en/docs/http/ngx_http_core_module.html (`large_client_header_buffers 4 8k`)

### Secondary (MEDIUM confidence)

- github.com/nextcloud/HaRP (README, Architekturbeschreibung: HAProxy plus FRP, SPOE-Filter, Brute-Force-Schutz)
- docs.nextcloud.com Developer Manual, ExApp/HaRP-Integration
- discourse.haproxy.org zu `tune.bufsize` minus `tune.maxrewrite` als wirksamer Kopfgrenze (Default 16384)

### Tertiary (LOW confidence)

- Alles, was an F13s vier offenen Entscheidungen hängt (Audience-Wert, Konto-Claim, Beispiel-Token/Realm-Export, Exchange-Ziel-Eintrag) sowie die Frage nach dem Zweck des `occ oauth2:add-client`-Schritts in F13s Spec-Note Abschnitt 6. Bewusst als Entscheidungsfläche markiert, nicht als Befund

## Metadata

**Confidence breakdown:**

- Bestandsaufnahme im eigenen Code: HIGH - jede Aussage an Datei und Zeile gelesen, keine über Suchtreffer geraten
- Audit-Kettenmechanik und die Folgen einer Feldänderung: HIGH - Schema, `_canonical`, `_row_values` und `_first_finding` zusammen gelesen
- Transportgrenzen der Kette: HIGH - selbst gemessen gegen eine laufende Produktionsnahe Topologie, mit Bisektion und identifiziertem antwortenden Bauteil
- Tokengrößen: MEDIUM - synthetisch gemessen gegen realistisch geformte Claim-Sätze; die echte F13-Größe bleibt offen
- occ-Kommandomuster: HIGH - Quelltext und die darin dokumentierten Messungen gegen app_api v34.0.3
- Die vier Entscheidungen (D1 bis D4): HIGH für die Beschränkungen, MEDIUM für die Empfehlungen (Entwurfsentscheidungen, keine Befunde)
- Alles mit F13-Bezug: LOW, ausdrücklich als Entscheidungsfläche markiert

**Research date:** 2026-09-23
**Valid until:** 2026-10-23 für den eigenen Code (ändert sich nur mit diesem Repo); 2026-10-07 für die Fremdmessungen (HaRP-Release-Tag bewegt sich, eine neue HaRP-Fassung könnte `tune.bufsize` setzen)

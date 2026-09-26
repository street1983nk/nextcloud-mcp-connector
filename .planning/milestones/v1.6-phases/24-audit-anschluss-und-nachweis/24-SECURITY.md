---
phase: 24
slug: audit-anschluss-und-nachweis
status: verified
threats_open: 0
threats_total: 38
threats_closed: 34
threats_accepted: 4
asvs_level: 2
block_on: critical
created: 2026-09-26
verified_at_head: e96477a
---

# Phase 24: Security

> Sicherheitsvertrag dieser Phase: Bedrohungsregister, akzeptierte Risiken, Audit-Trail.
> Grundlage sind die neun `<threat_model>`-Blöcke der Pläne 24-01 bis 24-09 (zur Planzeit
> verfasst, `register_authored_at_plan_time = true`) und die `## Threat Flags` der neun
> SUMMARYs. Belegt wird ausschließlich am Code des aktuellen HEAD `e96477a` (nach dem Rebase
> auf den Community-PR #8, Squash `89bb7e7`), nicht an Absicht und nicht an alten SHAs.

---

## Trust Boundaries

| Boundary | Beschreibung | Data Crossing |
|----------|--------------|---------------|
| Fremde Realm zu Audit-Zeile | `azp` ist von einem Fremden gewählter Text und landet in Datei und Konsolenausgabe | `actor`, geklammert und auf `ACTOR_LIMIT` gekürzt |
| Bestehende Installation zu neuem Code | ältere Zeilen werden vom neuen Code gelesen und nachgerechnet | `CANONICAL_FIELDS` unverändert |
| Fremder zu Transportgrenze | der Exchange-Pfad ist vor-authentisch; jede Antwort ist bestellbare Information | byte-gleiche 401/429, kein Bezeichner im Körper |
| Fremder zu Audit-Datenbank | jede Abweisungszeile ist eine von außen bestellte Schreibaktion | Kette, `kind`, Zeitpunkt, `outcome`, `reason`, Anzahl |
| Abweisungskette zu Kontoprüfung D-12 | die Kontoprüfung löscht Ketten ohne Konto | nur Ketten mit `USER_CHAIN_PREFIX` |
| Vorgelegtes Token zu Trockenlauf | Administratorwert, inhaltlich fremder Text | nie zurückgegeben, nur Schritt, Ausgang, Bezeichner |
| Trockenlauf zu Identitätsanbieter / laufender Betrieb | ein JWKS-Abruf je Lauf, keine Bremse des heißen Pfads verbraucht | eigene `KeySet`-Instanz |
| AppAPI zu occ-Route | einzige Admin-Grenze des Kommandos | Doppelprüfung `x-origin-ip` (404) + `require_appapi` (401) |
| Administrator zu Prozessliste | Tokenwert als Optionswert in `ps` und Shell-Historie | benannt, nicht behoben |
| Konto A zu Dateien von Konto B | von Nextcloud durchgesetzt, hier gemessen | 404, nie 200 |
| Nextcloud-Anmeldung zu getauschtem Token | HaRP löst eine mitgeschickte Anmeldung vor dem Bearer auf | handelnde Identität (siehe T-24-32) |
| Messlauf zu Repo, Test-Issuer zu ExApp-Container | Schlüssel, Tokens, selbst signiertes Zertifikat | nur im Prozess bzw. in der Wegwerf-Topologie |
| Doku zu Betreiber, Doku zu Code | jede Zahl der Doku ist eine Behauptung über den Code | Gate `test_docs_exchange_truth.py` |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (Belegstelle im Code) | Status |
|-----------|----------|-----------|-------------|----------------------------------|--------|
| T-24-01 | Tampering (Log Injection) | `audit/store._row_values`, `exapp/audit_read._line` | mitigate | Eine Regel: `audit/text.py:34-53` (`str.isprintable` wird zu Leerzeichen, Läufe fallen zusammen, Schnitt bei `limit`). `ACTOR_LIMIT = 64`: `store.py:170`; `_clean_actor` ruft `printable(value, limit=ACTOR_LIMIT)`: `store.py:614-632`, angewendet in `_row_values` `store.py:646`. Ausgabe: Textform `audit_read.py:321` über `_cleaned` `:345`, JSON-Form `audit_read.py:417`. Fälle mit `\n` und U+202E: `tests/unit/test_audit_store.py:356` (Asserts `:380-383`), `tests/unit/test_exapp_audit_read.py:773`, `tests/unit/test_audit_record.py:404`; Grenze gegen `exchange_accounts.MAX_ACTING_PARTY_LENGTH`: `test_audit_store.py:386` | CLOSED |
| T-24-02 | Denial of Service | `audit/refusals.RefusalWriter` | mitigate | Fenster je Bezeichner, Zähler statt Zeile: `refusals.py:139-148`; Fenster `REFUSAL_WINDOW_SECONDS = 300`: `refusals.py:68`; Zustand begrenzt, weil der Schlüssel `known_reason(reason) or REASON_UNSPECIFIED` ist (`refusals.py:140`). Fälle: `tests/unit/test_audit_refusals.py:172` (1000 Abweisungen, eine Zeile), `:203` (Nachtrag `removed == 1000`), `:261` (Zustand durch Zahl der Gründe begrenzt), `:482` (werfender Store nur einmal je Fenster gefragt) | CLOSED |
| T-24-03 | Information Disclosure | HTTP-Antwort des Exchange-Pfads (401, 429) | mitigate | Nur `reason` aus dem eingefrorenen Satz, die Antwort bleibt eine für alle Gruppen: `chain.py:565-573`. Bezeichner eingefroren: `errors.py:43-71`, `known_reason` `errors.py:94`. Wortgate und Byte-Gleichheit: `tests/unit/test_oauth_exchange_chain.py:1504` (429 ohne Bezeichner), `:1523` (vier verschieden scheiternde Tokens, eine 401). ExApp-Zwilling: `tests/unit/test_exapp_entry.py:2998` | CLOSED |
| T-24-04 | Information Disclosure / Tampering | Abweisungszeile, `oauth/chain.py`, `audit/refusals.py` | mitigate | Der Schreiber bekommt nur einen Bezeichner: Typ `RefusalNote = Callable[[str], Awaitable[None]]` `chain.py:375-377`; Aufrufe `chain.py:572,585,626`. Die Zeile trägt sechs Werte, `actor` leer: `refusals.py:152-165`. Quelltext-Gate: `tests/contract/test_no_claim_leak.py:196,209,250,262,279` (mit Gegenproben `:209,262,314`). Lesesicht: `tests/unit/test_exapp_audit_read.py:1009`; Ablage: `tests/unit/test_audit_store.py:1088`. Anmerkung: Das Plan-Kriterium "grep `azp` in `refusals.py` = 0" trifft heute einmal, in einem Kommentar (`refusals.py:152`); das maßgebliche Gate filtert Prosa (`test_no_claim_leak.py:291`) und ist grün | CLOSED |
| T-24-05 | Repudiation | `audit/store.CANONICAL_FIELDS` | mitigate | Feldliste `store.py:336-354`, im Diff `89bb7e7..e96477a` nicht verändert (nur Erwähnungen in Kommentaren). Festgehalten: `tests/unit/test_audit_store.py:399` (die siebzehn Felder aus Phase 18). Neu öffnen und nachrechnen: `test_audit_store.py:429` (`verify_chains() == []` über eine zweite Store-Instanz). Der neue `kind` ist ein Wert: `KIND_REFUSAL` `store.py:253` | CLOSED |
| T-24-06 | Information Disclosure | Tokenwert in `ps` und Shell-Historie | mitigate | Folge in der Optionsbeschreibung benannt: `exapp/occ.py:216-220`, gehalten von `tests/unit/test_exapp_lifecycle.py:553`. Antwort wiederholt den Wert nie: `exchange_check.py:278-283`, Fälle `tests/unit/test_exapp_exchange_check.py:411,421`. Lebensdauergrenze `MAX_TOKEN_LIFETIME_SECONDS = 900`: `oauth/exchange.py:100`. Doku: `docs/token-exchange.md:183-187`. Der Restweg (Wert steht im `ps`) ist per Konstruktion nicht schließbar und so im Plan vorgesehen | CLOSED |
| T-24-07 | Denial of Service (Selbstschaden) | `oauth/jwks.KeySet` des laufenden Prüfers | mitigate | Eigene Instanz je Lauf: `exchange_dryrun.py:395-401` (`keys = KeySet(...)` innerhalb von `dry_run`). Preis in der Antwort: `COST_SENTENCE` `exchange_dryrun.py:177-181`. Fälle: `tests/unit/test_oauth_exchange_dryrun.py:411` (Bremsen des laufenden Prüfers unberührt), `:390,:402` (null bzw. genau ein Abruf) | CLOSED |
| T-24-08 | Elevation of Privilege | `exchange_check._guard` | mitigate | `x-origin-ip` ergibt 404, fehlender AppAPI-Nachweis 401 ohne Detail: `exchange_check.py:398-411`; erster Schritt des Handlers: `exchange_check.py:250-253`. Route nur über `exchange_check_routes`: `entry_exapp.py:373`. Fälle: `tests/unit/test_exapp_exchange_check.py:147,154,160`; Transport: `tests/unit/test_exapp_entry.py:340` | CLOSED |
| T-24-09 | Information Disclosure | `DryRunStep`, `DryRunResult`, Text- und JSON-Antwort | mitigate | Felder nur `step`, `outcome`, `reason`, `note`: `exchange_dryrun.py:192-215`; Ergebnis `:218-231`. Markertests: `tests/unit/test_oauth_exchange_dryrun.py:341,642` (`azp`, `iss`, `aud`, `sub`, `kid`), `:375`. Konsole: `tests/unit/test_exapp_exchange_check.py:411,421`; Info-Zeile nennt nur Urteil und ersten gefallenen Schritt: `exchange_check.py:284-288` | CLOSED |
| T-24-10 | Information Disclosure | Messdatei, Skript, Compose-Änderung | mitigate | Schlüssel entsteht im Prozess: `scripts/exchange_evidence.py:259` (`rsa.generate_private_key`). `git status --short` am HEAD leer; `git ls-files` enthält keine `.pem`, `.key`, `.p12`, `.crt` und kein JWK. Der Phasen-Diff `89bb7e7..e96477a` außerhalb `.planning` enthält nur Quelltext, Tests, Doku, `compose.nc35.yml`, `appinfo/info.xml` und das Skript | CLOSED |
| T-24-11 | Spoofing (Fehlleitung) | Audience-Konvention, `occ oauth2:add-client` | mitigate | "Recommendation, not a rule.": `docs/token-exchange.md:62-67`; eigener Abschnitt "What hangs on F13's four open answers": `docs/token-exchange.md:309`, Zeile 1 `:317`. Gate: `tests/unit/test_docs_exchange_truth.py:269` (beide Ehrlichkeitsabschnitte), `:278` (Empfehlung), `:289` (Rolle des Clients offen), `:302` | CLOSED |
| T-24-12 | Information Disclosure | `OAuthIdentity.__repr__` | mitigate | `__repr__` nennt `nc_user`, `principal`, `auth_id`, `client_id`, `client_name`, `revoked`, `credential` und `app_password='***'`, nicht `actor`: `oauth/verifier.py:172-179` (Feld `actor` `:169`). Restpunkt: kein Test hält die Auslassung fest (Review IN-03, offen), siehe R-24-04 | CLOSED |
| T-24-13 | Spoofing | `deps.resolve_caller`, AppAPI-Zweig | accept | AppAPI-Zweig setzt `actor=None`: `deps.py:203`; OAuth-Zweig übernimmt `identity.actor or None`: `deps.py:188`. Siehe R-24-01 | CLOSED (accepted) |
| T-24-14 | Information Disclosure | Logstufe des Prüfers | mitigate | Eine Stelle, DEBUG, feste Phrase: `oauth/exchange.py:203` (`logger.debug("exchange refused: %s", reason)`). Gate: `tests/unit/test_oauth_exchange.py:1374` (genau die Phrase, kein Gruppenbezeichner), Handler direkt am Logger `:960` | CLOSED |
| T-24-15 | Tampering | `reason=` als freier Text | mitigate | `ExchangeRefused` im AST-Gate: `tests/unit/test_errors_reason.py:44` (`_ERROR_CLASSES_WITHOUT_THE_SUFFIX`), angewendet `:57`. Gegenprobe mit erfundenem Text: `test_errors_reason.py:147` (Quelle `:153`, `:158`). Flächenlauf `:162` | CLOSED |
| T-24-16 | Denial of Service | vergessener Bezeichner an einer Aufrufstelle | mitigate | Neunzehn `_refused(`-Stellen mit zwei Argumenten: `oauth/exchange.py:397-533`. AST-Gate: `tests/unit/test_oauth_exchange.py:1260` (Anzahl 19, `len(call.args) < 2` ist Befund), `:1280` (zweites Argument nur Name aus dem Sechsersatz) | CLOSED |
| T-24-17 | Tampering (mittelbar) | Größengrenze des Stores | mitigate | `CHAIN_EXCHANGE = "x:exchange"` `store.py:216`, getrennt von `CHAIN_INSTANCE` `store.py:195`. Verfall und Obergrenze sparen nur `CHAIN_INSTANCE` aus (`chain <> ?`): `store.py:415-424`, angewendet `store.py:766,773,802,809`. Fälle: `tests/unit/test_audit_store.py:1117` (nicht die Instanzkette), `:1137` (Verfall), `:1158` (Obergrenze), `:1180` (Änderung wird gefunden); Sweep vom Schreibweg: `tests/unit/test_audit_refusals.py:365,391` (CR-01) | CLOSED |
| T-24-18 | Repudiation | `silent_users`, `drop_user_chain` | mitigate | Positiver Präfixfilter mit `substr`: `store.py:458-461`, Präfix als Platzhalter aus `USER_CHAIN_PREFIX` (`store.py:199`) in `store.py:1052`. Fälle: `tests/unit/test_audit_store.py:1194`, `tests/unit/test_audit_accounts.py:504` (Kette steht nach einer Kontoprüfung, die sie nie kannte) | CLOSED |
| T-24-19 | Denial of Service | werfender Ablehnungsschreiber, Store-Fehler im vor-authentischen Pfad | mitigate | Kette: `chain.py:503-521` (`except Exception`, nur `type(exc).__name__`). Schreiber: `refusals.py:149-182` (Schreibung und Sweep in einer Klammer, nur Typname). Fälle: `tests/unit/test_oauth_exchange_chain.py:1044`, `tests/unit/test_audit_refusals.py:322,339` | CLOSED |
| T-24-20 | Elevation of Privilege | `exapp/middleware.py` | mitigate | `git diff --stat 89bb7e7 e96477a -- src/mcp_connector/exapp/middleware.py` ist leer | CLOSED |
| T-24-21 | Repudiation | Standalone-Betrieb ohne Verdrahtung | mitigate | `refusals=None` mit ausgeschriebener Begründung: `entry_oauth.py:278-292`. Fall: `tests/unit/test_entry_oauth.py:1206` (Assert `verifier._refusals is None` `:1227`). Begründung im SUMMARY 24-04 | CLOSED |
| T-24-22 | Elevation of Privilege | OAuth-Store, Autorisierungen, Audit-Kette | mitigate | `exchange_dryrun.py` importiert weder Store noch Kontoquelle (Importe `:32-65`). Fälle: `tests/unit/test_oauth_exchange_dryrun.py:683` (`OAuthStore`, `AuditStore` und `sqlite3.connect` vergiftet, Lauf grün), `:699` (Quelltext enthält weder `resolve_identity` noch `OAuthStore`, `AuditStore`, `note_refusal`) | CLOSED |
| T-24-23 | Information Disclosure | grüner Trockenlauf als falsche Zusicherung | mitigate | `OUTCOME_NOT_CHECKED = "not_checked"` `exchange_dryrun.py:154`, Hinweis `NOTE_WOULD_CALL_NEXTCLOUD` `:161`, `LIMIT_SENTENCE` `:166-172`, gesetzt in jeder Antwort `:229-230`, Schritt am Ende `:264-267`. Fälle: `tests/unit/test_oauth_exchange_dryrun.py:596,610,629`; Konsole `tests/unit/test_exapp_exchange_check.py:300` | CLOSED |
| T-24-24 | Tampering | Auseinanderlaufen von Trockenlauf und Betrieb | mitigate | AST-Drift-Gate über `oauth/exchange.py` und `oauth/jwks.py`: `tests/unit/test_oauth_exchange_dryrun.py:928` (Zählstand beider Dateien), `:940` (jede Abweisung hat einen Schritt), `:959` (gleiche Gruppe), `:976` (Phrase oder benannte Ausnahme), Gegenproben `:985,:993`, Laufzeithälfte `:1053,:1069` | CLOSED |
| T-24-25 | Denial of Service | sehr großes Token, Anfragekörper | mitigate | Rule: `MAX_TOKEN_BYTES` importiert (`exchange_dryrun.py:55-57`), Zeichen- und Bytegrenze vor jedem Dekodierschritt: `exchange_dryrun.py:317-329`; Betrieb gleichlautend `oauth/exchange.py:397-411`. Handler: `MAX_BODY_BYTES = 2 * MAX_TOKEN_BYTES` `exchange_check.py:144`, `MAX_ANNOUNCED_DIGITS = 10` `:150`, angekündigte Länge zuerst und nur ASCII-Ziffern `:515-519`, danach `bounded_body` `:522`, Länge vor Wert `:537-544`. Fälle: `tests/unit/test_oauth_exchange_dryrun.py:234,249,256`, `tests/unit/test_exapp_exchange_check.py:315,326,335,343,363` | CLOSED |
| T-24-26 | Denial of Service | occ-Kommandozeile der Instanz | mitigate | Eintrag `exapp/occ.py:350-372`: `"arguments": []`, Modi `optional` und `none`, Werte-Option mit `"default": None`. Positivliste über alle Schemata: `tests/unit/test_exapp_lifecycle.py:450`; neuer Eintrag: `test_exapp_lifecycle.py:526` | CLOSED |
| T-24-27 | Information Disclosure | Route im Manifest | mitigate | `/exchange-check` nur im Kommentar als siebter bewusst abwesender Pfad: `appinfo/info.xml:248-256`; die `<url>`-Liste `appinfo/info.xml:380-452` enthält ihn nicht. Moduldocstring `exchange_check.py:13-21`, Verdrahtungskommentar `entry_exapp.py:320-325`. Fall: `tests/unit/test_exapp_exchange_check.py:173` | CLOSED |
| T-24-28 | Denial of Service | `oauth/throttle` im ExApp-Aufbau | mitigate | Gemessener Lauf gegen `entry_exapp.build_exapp_app`: `tests/unit/test_exapp_entry.py:2954` (401 bis `EXCHANGE_LIMIT`, dann 429, `Retry-After > 0`, `keys.call_count == 0`) | CLOSED |
| T-24-29 | Denial of Service (gegen den Identitätsanbieter) | `oauth/jwks.KeySet.forget` | mitigate | Gemessene Zahl mit Rechnung im Docstring: `jwks.py:209-230` ("36 outgoing fetches per window of 300 seconds, which reads as 31 plus 5"). Messung: `tests/unit/test_oauth_jwks.py:575` (31 Zyklen), `:613` (5 Fehlabrufe), `:647` (beide zusammen, 36); `forget` hebt Bremsen nicht auf `:490,:514` | CLOSED |
| T-24-30 | Repudiation | Test, der den Drosselpfad nie erreicht | mitigate | Eigener Gegenfall ohne AppAPI-Header: `tests/unit/test_exapp_entry.py:3024` (Handschlag-401 ohne `WWW-Authenticate`, Bearer-401 mit; Zählung gemessen) | CLOSED |
| T-24-31 | Elevation of Privilege | Zugriff über Kreuz zwischen zwei gemappten Konten | mitigate | Messung 2 und 3 mit je drei Wegen: `docs/exchange-evidence.md:119-143`; Apache-Zugriffslog mit zwei `404`: `:157-158`; Impersonationslog mit aufgelöstem Konto: `:168-173`. Wiederholbarer Lauf: `scripts/exchange_evidence.py`. Die Grenze setzt Nextcloud durch, nicht dieser Code; gemessen ist sie | CLOSED |
| T-24-32 | Spoofing (Confused Deputy) | zwei Anmeldewege in einer Anfrage | accept | **Erklärte Mitigation widerlegt, Befund per Owner-Entscheid akzeptiert.** Der Plan sagte zu: "ein zusätzlicher gültiger Basic-Header ändert die handelnde Identität nicht". Gemessen wurde das Gegenteil: Exchange-Token von bob zuerst, Basic von alice danach, die Anfrage läuft als alice (`docs/exchange-evidence.md:179-236`, Befund `:207-219`). Ursache ist die unveränderte Reihenfolge von `exapp/middleware.py` (AppAPI-Handschlag vor Bearer). Im Code steht keine Gegenmaßnahme; vorhanden sind Dokumentation (`docs/token-exchange.md:289-305`) und die Unterscheidbarkeit im Audit (Zeile ohne `client_id` und ohne `actor`). Keine Rechteausweitung, weil der Aufrufer eine funktionierende Anmeldung des anderen Kontos halten muss. Siehe R-24-05 | CLOSED (accepted) |
| T-24-33 | Repudiation | Nachweis, der die falsche Grenze misst | mitigate | `NC_MCP_EXCHANGE_ISSUER=https://test-issuer/realms/evidence`: `docs/exchange-evidence.md:46`; `urn:mcp-connector:token-exchange` in der Rohausgabe: `:62`, `:276`, `:281`. Zitierte Zeilen gegen den Code gehalten: `tests/unit/test_docs_exchange_truth.py:400,425,438` (WR-01) | CLOSED |
| T-24-34 | Tampering | selbst signiertes Zertifikat im Vertrauensweg | accept | Nur in `compose.nc35.yml:94-115` (Dienst `test-issuer`) und im Messskript (`scripts/exchange_evidence.py:91,332-335`). Kein Treffer für `SSL_CERT_FILE` oder `test-issuer` in `src/`, `appinfo/` oder einem Dockerfile. Siehe R-24-02 | CLOSED (accepted) |
| T-24-35 | Tampering (Doppelpflege) | Vorgabewerte der Variablen | mitigate | Eine Quelle: `oauth/chain.DEFAULT_JWKS_PATH` (importiert in `tests/unit/test_docs_exchange_truth.py:41`). Beide Richtungen: `test_docs_exchange_truth.py:103` (keine erfundene Variable), `:113` (keine verschwiegene), Gegenprobe `:124`; Vorgabewert `:257`; Zahlen `:146,:154,:164,:183,:193,:202` | CLOSED |
| T-24-36 | Information Disclosure | Token auf Nextclouds PHP-Strecke | mitigate | Dokumentiert als Eigenschaft der Umgebung: `docs/token-exchange.md:275-278`, Grenzwert Apache `:237`. Disposition verlangt Dokumentation, nicht Code; sie ist vorhanden | CLOSED |
| T-24-37 | Denial of Service | zu fetter Rollen- und Gruppen-Mapper | mitigate | Gemessene Schwelle "about 68 realm roles and 68 groups" und Rat an F13: `docs/token-exchange.md:240-250`; Bytegrenze gegen den Code: `tests/unit/test_docs_exchange_truth.py:146,154` | CLOSED |
| T-24-SC | Tampering (Supply Chain) | `pyproject.toml`, `uv.lock` | accept | `git diff --stat 89bb7e7 e96477a -- pyproject.toml uv.lock` ist leer. Der Test-Issuer ist ein Container in `compose.nc35.yml`, keine Laufzeitabhängigkeit. Siehe R-24-03 | CLOSED (accepted) |

*Status: open · closed*
*Disposition: mitigate (Umsetzung erforderlich) · accept (dokumentiertes Risiko) · transfer (Dritte)*

**Zählung:** 38 Bedrohungen (Mehrfachnennungen über die Pläne zusammengeführt: T-24-03 in 24-02/04/07,
T-24-04 in 24-03/04, T-24-05 in 24-01/03, T-24-06 in 24-06/09, T-24-09 und T-24-25 in 24-05/06,
T-24-19 in 24-03/04, T-24-SC in allen neun). 34 `mitigate` CLOSED; 4 `accept` CLOSED über das
Accepted Risks Log (T-24-32 per Owner-Entscheid vom 2026-09-26 von `mitigate` auf `accept`
umgestellt, R-24-05). 0 OPEN. Keine Bedrohung mit Disposition `transfer`.

---

## Offene Bedrohungen

Keine. T-24-32 wurde am 2026-09-26 per Owner-Entscheid als R-24-05 akzeptiert; der Befund
des Auditors bleibt unten unverändert dokumentiert.

### T-24-32: Confused Deputy, eine auflösbare Nextcloud-Anmeldung entscheidet vor dem getauschten Token (GESCHLOSSEN als R-24-05)

**Einstufung:** war OPEN, Schwere nicht kritisch; die erklärte Mitigation fehlt nicht nur,
sie ist gemessen widerlegt. Per Owner-Entscheid vom 2026-09-26 akzeptiert (Weg 1 unten).

**Was zugesagt war:** 24-08-PLAN, Messung 4: "ein zusätzlicher gültiger Basic-Header ändert
die handelnde Identität nicht".

**Was am HEAD steht:**
- `src/mcp_connector/exapp/middleware.py` ist in dieser Phase unverändert (T-24-20 verlangt das
  sogar). Die Reihenfolge "AppAPI-Handschlag, dann Bearer" gilt damit auch für den Exchange-Pfad.
- Die Messung (`docs/exchange-evidence.md:179-236`) zeigt: Exchange-Token von bob plus gültiges
  Basic von alice läuft als alice; die Antwort sagt das nicht.
- Vorhanden sind nur Dokumentation (`docs/token-exchange.md:289-305`) und die nachträgliche
  Unterscheidbarkeit in der Audit-Zeile (ohne `client_id`, ohne `actor`). Dokumentation zählt
  in diesem Audit nicht als Mitigation.

**Durchsuchte Stellen:** `src/mcp_connector/exapp/middleware.py`, `src/mcp_connector/oauth/chain.py`,
`src/mcp_connector/deps.py`, `src/mcp_connector/entry_exapp.py`, `docs/token-exchange.md`,
`docs/exchange-evidence.md`, `.planning/phases/24-audit-anschluss-und-nachweis/24-08-SUMMARY.md:100-118,261`.

**Zwei Wege zum Schließen (Owner-Entscheid, nicht Aufgabe dieses Audits):**
1. **Akzeptieren:** Der Owner übernimmt den Befund als R-24-05 ins Accepted Risks Log, mit der
   Begründung aus `docs/token-exchange.md:299-305` (keine Rechteausweitung; Risiko ist ein
   browsernaher Betrieb mit mitfahrendem Cookie). Danach `/gsd:secure-phase 24` erneut.
2. **Im Code mitigieren:** Wenn der Bearer die Form eines Exchange-Tokens hat und AppAPI bereits
   ein Konto aufgelöst hat, die Anfrage abweisen oder beide Identitäten vergleichen und bei
   Abweichung abweisen. Das berührt `exapp/middleware.py` und wäre eine eigene Änderung mit
   eigenem Test und neuer Messung.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-24-01 | T-24-13 | Der AppAPI-Zweig von `deps.resolve_caller` setzt `actor=None` (`deps.py:203`). Auf diesem Weg gibt es keine handelnde Partei, und ein Wert wäre erfunden. Kein Angriffsweg, sondern eine begründete Auslassung (24-01-PLAN, Threat Register) | Owner (Plan 24-01) | 2026-09-26 |
| R-24-02 | T-24-34 | Das selbst signierte Zertifikat des Test-Issuers lebt nur in der lokalen Wegwerf-Topologie (`compose.nc35.yml`, `scripts/exchange_evidence.py`) und in keinem ausgelieferten Artefakt. Abweichend vom Plan wird nicht `SSL_CERT_FILE` gesetzt, sondern die Wurzel an das `certifi`-Bündel des laufenden Containers gehängt (24-08-SUMMARY, Abweichung 1); die Wiederherstellung am Ende ersetzt den Container. **Restpunkt (Review IN-06, offen):** mit `--keep-armed` oder nach einem Abbruch bleibt der Container dem Test-Aussteller gegenüber vertrauensvoll; das Skript gibt dabei `the test issuer root is appended to ...` aus (`scripts/exchange_evidence.py:335`), der Hilfetext von `--keep-armed` sagt es nicht | Owner (Plan 24-08) | 2026-09-26 |
| R-24-03 | T-24-SC | Die Phase installiert kein Paket (24-RESEARCH.md, "Package Legitimacy Audit": leere Tabelle mit Begründung); `pyproject.toml` und `uv.lock` sind im Phasen-Diff nicht enthalten. Der Test-Issuer ist ein Container der Testumgebung und keine Laufzeitabhängigkeit. Kommt ein Paket hinzu, gilt das Legitimitätsgate vor der Aufnahme | Owner (alle neun Pläne) | 2026-09-26 |
| R-24-04 | T-24-12 (Restrisiko) | `actor` fehlt im `__repr__` von `OAuthIdentity` (`verifier.py:172-179`), was die sichere Richtung ist. Kein Test hält die Auslassung fest, und der Docstring stellt `actor` und `client_name` unter dieselbe Regel (Review IN-03, offen). Eine spätere "Vervollständigung" des `__repr__` würde ohne Gate durchgehen | Auditor, offen zur Übernahme durch Owner | 2026-09-26 |
| R-24-05 | T-24-32 | Eine von HaRP auflösbare Nextcloud-Anmeldung (Basic, Cookie) entscheidet die handelnde Identität vor einem getauschten Token; die Antwort sagt das nicht. Gemessen in `docs/exchange-evidence.md:179-236`. Keine Rechteausweitung: der Aufrufer muss eine funktionierende Anmeldung des anderen Kontos bereits halten. Der Betreiber ist gewarnt (`docs/token-exchange.md:289-305`, Abschnitt 9), und die Audit-Zeile macht den Fall nachträglich unterscheidbar (ohne `client_id`, ohne `actor`). Risikoprofil ist ein browsernaher Betrieb mit mitfahrendem Cookie; der vorgesehene Betrieb (Server-zu-Server über den F13-Orchestrator) schickt keine zweite Anmeldung mit. Eine Code-Mitigation in `exapp/middleware.py` bleibt als mögliche spätere Härtung benannt | Owner | 2026-09-26 |

*Akzeptierte Risiken tauchen in künftigen Audit-Läufen nicht wieder als offen auf.*

---

## Threat Flags aus den SUMMARYs

| SUMMARY | Threat Flags vorhanden | Inhalt | Mapping |
|---------|------------------------|--------|---------|
| 24-01 | nein (Abschnitt fehlt; "Threat Model Coverage" vorhanden) | keine neue Fläche | T-24-01, 05, 12, 13, SC |
| 24-02 | ja | einzige neue Fläche ist `reason` an der Ausnahme | T-24-03 |
| 24-03 | ja | keine; die gebremste Schreibstelle ist die Mitigation selbst | T-24-02 |
| 24-04 | ja | keine; vier Fäden einzeln gemessen | T-24-03, 04, 19, 20, 21 |
| 24-05 | ja | der eine ausgehende Abruf je Lauf ist Vertrauensgrenze des Plans | T-24-07 |
| 24-06 | nein (Abschnitt fehlt; "Threat Model Coverage" vorhanden) | neue occ-Route, nicht im Manifest | T-24-08, 25, 26, 27 |
| 24-07 | ja | keine neue Fläche, nur Messung | T-24-28, 29, 30 |
| 24-08 | ja | `threat_flag: auth-precedence` in `exapp/middleware.py` | **T-24-32** (informational, deckt sich mit der offenen Bedrohung) |
| 24-09 | ja | keine; Prosa und ein Lesetest | T-24-11, 35, 36, 37 |

### Unregistered Flags

Keine. Die einzige Flag (`auth-precedence`, 24-08) bildet auf T-24-32 ab und ist deshalb kein
`unregistered_flag`, sondern der Messbefund, der T-24-32 offen hält. Die eine neue Route der
Phase (`/exchange-check`) ist als T-24-08, T-24-25 und T-24-27 geführt.

**Prozessnotiz (WARNING-Kandidat, kein Gap):** Die SUMMARYs 24-01 und 24-06 tragen keinen
Abschnitt `## Threat Flags`, wohl aber eine Tabelle "Threat Model Coverage". Beide Pläne
legen laut Diff keine Fläche an, die nicht im Register steht; die occ-Route von 24-06 ist
registriert.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-26 | 38 | 37 (34 mitigate + 3 accepted) | 1 (T-24-32, nicht kritisch) | gsd-security-auditor (Claude) |
| 2026-09-26 | 38 | 38 (34 mitigate + 4 accepted) | 0 | Owner-Entscheid T-24-32 akzeptiert (R-24-05), eingetragen vom Orchestrator |

**Stand des Codes.** Geprüft am HEAD `e96477a`, nach dem Rebase von `main` auf den
Community-PR #8 (Squash `89bb7e7`: `files_download`, Chunk-Upload, `NC_MCP_FILES_ROOT`-Sandbox).
Alle Zeilenbelege stammen aus diesem Stand. Der Phasen-Diff wurde als `89bb7e7..e96477a`
gelesen; er enthält die neun Pläne und den Review-Fix-Lauf (`77356ca` CR-01, `1aea085` WR-02,
`b6ead79` WR-03, `b95d52b` WR-04, `7f59f01` WR-05, `ae69696` WR-06, `eb28e8b` WR-01). Die
Korrekturen stützen T-24-17 (Sweep vom Abweisungsschreiber, `refusals.py:167-174`), T-24-19
(eine Klammer um Schreiben und Sweep), T-24-01 (`ACTOR_LIMIT` gegen die Quelle,
`test_audit_store.py:386`) und T-24-33 (zitierte Zeilen gegen den Code).

**Lauf dieses Audits.** 888 Fälle grün, 5 übersprungen, aus `tests/contract/test_no_claim_leak.py`,
`tests/unit/test_audit_refusals.py`, `test_audit_store.py`, `test_audit_record.py`,
`test_exapp_audit_read.py`, `test_oauth_exchange.py`, `test_oauth_exchange_chain.py`,
`test_oauth_exchange_dryrun.py`, `test_exapp_exchange_check.py`, `test_oauth_jwks.py`,
`test_docs_exchange_truth.py`, `test_exapp_lifecycle.py`, `test_exapp_entry.py`,
`test_entry_oauth.py` und `test_errors_reason.py`. `git diff --stat 89bb7e7 e96477a` ist leer
für `pyproject.toml`, `uv.lock` und `src/mcp_connector/exapp/middleware.py`. `git status --short`
ist leer.

**Nicht Gegenstand dieses Audits.** Es wurde nicht blind nach neuen Schwachstellen gesucht.
Geprüft wurde jede Kennung des Registers nach ihrer Disposition. Keine Implementierungsdatei
wurde geändert. Die sieben offenen Info-Befunde des Reviews (IN-01 bis IN-07) wurden nur dort
aufgenommen, wo sie eine Bedrohung des Registers berühren (IN-03 als R-24-04, IN-06 in R-24-02).

---

## Sign-Off

- [x] Alle Bedrohungen haben eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log dokumentiert (R-24-01 bis R-24-05)
- [x] `threats_open: 0` bestätigt (T-24-32 per Owner-Entscheid akzeptiert, R-24-05)
- [x] `status: verified` im Frontmatter gesetzt
- [x] Register am aktuellen HEAD `e96477a` nach Rebase und Review-Fix-Lauf geprüft

**Approval:** verified 2026-09-26 (Owner-Entscheid zu T-24-32 am selben Tag)

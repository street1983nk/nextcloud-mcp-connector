# Roadmap: MCP Connector für Nextcloud

## Milestones

- **v1.0 MVP im Store**: Phasen 1-5 (shipped 2026-08-20, Release 0.1.2 live im Nextcloud App Store)
- **v1.1 Verwaltungs-Clients und Härtungs-Reste**: Phase 6 (shipped 2026-08-20; Phase 7 deferred, extern getaktet)
- **v1.2 Kuratierte Breite**: Phasen 8-11 (shipped 2026-08-25, Release 0.1.8 live im Store; Talk, Tables und Mail dazu, ohne das Sicherheitsversprechen oder die Schlankheit aufzugeben)
- **v1.3 Pflege und 0.1.9**: Phasen 12-13 (shipped 2026-08-26, Release 0.1.9 live im Store; Konsistenz- und Härtungs-Schulden abgeräumt, CIMD live nachgemessen, Enterprise-Fake-Door)
- **v1.4 Pflege und 0.1.10**: Phasen 14-15 (shipped 2026-08-28, Release 0.1.10 live im Store; gekürzter Enterprise-Text und Kontaktwechsel zu admin@infranode.dev, Doku-Reste aus v1.3 abgeräumt)
- **v1.5 Vorlauf openDesk**: Phasen 16-19 (shipped 2026-08-31, Abschluss nachgetragen 2026-09-18; Release 0.1.11, openDesk-Spike, Audit-Log als erster Enterprise-Baustein)
- **v1.6 F13 Token Exchange Identity Mapper**: Phasen 20-24 (AKTIV seit 2026-09-18; ein zweiter, ab Werk ausgeschalteter Prüfpfad nimmt ein nach RFC 8693 getauschtes Keycloak-Token an und handelt unter dem gemappten Nextcloud-Konto)

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

### v1.6 F13 Token Exchange Identity Mapper (Phasen 20-24), AKTIV

- [x] **Phase 20: JWKS-Schicht und PyJWT-Stand** - Eine einzige, für den vor-authentischen Einsatz gehärtete Schlüsselsatz-Schicht für beide Prüfpfade, auf dem Abhängigkeitsstand, der genau diesen Pfad betrifft (completed 2026-09-19)
- [x] **Phase 21: Exchange-Verifier** - Ein Keycloak-JWS wird vollständig geprüft, bevor irgendetwas davon den Server erreicht, gegen selbst erzeugte Schlüssel und ohne eine Antwort von F13 (completed 2026-09-19)
- [x] **Phase 22: Konfiguration, Kette und Drosselung** - Eigener Namensraum, ab Werk aus, Prüferkette mit formbasierter Weiche, und der neue Pfad ist vor-authentisch drosselbar (completed 2026-09-19)
- [x] **Phase 23: Konto-Mapping und Credential-Wege** - Ein getauschtes Token handelt unter einem existierenden Konto, in beiden Betriebsarten, ohne neue Vollmacht und ohne stille Kontoanlage
- [ ] **Phase 24: Audit-Anschluss und Nachweis** - Ein über Exchange handelnder Aufruf ist so nachvollziehbar wie jeder andere, und die Einrichtung ist ohne Live-Zugriff verprobbar und belegt

## Phase Details (v1.6)

### Phase 20: JWKS-Schicht und PyJWT-Stand

**Goal**: Es gibt genau eine Schlüsselsatz-Schicht im Produktionsbaum, sie trägt die zwei für den unauthentisierten heißen Pfad fehlenden Fähigkeiten, und der bestehende OIDC-Fluss verhält sich unverändert
**Depends on**: Nichts (erste Bauphase des Milestones; die P0-Credential-Frage ist mit D-v1.6-01 bereits entschieden)
**Requirements**: EXCH-01, DEP-01
**Success Criteria** (was wahr sein muss):

  1. `oauth/jwks.py` ist die einzige Stelle im Produktionsbaum, an der ein Schlüsselsatz geholt, zwischengespeichert und rotiert wird; der bestehende OIDC-Fluss benutzt sie und verhält sich nachweislich gleich, belegt durch die bestehenden Tests ohne gelockerte Erwartung
  2. Ein unbekanntes kid löst nicht bei jedem Aufruf einen neuen Abruf aus: nach einem erfolglosen Nachladen gilt eine Abkühlzeit, gemessen an der Zahl der ausgehenden Abrufe unter einer Folge von Tokens mit erfundenen kid
  3. Gleichzeitige Anfragen nach demselben Schlüsselsatz erzeugen genau einen ausgehenden Abruf, von einem Test mit parallelen Aufrufen gehalten
  4. Ein unerreichbarer oder unbrauchbarer Schlüsselsatz führt zur Abweisung und nie zur Annahme, auch bei abgelaufenem Cache-Eintrag; Algorithmen- und Schlüsseltyp-Allowlist, Gleich-Origin-Prüfung und Größenlimit gelten in der herausgelösten Schicht unverändert weiter
  5. PyJWT steht auf >=2.14,<3 mit Lock 2.14.0, cryptography ist im selben Lock-Schritt mitgezogen, `docs/dependency-audit.md` trägt den Nachtrag zur Sicherheitsfreigabe vom 11.09.2026, und alle sechs Versionsstellen-Gates bleiben grün

**Plans**: 2 plans

Plans:

- [x] 20-01-PLAN.md: PyJWT auf >=2.14,<3, Lock 2.14.0, cryptography mitgezogen, Audit-Nachtrag (DEP-01)
- [x] 20-02-PLAN.md: oauth/jwks.py herausgelöst, OIDC verhaltensgleich umgestellt, Abkühlzeit und Single-Flight (EXCH-01)

### Phase 21: Exchange-Verifier

**Goal**: Ein fremdes Keycloak-JWS wird von freistehenden, testbaren Funktionen vollständig geprüft, und jede einzelne Abweichung hat ihren eigenen Ablehnungsgrund
**Depends on**: Phase 20 (teilt die herausgelöste Schlüsselsatz-Schicht)
**Requirements**: EXCH-02, EXCH-03
**Success Criteria** (was wahr sein muss):

  1. Ein selbst gebautes Token mit erlaubtem Issuer, gültiger Signatur, erlaubtem Algorithmus und Schlüsseltyp, vollständigen Pflicht-Claims und passender Audience wird angenommen; fremder Issuer, falscher Schlüssel, unerlaubter Algorithmus, unerlaubter Schlüsseltyp, abgelaufen, noch nicht gültig und fehlendes aud werden je einzeln abgewiesen
  2. Ein ID-Token wird abgewiesen, auch wenn es sonst alles Richtige trägt: der typ-Claim wird im Claim-Satz geprüft und nicht im Header, weil Keycloak dort `JWT` schreibt
  3. Die Audience wird exakt verglichen: ein Token, dessen Audience die konfigurierte nur als Pfadpräfix enthält, wird abgewiesen, und `check_resource_allowed` kommt im Exchange-Pfad nicht vor
  4. Ein Token mit mehreren Audiences hält nur, wenn die konfigurierte darunter ist, und die handelnde Partei wird über eine azp-Allowlist geprüft: ein unbekanntes azp wird abgewiesen, auch bei sonst fehlerfreier Signatur
  5. Uhrenversatz innerhalb der konfigurierten Toleranz hält, jenseits davon nicht, in beide Richtungen mit je einem Testfall

**Plans**: 2 plans

Plans:

- [x] 21-01-PLAN.md: Prüfkern in `oauth/exchange.py`: Issuer, Signatur über die Schlüsselsatz-Schicht, Algorithmen- und Schlüsseltyp-Allowlist, Standard-Claims, typ-Claim im Payload, Uhrenversatz (EXCH-02)
- [x] 21-02-PLAN.md: Audience exakt statt Präfix, azp-Allowlist, Negativkorpus und der gemessene Beweis gegen das Ablehnungs-Orakel (EXCH-03)

### Phase 22: Konfiguration, Kette und Drosselung

**Goal**: Der neue Prüfer hängt als Kette hinter der unveränderten Transportgrenze, hat einen eigenen Schalter, und im Aus-Zustand ist das Verhalten das von heute
**Depends on**: Phase 21 (die Kette muss die Form des Prüfers und die Feldnamen der Konfiguration kennen)
**Requirements**: CONF-01, EXCH-04, EXCH-05
**Success Criteria** (was wahr sein muss):

  1. Im Werkszustand (kein `NC_MCP_EXCHANGE_*` gesetzt) verhält sich der Server wie heute: `select_mode` kennt keinen sechsten Modus, der `StoreTokenVerifier` ist unverändert, und ein Test hält diesen Aus-Zustand fest
  2. Die vier von F13 abhängigen Werte (Audience, Konto-Claim, Issuer, azp) sind Konfiguration mit dokumentierten Defaults; eine halb ausgefüllte Konfiguration bricht beim Start mit einer benannten Meldung, statt still halb zu laufen
  3. Ein heute gültiges Token erreicht den neuen Code in keinem Fall: die Weiche fällt vor jeder Prüfung über die Tokenform (punktloser Store-Wert gegen kompaktes JWS mit zwei Punkten), es gibt keinen zweiten Versuch nach einem Fehlschlag, und ein Test belegt beide Richtungen
  4. Wiederholte Exchange-Ablehnungen werden vor-authentisch begrenzt: die bewusste Ausnahme der MCP-Route in `throttle.py` gilt für den neuen Pfad nicht, das Greifen der Grenze ist gemessen, und der Docstring der Ausnahme sagt in derselben Änderung die Wahrheit
  5. Ein Widerruf wirkt über die ganze Kette: derselbe `invalidate()`-Aufruf erreicht Store-Eintrag und zwischengespeicherten Schlüsselsatz, und ein Ausfall des Exchange-Zweigs macht aus fail-closed kein fail-everything für den bestehenden Pfad

**Plans**: 3 plans

Plans:

- [x] 22-01-PLAN.md: Namensraum `NC_MCP_EXCHANGE_*`, Schalter ab Werk aus, dokumentierte Defaults und Startabweisung bei halber Konfiguration (CONF-01)
- [x] 22-02-PLAN.md: `ChainedVerifier` mit formbasierter Weiche, gemeinsames `invalidate()` bis in den Schlüsselsatz, Einbau an beiden Transportgrenzen (EXCH-04)
- [x] 22-03-PLAN.md: Pfadklasse `CLASS_EXCHANGE`, gemessene Grenze auf der MCP-Route und der korrigierte Docstring der Ausnahme (EXCH-05)

### Phase 23: Konto-Mapping und Credential-Wege

**Goal**: Ein getauschtes Token handelt unter einem existierenden Nextcloud-Konto, in beiden Betriebsarten, ohne neue Vollmacht und ohne stille Kontoanlage
**Depends on**: Phase 22 (erst mit Kette und Konfiguration erreicht ein geprüftes Token einen Aufruf)
**Requirements**: MAP-01, MAP-02, CRED-01, CRED-02
**Success Criteria** (was wahr sein muss):

  1. Das Claim-Mapping ist konfigurierbar mit mindestens einem sub-basierten und einem LDAP-tauglichen Profil, und sein Ergebnis ist der kanonische Principal und nicht der Anmeldename; ein Test hält fest, dass Pausenschalter, Audit-Kettenname und Sweep für ein gemapptes Konto genauso greifen wie für ein angemeldetes
  2. Ein Token, dessen Claim auf kein existierendes Konto zeigt, wird abgewiesen: es entsteht kein Konto, und wenn die Kontoexistenz nicht feststellbar ist, wird ebenfalls abgewiesen statt durchgelassen
  3. Im ExApp-Modus erreicht ein per Exchange gemapptes Konto Nextcloud über AppAPI-Impersonation, ohne dass je Nutzer vorher etwas provisioniert wurde, und Nextcloud prüft die Rechtegrenze weiterhin selbst
  4. Im Standalone-Betrieb wählt das getauschte Token eine bestehende, vom Nutzer vorab im Browser erteilte Autorisierung aus und erzeugt keine neue; ein Token ohne solche Autorisierung wird mit einem Fehler abgewiesen, der nicht verrät, an welchem Schritt es lag
  5. Der Nutzer sieht die Exchange-Zuordnung bei seinen Verbindungen und kann sie einzeln widerrufen; der unmittelbar nächste Aufruf desselben getauschten Tokens wird danach abgewiesen

**Plans**: 6 plans

Plans:

- [x] 23-01-PLAN.md: Claim-Mapping-Profile (sub-basiert und LDAP-tauglich) und ihre Konfiguration im bestehenden Namensraum (MAP-01)
- [x] 23-02-PLAN.md: Die Exchange-Identität an der einen benannten Stelle, plus der gemessene Gleichlauf von Pausenschalter, Audit-Kette und Sweep (MAP-01)
- [x] 23-03-PLAN.md: ExApp: Kontoexistenz fail-closed gegen die Instanz und AppAPI-Impersonation als Credential-Weg (MAP-02, CRED-01)
- [x] 23-04-PLAN.md: Standalone: die vorab gebundene Autorisierung lesen, ohne Bindung eine ununterscheidbare Abweisung (CRED-02)
- [x] 23-05-PLAN.md: Standalone: die Mechanik, mit der eine Bindung nur nach bestätigter Browser-Identität entsteht (CRED-02)
- [x] 23-06-PLAN.md: Standalone: die Seite zum Einrichten, Sehen und Widerrufen, und der gemessene sofortige Widerruf (CRED-02)

### Phase 24: Audit-Anschluss und Nachweis

**Goal**: Ein über Exchange handelnder Aufruf ist genauso nachvollziehbar wie jeder andere, und die Einrichtung lässt sich ohne Live-Zugriff auf F13 verproben und belegen
**Depends on**: Phase 23 (erst mit einem Credential-Weg löst ein Ende-zu-Ende-Lauf einen echten Nextcloud-Aufruf aus)
**Requirements**: AUDIT-07, EXCH-06, EXCH-07, EXCH-08
**Success Criteria** (was wahr sein muss):

  1. Ein über Exchange ausgeführter Werkzeugaufruf steht in der bestehenden hash-verketteten Audit-Kette, trägt die handelnde Partei (azp) als eigenes Feld und hält die bestehenden Inhaltsverbote ein; über einen Lauf mit gemischten Aufrufen (eigenes Token und Exchange) bleibt die Kette prüfbar
  2. Ein abgewiesener Exchange-Versuch ist für den Betreiber sichtbar, ohne dass Token, Claims oder Schlüsselmaterial in einer Zeile stehen, von einem Gate gegen Claim-Leaks gehalten
  3. Ein Administrator prüft ein vorgelegtes Token mit einem Kommando gegen die aktive Konfiguration und bekommt je Prüfschritt ein benanntes Ergebnis; das Token löst dabei keinen Nextcloud-Aufruf aus und hinterlässt keine Sitzung
  4. Eine Messdatei neben den bestehenden Client-Nachweisen zeigt zwei über Exchange gemappte Konten, von denen keines die Dateien des anderen sieht, gemessen und nicht argumentiert
  5. Eine Doku unter `docs/` führt von der Keycloak-Seite bis zum ersten Werkzeugaufruf, nennt die empfohlene Audience-Konvention und das `occ oauth2:add-client`-Playbook und sagt ausdrücklich, was der Pfad nicht leistet und was an F13s vier offenen Antworten hängt

**Plans**: 9 plans

Plans:
**Wave 1**

- [ ] 24-01-PLAN.md: Die handelnde Partei (azp) als eigenes Feld in der Audit-Zeile, ueber die bestehende Spalte `actor` (AUDIT-07)
- [ ] 24-02-PLAN.md: Der Ablehnungsbezeichner an `ExchangeRefused`, sechs gruppierte Gruende, und das Antwort-Gate gegen ein Orakel (AUDIT-07)
- [ ] 24-07-PLAN.md: BL-21: der gemessene 429-Lauf gegen die gebaute ExApp (IN-04) und die nachgemessene JWKS-Abrufgrenze (IN-05)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 24-03-PLAN.md: Die gefegte Abweisungskette `x:exchange` und die Schreibbremse des vor-authentischen Pfads (AUDIT-07)
- [ ] 24-05-PLAN.md: Die Regel des Trockenlaufs als reine Funktion, mit eigenem Schluesselsatz und Drift-Gate (EXCH-06)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 24-04-PLAN.md: Der Ablehnungsschreiber an der Kette, an beiden Einstiegspunkten, plus das Gate gegen Claim-Leaks (AUDIT-07)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 24-06-PLAN.md: `occ mcp_connector:exchange:check` als viertes Kommando, mit gemessener Bodygrenze (EXCH-06)
- [ ] 24-08-PLAN.md: Der Zwei-Konten-Negativbeweis als Messdatei `docs/exchange-evidence.md` (EXCH-07)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 24-09-PLAN.md: Die Einrichtungsdoku `docs/token-exchange.md` von der Keycloak-Seite bis zum ersten Werkzeugaufruf (EXCH-08)

**Reihenfolge-Begründung**: Die Serialisierung folgt drei unabhängig belegten Punkten aus `research/SUMMARY.md`. Phase 20 steht zuerst, weil eine zweite Schlüsselsatz-Implementierung die Sorte Doppelpflege erzeugt, bei der eine Lücke später nur in einer der zwei Kopien geschlossen wird. Phase 21 baut den Prüfer als freistehende Funktionen, weil vier der zwölf kritischen Pitfalls dort vollständig gegen selbst erzeugte Schlüssel verifizierbar sind, ohne auf F13 zu warten. Phase 22 fasst Konfiguration und Kette zusammen, weil die Kette die Feldnamen der Konfiguration ohnehin kennen muss und beide denselben Aus-Zustand beweisen. Phase 23 kommt nach der Kette, weil die Vollmachtsfrage mit D-v1.6-01 entschieden ist und nur noch umgesetzt wird, und Phase 24 zuletzt, weil Audit-Zeile, Lasttest und Zwei-Konten-Beweis einen betriebsfähigen Pfad voraussetzen.

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
| 24. Audit-Anschluss und Nachweis | v1.6 | 0/9 | Planned | - |

## Next

`/gsd:plan-phase 20`: Phase 20 ist die risikoärmste und zugleich blockierende Bauphase. Sie verlangt eine verhaltensgleiche Umstellung des bestehenden OIDC-Flusses auf eine herausgelöste Schlüsselsatz-Schicht plus zwei neue Fähigkeiten (Abkühlzeit, Single-Flight) und die Anhebung von PyJWT auf >=2.14,<3, deren Sicherheitsfreigabe vom 11.09.2026 genau den Pfad betrifft, den dieser Milestone baut. Recherche ist laut `research/SUMMARY.md` für die Phasen 20 bis 22 überspringbar; tiefer nachgesehen werden muss bei den Credential-Wegen in Phase 23 (Provisionierung einer vorab gebundenen Autorisierung ist dokumentiert, aber nicht gemessen) und beim Nachweis in Phase 24 (Header-Größe eines echten Keycloak-Tokens über HaRP ist ungemessen).

---
*Roadmap created: 2026-08-14 (granularity: coarse, mode: mvp); v1.0 abgeschlossen: 2026-08-20; v1.1 abgeschlossen: 2026-08-20 (Phase 7 deferred); v1.2 abgeschlossen: 2026-08-25 (Release 0.1.8 live); v1.3 abgeschlossen: 2026-08-26 (Release 0.1.9 live); v1.4 abgeschlossen: 2026-08-28 (Release 0.1.10 live); v1.5 abgeschlossen: 2026-08-31 (Release 0.1.11, openDesk-Spike, Audit-Log; Abschluss nachgetragen 2026-09-18); v1.6 aufgesetzt: 2026-09-18 (Phasen 20-24, 15 Requirements, granularity coarse)*

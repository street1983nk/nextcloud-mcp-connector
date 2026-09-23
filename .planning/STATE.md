---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: F13 Token Exchange Identity Mapper
status: "Phase 23 ist abgeschlossen und verifiziert (9/9): Claim-Mapping mit zwei Profilen auf den kanonischen Principal (23-01), die Exchange-Identitaet mit Gleichlauf von Pausenschalter, Audit und Sweep (23-02), AppAPI-Impersonation fail-closed (23-03), die gebundene Kontoquelle des Standalone-Betriebs (23-04), das Enrollment in drei Schritten (23-05) und die Seite zum Sehen und Widerrufen mit gemessenem 200-dann-401 (23-06); als Naechstes Phase 24 (Audit-Anschluss und Nachweis)
stopped_at: Completed 22-03-PLAN.md
last_updated: "2026-09-19T09:57:18.141Z"
last_activity: 2026-09-19, Plan 22-03 ausgeführt (2 Tasks, TDD, alle Gates grün), EXCH-05 komplett, der Exchange-Pfad ist vor-authentisch gedrosselt
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 7
  completed_plans: 7
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-21)

**Core value:** Die zugänglichste und sauberste MCP-Anbindung für Nextcloud: per Klick installierbar, spec-konformes OAuth statt App-Passwort-Gebastel, und der Assistent sieht niemals mehr als der angemeldete Nutzer.
**Current focus:** v1.6 F13 Token Exchange Identity Mapper, Phasen 20-24; Roadmap steht, als Nächstes die Planung von Phase 20 (JWKS-Schicht und PyJWT-Stand)

## Current Position

Phase: 23 von 24 (v1.6: Phasen 20-24), ABGESCHLOSSEN (fuenf Wellen), verifiziert 9/9
Plan: 6 von 6 abgeschlossen (23-01/23-02 MAP-01, 23-03 MAP-02+CRED-01, 23-04 bis 23-06 CRED-02)
Status: Phase 23 komplett und goal-backward verifiziert (23-VERIFICATION.md, result passed, 9/9): getauschte Tokens handeln unter einem existierenden Konto, in beiden Betriebsarten, ohne neue Vollmacht und ohne stille Kontoanlage; als Naechstes Phase 24 (Audit-Anschluss und Nachweis)
Progress: [██████████] 100%
Last activity: 2026-09-23, Phase 23 ausgefuehrt (6 Plaene, 5 Wellen, TDD, 4162 Tests gruen) und verifiziert (passed, 9/9); am selben Tag drei Quick-Tasks (BL-15, BL-17, BL-01) abgeschlossen

## Performance Metrics

**Velocity:**

- Total plans completed: 125
- Average duration: 35 min
- Total execution time: 15.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 14 | - | - |
| 2 | 7 | 254 min | 36 min |
| 3 | 8 | 400 min | 50 min |
| 4 | 2 | 85 min | 43 min |
| 05 | 16 | - | - |
| 6 | 11 | - | - |
| 8 | 5 | - | - |
| 9 | 5 | - | - |
| 10 | 8 | - | - |
| 12 | 4 | - | - |
| 13 | 6 | - | - |
| 14 | 2 | - | - |
| 15 | 4 | - | - |
| 18 | 10 | - | - |
| 19 | 9 | - | - |
| 20 | 2 | 49 min | 25 min |
| 22 | 1 | 25 min | 25 min |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01-server-kern P01 | 24 min | 3 tasks | 10 files |
| Phase 01-server-kern P02 | 18 min | 3 tasks | 21 files |
| Phase 01-server-kern P12 | 14 min | 3 tasks | 2 files |
| Phase 01-server-kern P03 | 25 min | 3 tasks | 10 files |
| Phase 01-server-kern P04 | 20 min | 3 tasks | 12 files |
| Phase 01-server-kern P06 | 27 min | 2 tasks | 13 files |
| Phase 01-server-kern PP07 | 34 min | 3 tasks | 13 files |
| Phase 01-server-kern P08 | 25 min | 2 tasks | 10 files |
| Phase 01-server-kern P05 | 16 min | 2 tasks | 13 files |
| Phase 01-server-kern P09 | 13 min | 2 tasks | 10 files |
| Phase 01-server-kern P10 | 15 min | 2 tasks | 12 files |
| Phase 01-server-kern P11 | 74 min | 2 tasks | 11 files |
| Phase 01-server-kern P14 | 71 min | 3 tasks | 13 files |
| Phase 02-exapp-shell P01 | 30 min | 3 tasks | 15 files |
| Phase 02-exapp-shell P02 | 15 min | 3 tasks | 10 files |
| Phase 02-exapp-shell P03 | 32 min | 3 tasks | 8 files |
| Phase 02-exapp-shell P04 | 63 min | 3 tasks | 10 files |
| Phase 02-exapp-shell P05 | 14 min | 3 tasks | 5 files |
| Phase 02-exapp-shell P06 | 45 min | 2 tasks | 3 files |
| Phase 02-exapp-shell P07 | 55 min | 3 tasks | 6 files |
| Phase 03 P01 | 65 min | 3 tasks | 15 files |
| Phase 03 P03 | 20 min | 2 tasks | 6 files |
| Phase 03 P02 | 95 min | 3 tasks | 15 files |
| Phase 03 P04 | 25 min | 3 tasks | 14 files |
| Phase 03 P05 | 35 min | 3 tasks | 14 files |
| Phase 03 P06 | 40 min | 3 tasks | 16 files |
| Phase 03 P07 | 40 min | 3 tasks | 11 files |
| Phase 03 P08 | 80 min | 3 tasks | 11 files |
| Phase 04 P01 | 60 min | 2 tasks | 7 files |
| Phase 04 P02 | 25 min | 3 tasks | 5 files |
| Phase 04 P03 | 70 | 3 tasks | 11 files |
| Phase 4 P04 | 90 min | 2 tasks | 6 files |
| Phase 05 P01 | 14 min | 2 tasks tasks | 6 files files |
| Phase 05 P03 | 25 min | 2 tasks | 5 files |
| Phase 05 P02 | 20 min | 2 tasks tasks | 8 files files |
| Phase 05 P04 | 18 min | 2 tasks | 7 files |
| Phase 05 P05 | 25 min | 2 tasks | 3 files |
| Phase 05 P06 | 25 min | 2 tasks tasks | 12 files files |
| Phase 05 P07 | 75 min | 3 tasks tasks | 4 files files |
| Phase 05 P09 | 15 min | 2 tasks tasks | 6 files files |
| Phase 05 P08 | 60 min | 3 tasks tasks | 9 files files |
| Phase 05 P10 | 30 min | 3 tasks | 8 files |
| Phase 05 P11 | 35 min | 2 tasks tasks | 5 files files |
| Phase 05 P12 | 20 min | 2 tasks tasks | 1 file files |
| Phase 05 P15 | 30 min | 2 tasks tasks | 5 files files |
| Phase 05-hardening-und-store-einreichung P16 | 20 | 2 tasks | 3 files |
| Phase 05-hardening-und-store-einreichung P13 | 15 min | 2 tasks tasks | 4 files files |
| Phase 05-hardening-und-store-einreichung P14 | 25 min | 2 tasks | 2 files |
| Phase 06 P01 | 30 min | 2 tasks | 4 files |
| Phase 06 P03 | 25 min | 3 tasks tasks | 6 files files |
| Phase 06 P02 | 40 min | 3 tasks | 2 files |
| Phase 06 P04 | 20 min | 2 tasks tasks | 6 files files |
| Phase 06 P05 | 35 min | 2 tasks | 7 files |
| Phase 06 P06 | 40 min | 3 tasks | 7 files |
| Phase 06 P07 | 45 min | 3 tasks tasks | 9 files files |
| Phase 06 P08 | 35 min | 2 tasks | 6 files |
| Phase 06 P09 | 50 min | 3 tasks tasks | 6 files files |
| Phase 06 P10 | 30 | 3 tasks | 5 files |
| Phase 06 P11 | 30 min | 3 tasks | 8 files |
| Phase 08-erreichbarkeits-spike-und-tables P01 | 42 min | 3 tasks tasks | 4 files files |
| Phase 08-erreichbarkeits-spike-und-tables P02 | 12 min | 3 tasks | 9 files |
| Phase 08 P03 | 12 min | 3 tasks | 3 files |
| Phase 08 P04 | 18 min | 3 tasks | 14 files |
| Phase 08 P05 | 24 min | 2 tasks tasks | 5 files files |
| Phase 09-talk P01 | 20 min | 3 tasks | 8 files |
| Phase 09-talk P02 | 17 min | 3 tasks tasks | 12 files files |
| Phase 09-talk P03 | 26 min | 3 tasks | 3 files |
| Phase 09-talk P04 | 33 min | 3 tasks | 15 files |
| Phase 09-talk P05 | 29 min | 3 tasks tasks | 6 files files |
| Phase 10-mail P01 | 42 min | 3 tasks tasks | 3 files files |
| Phase 10-mail P02 | 17 min | 3 tasks tasks | 5 files files |
| Phase 10-mail PP03 | 25 min | 3 tasks tasks | 5 files files |
| Phase 10-mail P04 | 22 min | 3 tasks | 3 files |
| Phase 10 P05 | 20min | 3 tasks | 5 files |
| Phase 10 P06 | 15 min | 3 tasks tasks | 7 files files |
| Phase 10 P07 | 13min | 3 tasks | 8 files |
| Phase 10 P08 | 22 min | 2 tasks tasks | 2 files files |
| Phase 11 P01 | 25min | 2 tasks | 4 files |
| Phase 11 P02 | 22 min | 2 tasks tasks | 3 files files |
| Phase 11 P03 | 34 min | 3 tasks tasks | 5 files files |
| Phase 11 P04 | 20 min | 3 tasks tasks | 2 files files |
| Phase 11 P05 | 17 min | 3 tasks tasks | 4 files files |
| Phase 11 P06 | 27 min | 2 tasks tasks | 3 files files |
| Phase 11 P07 | 19 min | 2 tasks tasks | 5 files files |
| Phase 11 P08 | 30 min | 3 tasks tasks | 9 files files |
| Phase 11 P09 | 25 min | 3 tasks | 6 files |
| Phase 11 P10 | 20 min | 4 tasks | 2 files |
| Phase 12 P01 | 9 min | 2 tasks tasks | 4 files files |
| Phase 12 P02 | 10 min | 2 tasks | 4 files |
| Phase 12 P03 | 21 min | 3 tasks tasks | 3 files files |
| Phase 12 P04 | 18 min | 3 tasks tasks | 7 files files |
| Phase 13 P01 | 12 min | 2 tasks tasks | 8 files files |
| Phase 13 P02 | 8min | 3 tasks | 6 files |
| Phase 13 P03 | 40 min | 3 tasks tasks | 2 files files |
| Phase 13 P04 | 12 min | 2 tasks | 1 files |
| Phase 13 P05 | 13 min | 3 tasks tasks | 1 file files |
| Phase 13 P06 | 12 min | 3 tasks | 1 file |
| Phase 14 P01 | 3 min | 2 tasks tasks | 4 files files |
| Phase 14 P02 | 6 min | 3 tasks tasks | 3 files files |
| Phase 15 P01 | 8 min | 2 tasks | 8 files |
| Phase 15 P02 | 20 min | 2 tasks | 1 files |
| Phase 15 P03 | 12 min | 3 tasks | 1 files |
| Phase 16-release-0-1-11 P01 | 7 min | 2 tasks | 8 files |
| Phase 16-release-0-1-11 P02 | 11 min | 2 tasks | 1 files |
| Phase 16-release-0-1-11 P03 | 9 min | 3 tasks | 1 files |
| Phase 17-opendesk-spike P01 | 18 min | 3 tasks tasks | 1 file files |
| Phase 17 P02 | 74 min | 3 tasks | 6 files |
| Phase 17 P03 | 48 | 3 tasks | 3 files |
| Phase 17 P04 | 41 min | 3 tasks | 2 files |
| Phase 17 P05 | 78 | 3 tasks | 2 files |
| Phase 17 P06 | 52 | 3 tasks | 2 files |
| Phase 17 P07 | 64 min | 3 tasks | 5 files |
| Phase 17 P08 | 20 | 3 tasks | 3 files |
| Phase 17 P09 | 35 min | 3 tasks | 1 files |
| Phase 18-audit-log-kern P01 | 20 min | 3 tasks tasks | 4 files files |
| Phase 18-audit-log-kern P02 | 15 min | 2 tasks tasks | 3 files files |
| Phase 18-audit-log-kern P03 | 25 min | 3 tasks | 10 files |
| Phase 18-audit-log-kern PP04 | 20 min | 3 tasks tasks | 4 files files |
| Phase 18-audit-log-kern P05 | 12 min | 3 tasks | 5 files |
| Phase 18 P06 | 28min | 3 tasks | 5 files |
| Phase 18 P07 | 50min | 3 tasks | 10 files |
| Phase 18 P08 | 55min | 3 tasks | 10 files |
| Phase 18 P09 | 62min | 3 tasks | 6 files |
| Phase 18 P10 | 45min | 3 tasks | 3 files |
| Phase 19 P01 | 22 min | 3 tasks | 7 files |
| Phase 19 P02 | 20 min | 2 tasks | 2 files |
| Phase 19 P03 | 24 min | 2 tasks | 1 files |
| Phase 19 P04 | 16 min | 2 tasks | 3 files |
| Phase 19 P05 | 19 min | 3 tasks | 4 files |
| Phase 19 P06 | 24 min | 3 tasks | 3 files |
| Phase 19 P07 | 25 min | 3 tasks | 5 files |
| Phase 19 P08 | 17 min | 2 tasks | 5 files |
| Phase 19 P09 | 12 min | 2 tasks | 1 files |
| Phase 20-jwks-schicht-und-pyjwt-stand P01 | 16 min | 2 tasks | 3 files |
| Phase 20 P01 | 16 min | 2 tasks | 3 files |
| Phase 20 P02 | 33 min | 3 tasks | 3 files |
| Phase 21-exchange-verifier P01 | 28 min | 3 tasks | 3 files |
| Phase 21-exchange-verifier P02 | 20 min | 2 tasks | 2 files |
| Phase 22 P02 | 35 | 3 tasks | 11 files |
| Phase 22 P03 | 21 min | 2 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 21]: audience ist in ExchangeSettings genau eine Zeichenkette und nie eine Liste, damit der erwartete Wert beim Vergleich in 21-02 nie zur Oder-Verknüpfung werden kann; azp_allowed steht validiert in den Settings, seine Prüfung baut 21-02 (21-01)
- [Phase 21]: der typ-Claim wird im Payload geprüft (Bearer gegen ID), der Header-typ wird toleriert (JWT/at+jwt ohne Gross-Klein) und nie verlangt, weil Keycloak den Header je nach Client-Alter setzt (Diskussion 19419); der Grund steht als Kommentar im Modul, damit niemand die Prüfung später auf at+jwt im Header "korrigiert" (21-01)
- [Phase 21]: der Prüfer führt zwei getrennte, injizierbare Uhren (monotone Uhr nur an das KeySet, Wanduhr nur für Lebensdauer- und Altersregel) und einen iss-Vorfilter auf dem ungeprüften Payload, der nur ablehnen kann und null ausgehende JWKS-Abrufe für fremde Issuer garantiert (per respx call_count gemessen); Toleranz 30 s, maximale Lebensdauer und maximales Alter 900 s, Abweisung statt Kürzung (21-01)
- [Phase 20]: die Abkühlzeit der herausgelösten Schlüsselsatz-Schicht steht auf 60 Sekunden statt der 30 von PyJWT 2.14, weil der Pfad ab Phase 21 vor-authentisch erreichbar ist (PITFALLS Pitfall 5); der Wert ist als `cooldown_seconds` je Instanz stellbar, damit Phase 22 ihn an die Konfiguration hängen kann, ohne die Schicht anzufassen; der Stempel wird vor dem ausgehenden Abruf gesetzt, damit ein langsamer Anbieter das Fenster nicht verlängert (20-02)
- [Phase 20]: `oauth/jwks.py` definiert keine eigene Ausnahme; der Aufrufer gibt seine Abweisungsfabrik (`refuse`) herein, `OidcClient` reicht `_refused` durch, und Ausnahmetyp und Logtext des OIDC-Flusses bleiben exakt die von vorher; Verhaltensgleichheit belegt durch byte-identische `tests/unit/test_oauth_oidc.py` (20-02)
- [Phase 20]: der Single-Flight-Versuchszähler bewegt sich erst nach Abschluss eines Abrufversuchs (Erfolg wie Fehlschlag): nur so teilt ein Wartender, der während des Flugs ankommt, den Fehlschlag statt einen zweiten Abruf zu starten; das Schliessen der Antwort läuft über `aclosing` statt `finally`, damit die "auf dem Rückweg schreiben"-Form (GHSA-fhv5-28vv-h8m8) im Modul nicht vorkommt (20-02)
- [Milestone v1.6]: die Roadmap folgt der von drei Recherchen unabhängig gestützten Baureihenfolge (Schlüsselsatz-Herauslösung, fremder Prüfer, Konfiguration samt Kette, Credential-Wege, Audit und Nachweis) und fasst sie bei granularity coarse zu fünf Phasen zusammen; die P0-Credential-Frage ist mit D-v1.6-01 (Weg A und B kombiniert) vor der ersten Codezeile entschieden und deshalb keine eigene Phase
- [Milestone v1.6]: DEP-01 (PyJWT >=2.14,<3) liegt in Phase 20 und nicht am Ende, weil die Sicherheitsfreigabe vom 11.09.2026 genau den Schlüsselsatz-Pfad betrifft, der dort herausgelöst wird
- [Phase 19]: der wartende Textrest der Phase steht in einem NEU angelegten `[Unreleased]`-Block über dem Eintrag zu 0.1.11 (Phase 16 hatte den vorigen Block in diesen Eintrag überführt, die Datei begann danach direkt mit 0.1.11): drei Added-Punkte, vier Changed-Punkte, zwei Fixed-Punkte, eine Linkdefinition auf `compare/v0.1.11...HEAD`; kein Release-Eintrag ist angefasst, weil ein Release-Eintrag ein Datum ist (19-09, T-19-37, Diff 62 Einfügungen und 0 Löschungen)
- [Phase 19]: der Deaktivieren-Aktivieren-Zyklus ist ein eigener Changelog-Punkt und kein Nebensatz: er ist die einzige Aussage des Blocks, die eine Handlung verlangt, und ohne ihn sieht eine bestehende Installation weder das neue Kommando noch die neue Beschriftung (19-09)
- [Phase 19]: ein Urteil in einer Nachweistabelle ist `gemessen` oder `hergeleitet`, und wo der Kern am Baum gemessen, die Aussage über eine laufende Instanz aber nicht messbar ist, folgt das Urteil dem schwächeren Teil; drei Punkte sind ausdrücklich hergeleitet (Erscheinen des Kommandos in `occ list`, Ausbleiben einer Optionsnamen-Kollision, Sichtbarkeit der neuen Beschriftung), Präzedenz R-18-05 (19-09, T-19-38)
- [Phase 19]: der Enterprise-Absatz steht an sechs Stellen (drei Manifestbeschreibungen und drei READMEs) in ZWEI Absätzen statt einem: der erste sagt, dass das Protokoll der Werkzeugaufrufe Teil dieser App ist, ab Werk aus, über die Admin-Einstellungen eingeschaltet, mit `occ mcp_connector:audit:read` gelesen und mit `occ mcp_connector:audit:verify` geprüft wird; der zweite behält das Wort "geplant" für Gruppen-Policies und die Anmeldung über den Identitätsanbieter. Die Trennung ist nicht Typografie, sondern die Bedingung, unter der ein Test zeilenweise verbieten kann, dass das Audit-Log wieder als geplant bezeichnet wird (19-08, T-19-31)
- [Phase 19]: sechs Fundstellen einer öffentlichen Aussage werden durch eine Liste plus Test zusammengehalten und nicht durch Sorgfalt: `ENTERPRISE_MARKERS` trägt je Sprache ein Markertripel (EN "audit log"/"off by default"/"group policies", DE "Audit-Log"/"ab Werk aus"/"Gruppen-Policies", FR "journal d'audit"/"désactivé par défaut"/"politiques de groupe"), `enterprise_section` schneidet den Abschnitt unter seiner Überschrift heraus, und die Marker werden gegen den auf einfache Leerzeichen geglätteten Abschnitt geprüft, weil eine README ihre Zeilen umbricht (19-08)
- [Phase 19]: die Enterprise-Positionierung verspricht Leistung und nicht Zugang, weil die App unter AGPL-3.0 offen liegt und das Protokoll Teil davon ist; die grössere Lizenzfrage bleibt OD-03 auf der Fragenliste des ISV-Calls und wird nicht im Store-Text beantwortet (19-08, T-19-33 accept)
- [Phase 19]: kein Optionsmodus eines occ-Kommandos verlässt die Positivliste `required`, `optional`, `none`, und kein Kommando registriert ein Argument; die Regel steht als Test über alle Schemata im Repo, weil `appinfo/register_command.php` von app_api beim Start JEDES occ-Aufrufs alle ExApp-Kommandos baut und nur Container-Ausnahmen fängt: ein abgelehnter Modus kostet die occ-Kommandozeile der ganzen Instanz (19-07, T-19-26)
- [Phase 19]: das Lesekommando hat eine eigene JSON-Beschreibung statt der des Prüfkommandos, weil die Maschinenform hier zugleich die Übergabe aus AUDIT-04 ist und die Kettenreihenfolge trägt; die Zahlen der Optionsbeschreibungen (200, 5000, 3650) werden aus den Konstanten hineinformatiert und nie abgeschrieben (19-07)
- [Phase 19]: die drei Audit-Umgebungsvariablen sind im Manifest deklariert, jede ohne `default`; der Hauptweg bleibt das Admin-Formular (BL-06), aber eine öffentlich beschriebene Grenze, die der Deploy-Daemon wortlos verwirft, wäre eine halbe Zusage (19-07, deferred item aus 18-07 geschlossen)
- [Phase 19]: harte Zahlen in Registrierungstests lesen ab jetzt `len(occ.command_schemes())`; `test_both_commands_failing_...` trug die Zahl sogar im Namen und heisst jetzt `test_every_command_failing_...` (19-07)
- [Phase 19]: das Lesekommando ist EIN Kommando `mcp_connector:audit:read` mit einer Maschinenform und nicht zwei Kommandos, und die Maschinenform ist EIN JSON-Dokument über `json_response` statt JSONL, gegen die Empfehlung der Recherche: `json_response` samt `NO_STORE` ist die etablierte Maschinenform dieses Projekts; CSV oder JSONL können später Werte einer `--format`-Option werden (19-06)
- [Phase 19]: die Textform des Lesekommandos zeigt die neuesten Einträge zuerst, die Maschinenform die Kettenreihenfolge (`reversed`); die Umkehrung steht im Handler, weil der Speicher immer die jüngsten zuerst liefert (19-06, Fortschreibung von 19-04)
- [Phase 19]: `limit_applied` wird im Handler gegen die importierte Konstante `READ_LIMIT_MAX` geklemmt und nicht nur im Speicher, sonst stünde bei `--limit 999999` eine Zahl im Kopf, die die Antwort nie erreicht, und `truncated` wäre falsch (19-06)
- [Phase 19]: `--user instance` adressiert die Instanzkette, weil sie kein Konto hat; der Preis (ein Konto namens `instance` ist über diese Option nicht adressierbar) steht im Docstring, und `--since` nimmt ganze Tage und niemals ein Datum, weil eine Zahl prüfbar ist und ein Datum nicht (19-06)
- [Phase 19]: die Ausgabeform wird im selben `try` gebaut wie die Abfrage, weil eine Zeile aus einer manipulierten Datei beim Rendern wirft und eine 500 die Antwort verschluckt (T-18-20); `_moment` und `_hex` sind zusätzlich total (19-06)
- [Phase 19]: die verengte Formulierung aus D-v1.5-01 ("die Aufbewahrungsfrist ist der einzige automatische Löscher") steht in keinem Nutzertext; `docs/privacy.md` nennt alle drei Löschwege mit ihren Zahlen (180 Tage Vorgabe, 100 MB Obergrenze, Konto seit 30 Tagen stumm), und ein Testfall hält die Wendung "the only automatic" aus allen drei Doku-Seiten heraus (19-05, T-19-15)
- [Phase 19]: jede Zahl eines öffentlichen Textes wird im Test aus der Codekonstante formatiert und nie als Literal wiederholt; `tests/unit/test_docs_audit_truth.py` bindet `docs/privacy.md`, `docs/uninstall.md` und `docs/faq.md` an `RETENTION_DAYS`, `SIZE_LIMIT_BYTES`, `USER_SILENCE_DAYS` und `AUDIT_FILENAME` (19-05)
- [Phase 19]: `docs/uninstall.md` ist ein Messprotokoll mit Datum, also bekommt ein später ergänzter Pruefschritt keine erfundene Messzahl: Check 5 sagt ausdrücklich, dass er die auszuführende Form ist, und nennt beide richtigen Antworten (eine Zeilenzahl oder eine fehlende Datei); R-18-04 damit geschlossen (19-05)
- [Phase 19]: `docs/faq.md` ist über CONTEXT hinaus mitgezogen (Assumption A5), weil die completely-Antwort denselben falschen Purge-Satz trug wie `docs/privacy.md` (19-05)
- [Phase 19]: `AuditStore.read_entries` gibt rohe Tupel heraus und keine `Entry`-Objekte, weil `Entry` `seq`, `prev_hash` und `hash` absichtlich nicht trägt und eine Ausgabezeile ohne Nummer nicht nachvollziehbar ist; der Aufrufer nimmt `_entry_of_row(row)`, `row[0]`, `row[-2]` und `row[-1]` (19-04)
- [Phase 19]: sortiert wird `ORDER BY seq DESC` und nie nach `at`, weil `at` die Wanduhr beim Schreiben ist und nach einem Zeitsprung nicht monoton (WR-02); die Richtung ist immer neueste zuerst, weil `ORDER BY seq ASC LIMIT ?` die ältesten Zeilen liefern würde, und die Umkehrung für einen Export gehört in den Handler von 19-06
- [Phase 19]: das Leselimit ist an beiden Enden geklemmt (`max(1, min(limit, READ_LIMIT_MAX))`, Vorgabe 200, Höchstwert 5000): ein negatives `LIMIT` liest SQLite als kein Limit, und AppAPI wartet mit `timeout => 0`, also deckelt von aussen nichts (T-19-12)
- [Phase 19]: die vier verbotenen Ansprüche (revisionssicher, AI-Act-konform, DSGVO-konform, SIEM-zertifiziert) stehen als vier Muster in EN, DE und FR neben `FORBIDDEN_VOCABULARY` in `tests/unit/test_exapp_env_setup.py`, mit der Reichweite des Vokabular-Gates plus dem Manifesttext; verboten ist die Behauptung und nicht das Wort, weshalb "SIEM-Ausleitung", "specification compliant" und "conforme à la spécification" als Negativfälle festgeschrieben sind (T-19-08, T-19-10)
- [Phase 19]: eine Gegenprobe, die über eine Verbotsliste schleift, nennt die Länge der Liste als erste Behauptung; ohne sie besteht sie eine geleerte Liste kommentarlos, gemessen in 19-03 (T-19-09)
- [Phase 19]: die Grenzbeschreibung des Audit-Schalters ist inhaltlich und nicht wörtlich an `exapp/audit_verify.LIMIT_SENTENCE` gebunden; gehalten werden die zwei tragenden Begriffe "changed or removed unnoticed" und "recompute", weil das Formular vor der Entscheidung spricht und die Konsole nach der Prüfung, und ein Test hält beide Orte gegeneinander (T-19-06)
- [Phase 19]: die Beschriftung nennt alle drei automatischen Löschwege (Frist 180 Tage, Obergrenze 100 MB, Kontolöschung in Nextcloud) und erklärt keinen davon zum einzigen; die verengte Formulierung aus D-v1.5-01 wäre am Code falsch, die Korrektur steht in 19-CONTEXT.md
- [Phase 19]: das Wort einer zweiten Inhaltsstufe ist an der Oberfläche als Wortform mit Wortgrenzen verboten, nicht als Substring, und `src/mcp_connector/exapp/ui/strings.py` trägt es seit 19-02 an keiner Stelle mehr, auch nicht in einem Kommentar
- Roadmap v1.5: Phasennummerierung setzt bei 16 fort (v1.4 verbrauchte 14 und 15); vier Phasen bei Granularität coarse, weil der Meilenstein zwei fast unabhängige Stränge plus ein fertiges Release trägt
- Roadmap v1.5: KEINE Entscheidungsphase, obwohl die Recherche eine vorschlägt; die vier Owner-Entscheidungen D-v1.5-01 bis D-v1.5-04 stehen bereits oben in REQUIREMENTS.md und werden in der Planung nicht wieder aufgemacht
- Roadmap v1.5: die offene Architekturfrage aus SUMMARY.md (Weg 0 über `integration_openproject` gegen Weg 1 als eigener OAuth-Client) wird von der Roadmap NICHT vorentschieden; sie fällt in Phase 17 auf der Messung in OD-02
- Roadmap v1.5: Phase 16 (Release 0.1.11) liegt vor Phase 19, weil beide dieselben Textstellen anfassen (CHANGELOG.md, info.xml, Versionszeichenketten); der `[Unreleased]`-Block muss geleert sein, bevor AUDIT-06 ihn wieder füllt, sonst führte 0.1.11 Text über ein Modul mit, das es beim Upload nicht gibt
- Roadmap v1.5: Phase 17 (Spike) und Phase 18 (Audit-Log Kern) hängen an nichts und laufen parallel zu Phase 16; die einzige echte Serialisierung ist Phase 19
- Roadmap v1.5: OD-01, OD-02 und OD-03 liegen in EINER Spike-Phase statt in dreien (Recherche-Vorschlag), weil keiner der drei Produktionscode erzeugt; die Reihenfolge Installierbarkeit vor Auth-Frage ist Phaseninterna, kein Phasenschnitt
- Roadmap v1.5: das Audit-Log ist auf zwei Phasen geschnitten, weil Phase 19 ein feststehendes Satzschema und einen feststehenden Speicher braucht, bevor gelesen, geschaltet und beschrieben werden kann
- Roadmap v1.5: EXAPP-12 (Auslieferung des Audit-Logs als 0.1.12) ist per Owner-Entscheid Future Requirement und in keiner Phase abgebildet; die AUDIT-06-Texte warten im `[Unreleased]`-Block, ohne Tag und ohne Store-Upload
- Roadmap v1.5: kein Feature dieses Meilensteins fasst die Werkzeugoberfläche an; 15712 von 18000 Bytes über 21 Werkzeuge bleiben stehen, kein Gate-Grenzwert wird angehoben
- [Phase 16]: die Werkzeugoberfläche misst weiter 15712 Bytes über 21 Werkzeuge gegen ein Budget von 18000, byte-gleich zum 0.1.10-Lauf, weil `0.1.10` und `0.1.11` beide sechs Zeichen lang sind; kein Grenzwert wurde angehoben, das lokal gebaute Store-Paket hat 47349 Bytes und wird nicht signiert
- [Phase 16]: der Tag v0.1.11 steht auf 504de6c und ist irreversibel; ab hier kein `git tag -f`, kein Force-Push und kein Löschen eines Release-Assets, weil AppAPI von der Asset-URL installiert und nicht aus dem Store
- [Phase 16]: das veröffentlichte Asset misst 47046 Bytes bei sha256 `e4b570c0…`, das lokal gebaute 47349 bei `df5a9ca9…`; die Differenz ist erwartet, weil `tar.gz` nicht bytereproduzierbar ist, und Plan 16-04 signiert ausschließlich das Heruntergeladene
- [Phase 16]: die Owner-Freigabe für den Tag lag vor 09:36:25Z, ist aber nicht auf die Minute festgehalten, weil sie als Weitergabe im Planauftrag ankam statt als wörtliches Zitat; für das nächste Release wird sie im Moment der Freigabe mit UTC-Stempel notiert
- Roadmap v1.5: für EXAPP-11 gelten die Release-Regeln unverändert (Versionszeichenkette an sechs Stellen, Changelog-Block samt Linkdefinition, Branch-Push vor dem Tag, Tag nur nach wörtlicher Owner-Freigabe, Signatur über das heruntergeladene Asset, datierte Proof-Zeilen in docs/store-submission.md)

- Roadmap v1.4: Phasennummerierung setzt bei 14 fort (v1.3 verbrauchte 12 und 13); zwei Phasen bei Granularität coarse, weil das Release die Doku-Fixes im Asset mitnehmen muss und deshalb zwingend nach ihnen liegt
- Roadmap v1.4: DOC-01, DOC-02 und SEC-03 liegen in einer Phase, weil alle drei reine Text- und Gate-Nacharbeiten ohne gegenseitige Abhängigkeit sind und eine Aufteilung nur Reibung erzeugt
- Roadmap v1.4: EXAPP-10 ist die einzige Anforderung der Release-Phase; Gates bleiben 18000/1400 bei 21 Tools, Tag v0.1.10 nur nach ausdrücklicher Owner-Freigabe, Branch-Push vor dem Tag, Signatur über das heruntergeladene Asset (Runbook-Muster 0.1.9)

- Roadmap v1.3: Phasennummerierung setzt bei 12 fort (v1.2 verbrauchte 8 bis 11); zwei Phasen bei Granularität coarse, weil ein reiner Pflege-Milestone keine dritte Naht hat
- Roadmap v1.3: alle vier Code-Schulden (TOOL-17, TOOL-18, TOOL-19, SEC-02) liegen in einer Phase, weil sie dieselben Dateien und dasselbe Gate-Set berühren und eine Aufteilung nur Reibung erzeugt
- Roadmap v1.3: EXAPP-08 (CIMD-Live-Rerun) liegt in der Release-Phase und nicht davor, weil die Nachmessung gegen die Topologie laufen soll, die auch veröffentlicht wird
- Roadmap v1.3: die Gates bleiben auf der v1.2-Messung (BUDGET_BYTES 18000, MAX_TOOL_BYTES 1400); eine Anhebung ist ausdrücklich Out of Scope, `message_truncated` ist die einzige nutzersichtbare Änderung der Phase 12
- Roadmap v1.3: der Tag v0.1.9 entsteht erst nach ausdrücklicher Owner-Freigabe, Branch-Push davor, Signatur über das heruntergeladene Asset (Runbook Schritte 4 bis 8, Erfahrung 0.1.8)

- Roadmap v1.2: Phasennummerierung setzt bei 8 fort (v1.1 verbrauchte 6 und das deferred 7); vier Phasen bei Granularität coarse
- Roadmap v1.2: kein eigener Spike-Phasenkopf; der Mail-Erreichbarkeits-Spike (MAIL-04) ist der erste, blockierende Plan von Phase 8, weil Tables nicht an ihm hängt und die Erkenntnis damit genauso früh fällt
- Roadmap v1.2: die lethal-trifecta-Frage ist per Owner-Entscheid vom 2026-08-21 entschieden (talk_send kommt hinter einen neuen Admin-Schalter, TALK-04) und wird in der Planung nicht wieder aufgemacht
- Roadmap v1.2: SRV-06 liegt in Phase 10 statt Phase 8, weil "alle drei Familien degradieren sauber" erst nachweisbar ist, wenn alle drei Familien Werkzeuge haben
- Roadmap v1.2: SEC-01 liegt in Phase 10 statt in der Release-Phase, weil die Phase, die die Exfiltrationskette schließt, auch ihre Benennung liefern muss; eine später nachgezogene Sicherheitsaussage wäre in der Zwischenzeit unwahr
- Roadmap v1.2: CTX-01, CTX-02 und TOOL-16 bewusst in der letzten Phase gebündelt, weil die Bucket- und Kind-Entscheidungen beide neuen Kinds gleichzeitig sehen müssen und das Budget-Gate erst mit allen fünf Werkzeugen sinnvoll verankert wird

- Roadmap: 6 Research-Phasen auf 5 komprimiert (Kern + Streamable HTTP zusammengelegt); Settings/prepare_context und Hardening/Store getrennt gehalten
- Roadmap: App-ID-Freeze (EXAPP-03) und context_agent#227-Fix (CONTRIB-01) bewusst in Phase 1 (Long-Lead-Risiken früh)
- Roadmap: Discovery-durch-AppAPI-Proxy-Spike (AUTH-06) in Phase 2 als Go/No-Go, BEVOR die OAuth-Phase committet wird
- Roadmap: CSR-PR-Start ist von Phase 5 entkoppelt, startet sobald App-ID + Public Repo existieren
- [Phase 01-server-kern]: httpx2 bleibt ausschliesslich transitive Dependency von mcp: slopcheck [SUS]-Befund; Owner-Freigabe nach Verifikation (pydantic-Org, Tom Christie); eigener Code nutzt httpx, weil respx httpx mockt
- [Phase 01-server-kern]: ruff schliesst .planning/ aus: ruff formatiert Python-Bloecke in Markdown; Research-Dokumente muessen wortgetreu bleiben
- [Phase 01-server-kern]: files_read lehnt nur oberhalb von 2 MiB komplett ab; darunter liefert es eine markierte Teilantwort mit next_offset: Ein harter Abbruch bei 512 KiB wuerde grosse Textdateien unlesbar machen; die Truncation-Markierung schuetzt den Kontext genauso
- [Phase 01-server-kern]: reg_*-Module werden in server/__init__.py per pkgutil automatisch importiert: Jedes Tool-Bundle bekommt seine eigene Registrierungsdatei, damit parallel laufende Plaene keine gemeinsame Datei aendern
- [Phase 01-server-kern]: parse_multistatus lehnt jede DTD im Antwortkoerper ab, nicht nur die Entity-Aufloesung: Nextcloud sendet nie eine DTD; ein DOCTYPE ist damit ein Signal und keine Sonderform, die man tolerieren muesste (XXE, Billion Laughs)
- [Phase 01-server-kern]: Nur SRV-02 wird abgehakt; SRV-03, SRV-05, TOOL-01 und AUTH-01 bleiben Pending: Der Walking Skeleton liefert ein Tool und einen Transport; die vollen Nachweise gehoeren zu Plan 04 (HTTP) und Plan 14 (alle 15 Tools)
- [Phase 01-server-kern]: Repo-Sichtbarkeit option-a: alles oeffentlich inklusive .planning (Owner-Entscheidung, T-01-84 accept)
- [Phase 01-server-kern]: PyPI-Verfuegbarkeit nur ueber die JSON-API und den Simple-Index pruefen: die HTML-Projektseite liefert wegen einer Bot-Challenge auch fuer freie Namen 200
- [Phase 01-server-kern]: TOOL-09 bleibt Pending: der README-Nachweis reicht nicht, die Schreibgrenzen belegt erst der Grep- und Registry-Test in Plan 14
- [Phase 01-server-kern]: Annahme A1 bestaetigt: Nextcloud 34.0.2 antwortet auf PUT mit If-None-Match: * bei existierender Datei mit 412; Laufzeitbeweis gegen nextcloud:34-apache; der geplante PROPFIND-Fallback mit TOCTOU-Restrisiko entfaellt
- [Phase 01-server-kern]: occ-Kommandos mit Passwort laufen ueber 'docker compose exec -e OC_PASS=...', Testnutzer-Passwoerter mindestens 10 Zeichen; Grund: eine auf dem Host gesetzte Variable erreicht den Container nie, und Nextclouds Passwort-Policy lehnt kuerzere Passwoerter ab
- [Phase 01-server-kern]: select_mode nimmt die Header als Keyword dazu: aus dem Environment allein ist stdio nicht erkennbar, denn ein stdio-Prozess hat konstruktionsbedingt keine Header
- [Phase 01-server-kern]: Die Auth-Verdrahtung entsteht beim Bau des MCPServer in server/__init__.py: auth= und token_verifier= sind Konstruktorargumente, ein Moduswechsel ist ein Neustart
- [Phase 01-server-kern]: Im Static-Bearer-Modus bleibt der Nextcloud-Zugang aus dem Env: der Bearer authentifiziert den Aufrufer dieses Servers, er waehlt keinen Nextcloud-Nutzer
- [Phase 01-server-kern]: Die Nextcloud-Basis-URL kommt in jedem Modus aus NC_MCP_URL, nie aus dem Request: ein Client, der das Ziel waehlen koennte, koennte diesen Server samt Credentials auf einen fremden Host richten
- [Phase 01-server-kern]: Der Default-Testlauf deselektiert jetzt auch den matrix-Marker, damit 'uv run pytest' keinen Serverprozess startet
- [Phase 01-server-kern]: AUTH-01 bleibt Pending: Basic-Passthrough und Static Bearer sind unit-getestet, der Remote-Rundlauf mit echtem App-Passwort gegen eine laufende Nextcloud fehlt noch
- [Phase 01-server-kern]: OCS-Aufrufe tragen immer OCS-APIRequest: true und Accept: application/json; getrennte Parser parse_ocs und parse_app_json, weil Notes und Deck nicht im OCS-Envelope antworten
- [Phase 01-server-kern]: notes_search laeuft ueber den Unified-Search-Provider notes: die Notes-REST-API hat keine Search-Route; Titel und Excerpt kommen aus dem Search-Entry, also ein Request statt einem pro Treffer
- [Phase 01-server-kern]: Notiz-IDs werden aus resourceUrl geparst und Treffer ohne numerisches Endsegment uebersprungen; die zurueckgegebene url wird immer aus der konfigurierten Basis-URL gebaut (SSRF-Grenze)
- [Phase 01-server-kern]: Der Capabilities-Cache haelt 60 Sekunden pro (base_url, user), enthaelt keine Credentials und darf jederzeit leer sein; tools/list bleibt statisch
- [Phase 01-server-kern]: 507 behaelt eine eigene Meldung (Speicher voll) statt im generischen 5xx-Zweig zu verschwinden
- [Phase 01-server-kern]: AUTH-01 abgehakt: uvicorn ohne Nextcloud-Konto im Environment legt per HTTP mit dem App-Passwort aus dem Request eine Notiz an und liest sie zurueck
- [Phase 01-server-kern]: Eine per occ deaktivierte App bleibt in /cloud/capabilities sichtbar, bis die Nextcloud neu startet; Degradations-Tests brauchen den Neustart, unser eigener Cache ist nicht die Ursache
- [Phase 01-server-kern]: Recurrence-Expansion laeuft serverseitig per c:expand; das CalDAV-Modul enthaelt keine RRULE-Iteration und kein recurring-ical-events, ein Grep-Test haelt diese Grenze
- [Phase 01-server-kern]: Das halboffene Zeitfenster wird nie korrigiert: ein Termin exakt auf end liegt ausserhalb, ein Verschieben der Grenze wuerde zwei Aufrufer mit demselben Fenster unterschiedliche Ergebnisse sehen lassen
- [Phase 01-server-kern]: Ganztaegige Termine behalten das exklusive Enddatum aus RFC 5545; start gleich end wird auf start plus ein Tag korrigiert, damit kein Termin der Laenge null entsteht
- [Phase 01-server-kern]: calendar_create_event bekommt einen optionalen timezone-Parameter (Abweichung von der Plan-Signatur), weil ein ISO-Offset keine IANA-Zone ist und ohne Zonennamen kein IANA-VTIMEZONE erzeugbar waere
- [Phase 01-server-kern]: Nach dem Event-PUT wird einmal per GET nachgelesen; scheitert das Nachlesen, bleibt created true und confirmed false, damit das Modell den Termin nicht ein zweites Mal anlegt
- [Phase 01-server-kern]: Faellt ein einzelner Kalender aus, erscheint er als degraded-Eintrag; fallen alle aus, ist das ein Fehler und keine leere Terminliste
- [Phase 01-server-kern]: Generierte Adressbuecher (z-server-generated--, z-app-generated--) zaehlen nicht als Adressbuecher des Nutzers; sonst waere 'kein Adressbuch' auf jedem echten Server unerreichbar und eine Namenssuche wuerde das Kontenverzeichnis der Instanz mitliefern
- [Phase 01-server-kern]: contacts_search bleibt rein lesend, es gibt keinen CardDAV-Schreibpfad in Phase 1; D-07 plus T-01-57; ein Grep-Test haelt das Modul frei von schreibenden Methoden
- [Phase 01-server-kern]: Cursor-Handles sind unsigniert und tragen nur Offset, Suchbegriff und Ordner: sie enthalten kein Geheimnis und keine Autoritaet, die Credentials kommen pro Aufruf aus dem Auth-Kanal (T-01-33)
- [Phase 01-server-kern]: Ein Handle aus einer anderen Suche oder einem anderen Ordner wird abgelehnt statt still auf die falsche Seite angewendet
- [Phase 01-server-kern]: files_search behaelt die Serverreihenfolge (Folgeseiten entstehen aus groesserem d:limit plus Slice); files_list sortiert selbst, Ordner zuerst, dann Name
- [Phase 01-server-kern]: propfind_children erkennt den Ordner selbst am Pfad statt an der Position und gibt ihn mit zurueck, damit ein Dateipfad ohne zweiten Request erklaert werden kann
- [Phase 01-server-kern]: Das note-Feld 'matched on names only; contents are not indexed' steht in jeder Suchantwort, nicht nur bei null Treffern (Pitfall 5, gegen NC 34 verifiziert)
- [Phase 01-server-kern]: canCreateBoards false beendet deck_create_card nicht sofort, sondern loest eine Pruefung der Board-Rechte aus; canCreateBoards regelt in Deck nur neue Boards; ein Nutzer ohne dieses Recht kann Schreibrechte auf einem geteilten Board haben, eine woertliche Ablehnung waere falsch negativ
- [Phase 01-server-kern]: deck_browse ist ein Tool mit Literal-Enum level statt drei Tools; level=cards kostet genau einen Request; D-06 plus Token-Budget und Client-Slots; GET /boards/{id}/stacks liefert die Karten bereits mit, ein Request pro Stack waere N+1
- [Phase 01-server-kern]: Deck-API-Version 1.0 statt 1.1 und numerische Pflicht fuer alle Pfad-Ids; 1.1 bringt nur Attachment-Typen, 1.0 laeuft auf mehr Instanzen; nicht numerische Ids kaemen aus Modell-Eingaben direkt in den URL-Pfad (T-01-63)
- [Phase 01-server-kern]: unified_search liest die Provider-Liste bei jedem Aufruf frisch von der Instanz und cacht sie nicht: die Provider-Landschaft haengt an installierten Apps, eine hardgecodete Liste wuerde eine App verpassen oder eine erfinden
- [Phase 01-server-kern]: Unbekannte Provider und unbrauchbare resourceUrls ergeben kind url plus resolvable false statt einer geratenen Zuordnung; der Kalender-Provider bleibt bewusst draussen, weil seine resourceUrl keinen DAV-Objektnamen traegt
- [Phase 01-server-kern]: Ausgefallene, zu langsame und unbekannt angefragte Provider erscheinen namentlich im degraded-Feld; null Provider auf der Instanz ist dagegen ein Fehler mit Ausweg, weil eine leere Trefferliste dort eine Luege waere
- [Phase 01-server-kern]: providers ist ein kommaseparierter String statt einer Liste: ein Listen-Parameter erzeugt ein anyOf aus array und null im Input-Schema (Schema-Diaet)
- [Phase 01-server-kern]: pytest laeuft im Import-Modus importlib, weil Unit- und Integrationsebene denselben Testdateinamen tragen duerfen sollen
- [Phase 01-server-kern]: TOOL-06 bleibt Pending: der provider-parallele Fan-out ist live belegt, der Negativbeweis der Berechtigungstreue mit zwei Konten gehoert in Plan 01-14
- [Phase 01-server-kern]: Der #227-Fix macht stateless_http konfigurierbar statt hart False: der Default behebt den Bug, MCP_STATELESS_HTTP=1 erhaelt das alte Verhalten; minimaler Diff, hoechste Merge-Wahrscheinlichkeit
- [Phase 01-server-kern]: Der Regressionstest der #227-Klasse bleibt bei uns (tests/compat/legacy_client_check.py); im fremden CI braeuchte er ein zweites Client-Environment gegen einen laufenden ExApp-Container und erzeugte nur Rauschen
- [Phase 01-server-kern]: Upstream-Beitraege laufen im Fork ausserhalb unseres Repos, mit lokal gesetzter git-Identitaet street1983nk / k.cherif@outlook.de und git commit -s (DCO); die Einreichung loest immer der Owner aus
- [Phase 01-server-kern]: search und fetch sind die einzigen Tools MIT Output-Schema (kein structured_output=False); mcp 2.x erzeugt aus dem Pydantic-Rueckgabetyp structured_content und content gleichzeitig, genau die Doppelung, die OpenAI verlangt
- [Phase 01-server-kern]: graceful ist generisch (PEP 695), weil eine auf str festgenagelte Dekorator-Signatur genau die Return-Annotation geloescht hätte, aus der das SDK das Output-Schema baut
- [Phase 01-server-kern]: file:<fileid> wird per WebDAV-SEARCH mit d:eq auf oc:fileid in einen Pfad aufgeloest, live gegen Nextcloud 34 verifiziert; die Unified Search liefert nur die fileid, nie den Pfad
- [Phase 01-server-kern]: Die Deck-Kurzform wird per Sweep aufgeloest (ein Request pro Board, Abbruch beim Fund, Cache nur innerhalb des Aufrufs); die interne Route aus A4 wird nicht benutzt und steht deshalb nirgends woertlich im Modul, weil ein Grep-Test sie fernhaelt
- [Phase 01-server-kern]: fetch beantwortet eine url-ID mit einem ToolError, dessen Hinweis die URL traegt: ein Erfolgsergebnis ohne Inhalt ist die Form, die zum Erfinden einlaedt (T-01-75)
- [Phase 01-server-kern]: SRV-03 bleibt Pending: Annotationen und Budget-Gate stimmen fuer alle 15 Tools, die Abnahme gehoert nach Plan 01-14
- [Phase 01-server-kern]: Das Token-Budget-Gate steht auf dem gemessenen Wert plus 15 Prozent (10643 -> 12500 Bytes): 24000 war mehr als das Doppelte der Messung; ein Gate, das nie ausloest, schuetzt nichts
- [Phase 01-server-kern]: Das Destruktiv-Gate filtert Kommentare und Docstrings per AST, behaelt aber String-Literale: Der ehrliche Satz in dav.py wuerde ein naives Grep rot faerben; method=DELETE ist das eigentliche Ziel
- [Phase 01-server-kern]: Vulture laeuft bei voller Konfidenz mit annotierter Whitelist statt --min-confidence 80: Bei 80 meldete der CI-Schritt gar nichts und konnte nie fehlschlagen
- [Phase 01-server-kern]: Die README-Tool-Tabelle wird im Contract-Test gegen die laufende Registry geprueft statt von Hand gepflegt: Eine handgepflegte Tabelle veraltet beim ersten neuen Tool; die Registry ist die einzige Wahrheit
- [Phase 01-server-kern]: Modul-globaler veraenderlicher Zustand ist im Produktionscode verboten, mit genau zwei namentlich gelisteten Ausnahmen: Ein Dictionary, das eine Anfrage ueberlebt, ist einen Refactor von einem Session-Store entfernt und bricht den Restart-Beweis
- [Phase 01-server-kern]: CONTRIB-01 bleibt Pending und Success Criterion 5 nur zur Haelfte erfuellt: Die App-ID ist eingefroren und dokumentiert, aber der PR an context_agent 227 ist ein Owner-Schritt und noch nicht eingereicht
- [Phase 02-exapp-shell]: Die Lifecycle-Routen werden von einer Fabrik geliefert und nur von entry_exapp angehaengt, nicht per Dekorator am geteilten Serverobjekt registriert: eine Registrierung am Singleton wuerde /heartbeat, /init und /enabled auch im eigenstaendigen HTTP-Modus erscheinen lassen, sobald irgendein Import das Modul beruehrt (D-23)
- [Phase 02-exapp-shell]: Der ExApp-Modus gewinnt in select_mode gegen den statischen Bearer, aber nie gegen stdio; ein Prozess mit beiden Kanaelen wird beim Start mit Exit-Code 2 abgelehnt statt pro Request still aufgeloest (D-27)
- [Phase 02-exapp-shell]: Die AppAPI-Variablen tragen bewusst kein NC_MCP_-Praefix (APP_ID, APP_SECRET, APP_VERSION, AA_VERSION, APP_HOST, APP_PORT, APP_PERSISTENT_STORAGE, HP_SHARED_KEY, HP_EXAPP_SOCK, NEXTCLOUD_URL): die Namen gibt der AppAPI-Deploy-Daemon vor
- [Phase 02-exapp-shell]: /init antwortet auch dann 200, wenn der OCS-Fortschritts-Push scheitert; ein 500 wuerde die Installation abbrechen, ein verpasster Push kostet nur eine Logzeile (Pitfall 3)
- [Phase 02-exapp-shell]: Jede Lifecycle-Antwort traegt Cache-Control: no-store aus einer einzigen Hilfsfunktion; der PHP-Proxy cacht JSON sonst 3600 Sekunden (Pitfall 4)
- [Phase 02-exapp-shell]: Ein anliegender x-origin-ip-Header beendet /init und /enabled mit 404: nur der PHP-Proxy setzt ihn, und der schuetzt diese Pfade nicht, haengt aber gueltige AppAPI-Header selbst an (Pitfall 2)
- [Phase 02-exapp-shell]: EXAPP-01 und AUTH-05 bleiben Pending: dieser Plan belegt den Kontrakt in-process, der Installationsnachweis braucht Dockerfile, info.xml und eine laufende Nextcloud (Plaene 02-03 bis 02-05)
- [Phase 02-exapp-shell]: mode bleibt ein str-Feld mit benannten Konstanten statt eines Literal-Typs; sonst waere der Ablehnungszweig fuer einen dritten Modus im Test nur mit type: ignore erreichbar, und ein untestbarer Zweig schuetzt nichts
- [Phase 02-exapp-shell]: Der ExApp-Zweig steht vor dem Passthrough-Zweig und liest den Authorization-Header nie; HaRP reicht einen mitgeschickten Basic-Header durch, ein zweiter akzeptierter Kanal waere genau der stille Fallback, den D-27 verbietet (T-02-11)
- [Phase 02-exapp-shell]: Das Quelltext-Gate gegen hart verdrahtetes BasicAuth liest das gesamte clients-Paket statt einer Dateiliste; ein siebtes Client-Modul faellt damit ohne Testaenderung unter dasselbe Verbot (T-02-15)
- [Phase 02-exapp-shell]: AUTH-05 bleibt Pending, obwohl der vierte Credential-Modus steht; der Weg von AUTHORIZATION-APP-API bis in jede Anfrage ist unit-belegt, der Negativbeweis mit zwei Konten gegen eine laufende Nextcloud gehoert zu Plan 02-05
- [Phase 02-exapp-shell]: uv sync laeuft im Image mit --no-editable, damit die Laufzeitstufe nur die virtuelle Umgebung traegt und keine zweite Kopie von src; nc-mcp-exapp liegt danach als fertiges Skript in /app/.venv/bin
- [Phase 02-exapp-shell]: /frpc.toml wird im Image als leere Datei mit Eigentuemer 10001 angelegt, statt Schreibrechte auf / zu vergeben: start.sh bleibt damit woertlich das HaRP-Original, und ein unprivilegierter Prozess darf eine eigene Datei kuerzen
- [Phase 02-exapp-shell]: Das Volume-Ziel /nc_app_mcp_connector_data entsteht im Image mit Eigentuemer 10001, weil ein frisches Docker-Volume Eigentuemer und Modus des ueberdeckten Verzeichnisses erbt (DockerActions::buildDefaultExAppVolume)
- [Phase 02-exapp-shell]: Der Manifest-Gate vergleicht nicht nur eine Wortliste weiter Regexe, sondern matcht jede deklarierte Route gegen /heartbeat, /init und /enabled; eine Gegenprobe im Test belegt, dass das Gate ausloest
- [Phase 02-exapp-shell]: Der CI-Job image bekommt docker/setup-qemu-action zusaetzlich zu setup-buildx-action, weil die arm64-Haelfte des Matrix-Baus auf einem amd64-Runner sonst nicht ausfuehrbar ist; veroeffentlicht wird nichts (D-25)
- [Phase 02-exapp-shell]: EXAPP-01 bleibt Pending: das installierbare Paket existiert (Image plus Manifest), der Nachweis der Installation durch den Deploy Daemon gehoert zu Plan 02-04
- [Phase 02-exapp-shell]: Die HaRP-Testtopologie ist ein zweites compose-File mit eigenem Projektnamen nc-mcp-exapp, eigenem Volume, eigenem Netz und Port 8081 (D-31); die vom Owner genutzte Instanz aus compose.test.yml bleibt dadurch unberuehrt, und ein Test haelt fest, dass das Bootstrap-Skript sie nicht einmal erwaehnt
- [Phase 02-exapp-shell]: access_level wandert als Zahl in die json-info-Registrierung: AppAPI mappt PUBLIC/USER/ADMIN nur auf dem info.xml-Pfad, eine json-info-Registrierung schreibt den Wert roh in die Integer-Spalte von ex_apps_routes
- [Phase 02-exapp-shell]: Der ExApp-Port liegt bei 23000, weil der FRP-Server in HaRP nur 23000 bis 23999 erlaubt; ausserhalb meldet frpc port not allowed und HAProxy antwortet ohne Backend mit 503
- [Phase 02-exapp-shell]: Das Image legt /certs fuer uid 10001 an, weil HaRP das FRP-Client-Zertifikat mit der Identitaet des Containers installiert; ohne das Verzeichnis scheitert die Zertifikatsinstallation mit 500 und der Tunnel bleibt ungesichert und damit tot
- [Phase 02-exapp-shell]: EXAPP-01 ist abgehakt: occ app_api:app:list meldet mcp_connector als enabled, deploy und init stehen auf 100, der MCP-Endpunkt wird mit dem App-Passwort eines Nutzers bedient; der AIO-Nachweis bleibt Sache von Plan 02-07
- [Phase 02-exapp-shell]: AUTH-06 ist GO und abgehakt: die RFC-9728-Metadaten sind unauthentifiziert von aussen ueber BEIDE Proxy-Wege erreichbar (HaRP und PHP-Proxy je 200 mit JSON), der WWW-Authenticate-resource_metadata-Zeiger passiert beide Proxys unveraendert; die Discovery-Route leckt nichts (nur oeffentliche URL plus Methodenliste, kein Secret, kein interner Host)
- [Phase 02-exapp-shell]: Der kanonische RFC-9728-Wurzelpfad ist 404 und gehoert Nextcloud, nicht der ExApp; Phase 3 setzt auf den resource_metadata-Zeiger (SEP-985 Prioritaet 1) plus eine Admin-Reverse-Proxy-Regel als getesteten Fallback (Caddy und nginx in docs/spike-discovery.md)
- [Phase 02-exapp-shell]: Die Discovery-Sonde ist bewusst ein Spike-Artefakt (T-02-44): der 401 stammt aus einer eigenen Sonde unter /.well-known/, nicht aus /mcp, weil /mcp in Phase 2 bewusst auf USER steht; Ersatz durch echte PRM aus AuthSettings plus /mcp auf PUBLIC ist Phase-3-Aufgabe
- [Phase 02-exapp-shell]: Ein unbekannter Bearer ueber HaRP auf der USER-Route /mcp wird 403 (sauberes 4xx, kein 5xx) beantwortet; damit kann ein spaeter PUBLIC gestelltes /mcp unbekannte Tokens an den eigenen Token-Verifier weiterreichen statt in einen 401 zu kippen (Open Question 4)
- [Phase 02-exapp-shell]: Die exapp-Topologie musste fuer die Messung neu aufgebaut werden (down -v, frischer Hex64-HP_SHARED_KEY): die in den Volumes von 02-04 gespeicherte HaRP-Daemon-Registrierung nutzte den alten Nicht-Hex-Schluessel, den der nach 02-04 eingezogene require_hex64-Gate (CR-02) ablehnt; nur das nc-mcp-exapp-Projekt betroffen, nc-mcp-test blieb unberuehrt
- [Phase 02-exapp-shell]: AUTH-05 ist abgehakt (DAV-Spike D-30, Fall A): alle sechs API-Familien (WebDAV, CalDAV, CardDAV, OCS, Notes, Deck) laufen unter AppAPI-Impersonation gegen NC 34.0.2 / AppAPI 34.0.0, die Identitaet ist serverseitig belegt (cloud/user liefert genau alice bzw. bob, exapp_impersonation.log protokolliert jeden Request); keine Provider-Aufteilung, kein App-Passwort-Rueckfall, Annahme A1 bestaetigt
- [Phase 02-exapp-shell]: Der Negativfall ist der Kern von AUTH-05: bob erreicht alices Datei auch bei bekanntem Pfad nicht (404, nie 200); der Confused-Deputy-Beweis zeigt, dass ein zusaetzlicher gueltiger Authorization-Basic-Header fuer alice die bob-Impersonation NICHT ueberschreibt (cloud/user bleibt bob), weil die Identitaet allein aus AUTHORIZATION-APP-API stammt
- [Phase 02-exapp-shell]: Zwei Kontrollpruefungen machen die Matrix beweiskraeftig: der messende Prozess traegt kein NC_MCP_APP_PASSWORD und keinen NC_MCP_STATIC_BEARER, und ein falsches APP_SECRET (64 Nullen) wird mit 401 abgewiesen; die Create-only-Grenze (If-None-Match: *) haelt unter Impersonation (zweites PUT 412)
- [Phase 02-exapp-shell]: AUTH-05 ist ueber die volle Kette bestaetigt (MCP-Client, HaRP, ExApp, Impersonation, Nextcloud-ACLs); bob findet nichts von alice ueber files_search, notes_search, unified_search und files_read, alice findet ihre eigenen Inhalte im selben Lauf (test_permission_fidelity_exapp.py, 9 gruen); die Middleware-Grenze haelt live (anonymes /mcp = 403, Heartbeat von aussen = 502)
- [Phase 02-exapp-shell]: Ein per occ user:add angelegter Nutzer hat ein leeres Files-Home ohne suchbaren Root; eine WebDAV-SEARCH antwortet dann 500 statt leer; ensure_files_home legt eine neutrale Datei an und scannt sie (wie ein Erst-Login-Skeleton), danach ist die SEARCH ein sauberes leeres Ergebnis
- [Phase 02-exapp-shell]: Der Nextcloud-AIO-Smoke ist Fall B; er scheitert an AIOs Domain-Validierung (oeffentliche Domain plus gueltiges TLS), ist mit fehlenden Schritten in docs/exapp-install.md dokumentiert und als benannter Punkt an Phase 5 uebergeben (D-31), nicht still gestrichen
- [Phase 03-oauth-2-1]: Der issuer der AS-Metadaten wird als exakter String auf die konfigurierte public_url gesetzt: AnyHttpUrl haengt einer pfadlosen URL einen Schraegstrich an, und RFC 8414 vergleicht den issuer zeichengenau
- [Phase 03-oauth-2-1]: Genau ein Tool-Scope nextcloud in der PRM; offline_access nur in den AS-Metadaten: D-42 plus MCP-Spec: offline_access gehoert weder in scopes_supported der PRM noch in den WWW-Authenticate-Scope
- [Phase 03-oauth-2-1]: token_endpoint_auth_methods_supported traegt zusaetzlich none: Claude.ai und ChatGPT kommen als public clients ohne Client-Secret; das SDK listet per Default nur die beiden Secret-Methoden
- [Phase 03-oauth-2-1]: Die Bearer-Grenze ist fail-closed: ohne konfigurierten Verifier ist jeder Bearer ungueltig: Manifest-Umstellung auf PUBLIC und eigene Pruefung entstanden in derselben Aenderung (Pitfall 6); der echte Verifier folgt in Plan 03-06
- [Phase 03-oauth-2-1]: Das Manifest deklariert je Dokument eine vollstaendig verankerte Route, das Gate faellt ohne Endanker: HaRP matcht mit re.match, ein Muster ohne Endanker trifft auch Nachbarn; damit ist AR-02-06 geschlossen
- [Phase 03-oauth-2-1]: Jede HTML-Seite der Phase entsteht in genau einer Funktion (exapp/ui/layout.py): CSP mit Nonce, X-Frame-Options, Referrer-Policy und no-store haben damit eine Quelle statt einer Kopie je Seite
- [Phase 03-oauth-2-1]: page() nimmt die Umgebung und nie den Request: die Absenderzeile (Wortmarke plus Host) kommt aus config.public_url, sonst koennte ein gefaelschter Host-Header umschreiben, wer nach Zugriff fragt
- [Phase 03-oauth-2-1]: Der Client-Name aus der DCR-Registrierung wird vor dem Escaping gesaeubert (Steuerzeichen weg, 80 Zeichen) und der Escaping-Test vergleicht Elementanzahlen statt Teilzeichenketten
- [Phase 03-oauth-2-1]: Nutzertexte stehen als Modulkonstanten in __all__: das ist der Katalog fuer eine spaetere Lokalisierung und zugleich der Grund, warum der vulture-Gate ohne Whitelist-Eintrag gruen bleibt
- [Phase 03-oauth-2-1]: link() und form() lehnen jedes Ziel ab, das kein lokaler Pfad ist: ein Open Redirect im Consent-Umfeld ist im Renderer billiger verboten als in fuenf Route-Handlern geprueft
- [Phase 03-oauth-2-1]: AUTH-02 und AUTH-03 bleiben Pending: Plan 03-03 haengt bewusst keine Route ein, die Bausteine allein sind weder Browser-Login noch OAuth-Verbindung
- [Phase 03-oauth-2-1]: Der Datenschluessel wird nach dem Schreiben zurueckgelesen: zwei gleichzeitig startende Worker finden beide keinen Schluessel und schreiben beide einen; ohne Rueckleseschritt verschluesselt der Verlierer alles mit einem Schluessel, den niemand mehr liest (D-43)
- [Phase 03-oauth-2-1]: Eine nicht lesbare ExApp-Config-Antwort wirft, statt als fehlender Schluessel zu gelten: sonst wuerde ein Parse-Fehler einen lebenden Schluessel ueberschreiben und alle Verbindungen toeten
- [Phase 03-oauth-2-1]: Die Refresh-Einloesung schreibt den Nachfolger in derselben Transaktion und unterscheidet drei Ausgaenge (unknown, expired, reused): nur der dritte toetet in 03-07 die Familie, und ein Absturz zwischen zwei Schreibvorgaengen darf keinen Nutzer ohne gueltigen Token zuruecklassen
- [Phase 03-oauth-2-1]: Die Gueltigkeit eines Access-Tokens ist ein Join auf die Autorisierung: ein Widerruf wirkt damit sofort und nicht erst beim naechsten Aufraeumen (SC 4)
- [Phase 03-oauth-2-1]: Die Schreibbarkeit des Volumes wird durch Schreiben geprueft, nicht durch os.access: Berechtigungsbits sagen nichts ueber einen read-only-Mount oder eine Windows-ACL
- [Phase 03-oauth-2-1]: Client-Verfall laeuft nur in purge_expired, nie im Schreibpfad: das Loeschen eines Clients nimmt ueber die Kaskade seine Autorisierungen mit
- [Phase 03-oauth-2-1]: cryptography ist ab 03-02 direkte Dependency (Owner-Freigabe 16.08.); der Lock-Schritt lief mit `uv lock` statt `uv add`, damit die .venv unberuehrt bleibt
- [Phase 03-oauth-2-1]: Das Destruktiv-Gate bekommt eine eng gefasste, gegengeprobte Ausnahme fuer SQL in oauth/store.py (DELETE FROM, ON DELETE CASCADE): TOOL-09 ist ein Versprechen ueber Daten in Nextcloud, nicht ueber die eigene SQLite-Datei
- [Phase 03-oauth-2-1]: Der Poll laeuft immer gegen die konfigurierte Basis-URL mit festem Pfad, nie gegen die absolute Adresse aus der Startantwort (Pitfall 7c); ein Test mit einer zweiten respx-Route belegt, dass diese Adresse nie aufgerufen wird
- [Phase 03-oauth-2-1]: 404 heisst bei Nextcloud gleichzeitig 'noch nicht fertig' und 'unbekannt oder abgelaufen'; die Unterscheidung kommt deshalb aus unserer eigenen Zwanzig-Minuten-Frist im Flow-Datensatz, nie aus der Antwort
- [Phase 03-oauth-2-1]: Der Client-Name wird vor dem Absenden auf druckbares ASCII reduziert, gekuerzt und mit festem Praefix versehen: er wird bei Nextcloud zum User-Agent und damit zum angezeigten Namen im Bestaetigungsdialog (Pitfall 8)
- [Phase 03-oauth-2-1]: Der Anmeldelink steht auf der Seite, die der Start erzeugt, und nicht auf der sich alle drei Sekunden neu ladenden Warteseite; ein Link, der drei Sekunden nach dem Erscheinen verschwindet, ist schlechter als einer, den 'Start over' neu holt
- [Phase 03-oauth-2-1]: Die Onboarding-Strecke bucht ihre Flows unter einer reservierten Client-Zeile mit allowed=false, weil die flows-Tabelle einen Fremdschluessel auf clients hat und dieser Weg gar keinen registrierten Client kennt
- [Phase 03-oauth-2-1]: Der Flow-Datensatz wird geloescht, bevor die Zugangsberechtigung gerendert wird (das 200 des Polls kommt genau einmal); schlaegt das Loeschen fehl, wird das gerade erzeugte App-Passwort widerrufen statt ungenutzt in Nextcloud zu bleiben
- [Phase 03-oauth-2-1]: Die prozessweite Store-Instanz und der purge_expired-Aufruf leben in der Closure der Routen-Fabrik, nicht als Modulglobale: ein Zustand, der Requests ueberlebt, ist sonst einen Refactor von einem Session-Store entfernt (D-20)
- [Phase 03-oauth-2-1]: Ein GET startet nie einen Anmeldevorgang; der zustandsaendernde Schritt der Browser-Strecke ist ein POST mit benannter Aktion (T-03-35)
- [Phase 03-oauth-2-1]: Die drei Schalter von AUTH-07 liegen in einem unveraenderlichen Policy-Objekt, das an vier Stellen befragt wird statt an einer: wer nur bei der Registrierung prueft, laesst einen spaeter gesperrten Client bis zum Token-Ablauf weiterlaufen (Pitfall 9)
- [Phase 03-oauth-2-1]: Der Allowlist-Modus mit leerer Liste sperrt alles: ein Admin, der den Modus einschaltet und die Liste vergisst, wollte schliessen und nicht oeffnen; ein unbekannter Wert eines Schalters behaelt dagegen den Default und wird geloggt, weil ein Tippfehler kein Sicherheitsschalter ist
- [Phase 03-oauth-2-1]: get_client liefert fuer unbekannt, gesperrt, nicht gelistet und verfallen dieselbe Antwort None und loescht dabei verfallene Registrierungen; die Fehlerseite waehlt danach allein die Admin-Konfiguration aus (E1/E2/E3), nie der Zustand eines Clients (T-03-47)
- [Phase 03-oauth-2-1]: Das Client-Secret wird nur als SHA-256-Hash gespeichert; der SDK-ClientAuthenticator vergleicht Klartext, deshalb bleibt der Token-Endpunkt fuer vertrauliche Clients bis zum eigenen Authenticator in 03-06 fail-closed
- [Phase 03-oauth-2-1]: Von den Routen aus create_auth_routes werden zwei verworfen: das AS-Metadatendokument (03-01 liefert das vollstaendige) und /authorize (oauth/consent.py steht davor, damit eine Ablehnung eine Seite ist und kein JSON im Browser)
- [Phase 03-oauth-2-1]: Der Anmeldelink des Login Flow v2 reist als Query-Parameter der Weiterleitung zur Consent-Seite, weil der flows-Tabelle die Spalte fehlt und eine Migration teurer waere; gerendert wird er nur, wenn sein Host die konfigurierte Nextcloud oder die eigene public_url ist (T-03-42)
- [Phase 03-oauth-2-1]: Die Autorisierung wird unter der Id ihres eigenen Flows angelegt; damit verbindet sie sich mit dem Flow-Datensatz ohne zusaetzliche Spalte, und das App-Passwort aus dem einmaligen 200 des Polls ist sofort verschluesselt abgelegt
- [Phase 03-oauth-2-1]: Jeder Link und jede Formular-Aktion traegt jetzt den Praefix aus config.public_url: HaRP strippt /exapps/<app> vor dem Request, ein absoluter Pfad ohne Praefix zeigte auf die Nextcloud-Wurzel (Fund und Fix in 03-05, betraf auch die /connect-Seiten aus 03-04)
- [Phase 03-oauth-2-1]: Das Anti-Faelschungs-Merkmal des Consent-Formulars ist ein HMAC der Flow-Id unter dem Datenschluessel, keine Spalte: es braucht keine Migration, ueberlebt Neustart und zweiten Worker und kann von niemandem erzeugt werden, der nicht diese Installation ist (T-03-50)
- [Phase 03-oauth-2-1]: Eine Ablehnung loescht die Autorisierung und gibt das App-Passwort in einem Versuch an Nextcloud zurueck; eine abgelehnte Verbindung darf keinen brauchbaren Zugang hinterlassen (D-34)
- [Phase 03-oauth-2-1]: Der Authorization-Code wird beim Laden nicht verbraucht, sondern erst im Tausch, in der einen atomaren Anweisung des Stores: sonst verbrennt ein falscher PKCE-Verifier einen gueltigen Code
- [Phase 03-oauth-2-1]: auth_codes bekommt die Spalte redirect_uri_explicit samt idempotentem ALTER; ohne sie kann der SDK-Vergleich der Rueckadresse nach dem Loeschen des Flow-Datensatzes nicht mehr stimmen
- [Phase 03-oauth-2-1]: Die Transportgrenze loest die Nextcloud-Identitaet eines geprueften Tokens einmal pro Request auf und legt sie in den Request-Zustand; deps.resolve_credentials ist synchron und darf im Tool-Aufruf weder lesen noch entschluesseln (D-26)
- [Phase 03-oauth-2-1]: Kein dritter MODE_-Wert: gegenueber Nextcloud ist ein App-Passwort Basic-Auth, der OAuth-Zweig baut MODE_BASIC-Credentials
- [Phase 03-oauth-2-1]: provider.load_access_token bleibt eine Absage, weil der ProviderTokenVerifier des SDK Prozess-Cache, Audience-Pruefung und Client-Policy umgehen wuerde; geprueft wird ausschliesslich ueber oauth/verifier.py
- [Phase 03-oauth-2-1]: /token und /revoke werden mit einem eigenen ClientAuthenticator neu gebaut, der gegen den gespeicherten Hash vergleicht; das SDK vergleicht ein Klartext-Secret, das dieser Store nicht haelt
- [Phase 03-oauth-2-1]: Das Gnadenfenster aus D-41 wiederholt genau die vorgehaltene Antwort und erzeugt nie einen zweiten Familienzweig; eine verlorene vorgehaltene Antwort ist invalid_grant und nie ein Familienwiderruf
- [Phase 03-oauth-2-1]: Eine Wiederverwendung ausserhalb des Fensters widerruft Familie UND Autorisierung, ausschliesslich im Store, und vermerkt das App-Passwort als Aufraeumaufgabe: der Token-Pfad ruft Nextcloud nie an (Pitfall 13)
- [Phase 03-oauth-2-1]: Der Widerruf laeuft in der Reihenfolge Store, Prozess-Caches, Nextcloud; der dritte Schritt darf fehlschlagen und haelt die ersten beiden nie auf (cleanup_at vermerkt den Fehlschlag)
- [Phase 03-oauth-2-1]: /revoke wird als FamilyRevocation neu gebaut, weil load_access_token bewusst absagt und der SDK-Handler sonst 200 antwortet, ohne irgendetwas zu widerrufen; das eigene Request-Modell macht client_secret optional, sonst bekaeme jeder oeffentliche Client 400
- [Phase 03-oauth-2-1]: Die Drosselung hat zwei Grenzen: eine je Quelle, die ein gefaelschter X-Forwarded-For aufteilen kann, und eine je Pfadklasse, die er nicht aufteilen kann; gezaehlt wird nach Antwortstatus, gespeichert wird nur ein SHA-256-Digest
- [Phase 03-oauth-2-1]: Der Sweep fuer nie entschiedene Anmeldungen haengt an der Autorisierungsanfrage, hart begrenzt auf drei je Aufruf: dieses Projekt hat keinen Cron, und wer neu verbindet, zahlt fuer die, die niemand zu Ende gebracht hat

- [Phase 03-oauth-2-1]: NC_MCP_PUBLIC_URL ist die eine Variable, ohne die OAuth nicht funktioniert, und der Deploy-Daemon reicht eine Variable nur durch, wenn das Manifest sie deklariert: appinfo/info.xml deklariert sie und die drei AUTH-07-Schalter, sonst wird `--env` akzeptiert und verworfen (gemessen gegen AppAPI 34.0.0)
- [Phase 03-oauth-2-1]: Die ExApp-Config wird mit POST auf .../ex-app/config/get-values und dem Rumpf {"configKeys": [...]} gelesen, nicht mit GET und configKeys[]; die Antwort nennt ihre Felder klein (configkey/configvalue), und beides zusammen war der Grund, warum kein Datenschluessel je gelesen werden konnte
- [Phase 03-oauth-2-1]: Der geteilte httpx-Client fuehrt keinen Cookie-Jar mehr: Nextcloud setzt auf jede Antwort ein Session-Cookie, und auf einem prozessweiten Client wurde daraus eine Sitzung fuer alle Nutzer (gemessen: SEARCH mit dem Scope des einen und der Identitaet des anderen Nutzers)
- [Phase 03-oauth-2-1]: SC 5 ist gemessen statt geschaetzt: genau ein Nextcloud-Roundtrip je MCP-Request mit Authorization-Header, angenommen wie abgelehnt; die eigene Drosselung antwortet beim elften abgelehnten Token-Request mit 429 und Retry-After 300, und der Testnutzer meldet sich danach normal an
- [Phase 04]: Der Per-User-Schalter liegt in unserem Store und wird je Request lokal gelesen, ohne Prozess-Cache: nur so wirkt das Umlegen beim nächsten Aufruf (D-48), und es kostet keinen zweiten Nextcloud-Roundtrip (D-47)
- [Phase 04]: Freigeben löscht die user_access-Zeile, statt sie auf null zu setzen: 'nie pausiert' und 'wieder freigegeben' sind damit dieselbe Wahrheit, und der Default 'an' kostet keine Zeile (D-50)
- [Phase 04]: Ein Store-Ausfall am Schalter-Gate ist 503 mit no-store, nie ein Durchlass und nie ein behauptetes access_disabled (fail closed, D-37-Analogie); der AUTH-01-Zweig braucht damit ab jetzt ebenfalls den Store
- [Phase 04]: R1 antwortet 403 ohne WWW-Authenticate, bewusst abweichend von RFC 6750: ein 401 mit Challenge schickt OAuth-Clients in die volle Rediscovery-Schleife und legt deren Last auf Nextcloud
- [Phase 04]: prepare_context fragt die Unified Search OHNE Provider-Einschraenkung und buendelt nach dem kind-Feld: eine feste Providerliste wuerde ein installiertes Findling aussperren (D-53), und der Deck-Provider heisst search-deck-card-board (Pitfall 9)
- [Phase 04]: Jede Teilquelle hat ihr eigenes Timeout, das Buendel keines: ein globaler Abbruch wuerde die bereits fertige Teilantwort verwerfen; der Kalender-Cap von 10 s lebt in context.py, calendar.py behaelt seine 20 s
- [Phase 04]: Auch eine Kappung steht unter degraded (5 je Bucket, 10 Termine, 3 Auszüge): eine still verkuerzte Liste ist das Ergebnis, das ein Modell als "mehr gibt es nicht" weitergibt (SC 4)
- [Phase 04]: Gegen Prompt-Injection wird nicht maskiert (D-57): Herkunft als Strukturfelder, Auszug als reines Datenfeld, Warnung in der Tool-Description, und ein Waechter-Test, der injizierten Anweisungstext zeichengenau als Daten ankommen laesst
- [Phase 04]: Ein Schalter-HMAC ist zweckgebunden (access: plus Konto), damit ein Zeilen-Wert kein Konto pausieren kann und ein Konto-Wert kein fremdes
- [Phase 04]: Der Zeilen-Widerruf laeuft ausschliesslich ueber provider.end_connection; ein Quelltext-Waechter haelt revoke_authorization und revoke_family aus Seiten- und Routenmodul heraus (T-04-35, Verifier-Cache)
- [Phase 04]: Route 13 ist PUBLIC mit Identitaetspruefung in der App, aus dem gemessenen CR-01-Grund: eine USER-Route fuettert die HaRP-Blacklist mit genau den Abweisungen, die diese Seite als normalen Verkehr erzeugt
- [Phase 04]: Der Settings-Eintrag ist ein Wegweiser mit leerem fields, weil AppAPI eine Wertaenderung nie an die ExApp meldet; der Schalter lebt auf /connections. Gemessener AppAPI-Kontrakt (04-RESEARCH Frage 1): eine Checkbox waere ein Schalter, den die Transportgrenze nicht durchsetzt (D-47, D-48)
- [Phase 04]: Die Registrierung der Settings-Form laeuft fire-and-forget bei enabled=1. Ein 500 aus /enabled deaktiviert die App sofort wieder, ein fehlgeschlagener Wegweiser kostet nur eine Logzeile (Pitfall 11)
- [Phase 05]: Der Admin-Lesepfad faellt weich aus: jeder Fehler ist ein leeres Dict plus eine Logzeile; ein fehlender Admin-Wert bedeutet nur 'nichts gesetzt', waehrend crypto._read_key hart scheitert, weil ein erfundener Data Key jede Autorisierung unlesbar macht
- [Phase 05]: Die Vorrangregel Admin-Wert vor NC_MCP_-Env vor Code-Default entsteht durch Auslassen: admin_overlay traegt nur brauchbare Werte, ein leerer oder ungueltiger Wert fehlt einfach
- [Phase 05]: Die vier Feld-Ids der Admin-Form kommen aus config_values.CONFIG_KEYS, kein Feld traegt sensitive (ICrypto-Blob) und keines ist ein Button (Declarative Settings kennen keinen)
- [Phase 05]: Die zweite Formular-Registrierung liegt im enabled=1-Zweig in einem eigenen try-Block: ein Fehlschlag der einen Form darf die andere nicht kosten, und /enabled antwortet immer mit leerem error-Feld (Pitfall 11 der Phase 2)
- [Phase 05]: Permission-Parity braucht eine Asymmetrie in den DATEN: alice teilt einen Ordner read-only mit bob (permissions=1) und eine zweite Datei nie; ein Vergleich zweier gleicher Aufrufe ueber dieselben Schnittstellen waere immer gruen und wuerde nichts beweisen (05-RESEARCH Pitfall 6)
- [Phase 05]: Die Fixture-Namen werden wie APP_SECRET aus .env.exapp zurueckgelesen und nur beim ersten Mal erzeugt: ein frischer Suffix pro Lauf hätte die Instanz mit einer zweiten Freigabe hinterlassen, und der Test hätte gemessen, welche die Verbindungsdatei gerade nennt
- [Phase 05]: Die Fixture-Pfade stehen relativ zur Nutzerwurzel in .env.exapp und nc_status haengt den Statuscode an den Rumpf statt ihn nach /dev/null zu schreiben: Git Bash schreibt exportierte absolute POSIX-Pfade beim Prozessstart um, und mit dem exportierten MSYS_NO_PATHCONV=1 existiert /dev/null fuer curl.exe nicht (beides live gemessen, 05-03-MEASUREMENTS Schritte 4 und 6)
- [Phase 05]: Die Fixture legt ihre Objekte ueber WebDAV und OCS an, nicht per docker exec ins Datenverzeichnis: eine dort abgelegte Datei hat bis zum naechsten files:scan keine File-Id, und ein Ordner ohne File-Id ist nicht teilbar
- [Phase 05]: Der Per-User-Schalter wird am fruehesten Punkt durchgesetzt, an dem das Konto existiert (nach dem Login-Flow-v2-Poll): davor kennt kein Pfad das Subjekt, also waere eine frueher gesetzte Pruefung wirkungslos oder falsch adressiert
- [Phase 05]: Jede Ablehnung eines pausierten Kontos gibt das gerade entstandene App-Passwort in einem Versuch zurueck, auch im Store-Ausfall-Zweig: ohne diesen Schritt entstuende keine Verbindung, das App-Passwort aber schon (T-05-08)
- [Phase 05]: Ein Sicherheitsschalter wird mit drei Zustaenden gelesen (pausiert, nicht pausiert, keine Antwort): ein bool muesste fuer den Ausfall einen Default raten, und beide Defaults sind falsch (True sperrt eine gesunde Installation aus, False ist der Durchlass, gegen den BL-10 gebaut ist)
- [Phase 05]: Die Ablehnung eines pausierten Kontos auf der Zustimmungsseite bekommt keine access_denied-Weiterleitung, sondern die Seite E9: dieser Fehlercode heisst 'die Nutzerin hat abgelehnt', und hier hat sie nichts abgelehnt (T-05-09)
- [Phase 05]: /authorize und connect._start bleiben ungeprueft, und der Grund steht als Docstring-Absatz an genau diesen Stellen; zwei Quelltext-Tests halten ihn dort, damit die Luecke nicht fuer ein Versehen gehalten wird
- [Phase 05]: Die Admin-Werte werden genau einmal beim Prozessstart aufgeloest und als Umgebung an build_exapp_app gegeben, nicht pro Request nachgelesen: config.public_url bleibt synchron und pur, ein Prozess-Cache waere verbotener Modulzustand (D-20), und ein Lesen pro Request waere ein zweiter Nextcloud-Roundtrip je Anfrage (SC 5 der Phase 3); der Preis ist der Wiederaktivieren-Schritt und er steht an drei Stellen
- [Phase 05]: Eine fehlende oeffentliche Adresse beendet den Prozess nicht mehr mit Exit 2: mit Abbruch wird die App nie enabled, das Admin-Formular wird nie registriert und der Admin hat keinen Ort fuer den Wert; 'keine stille Fehlkonfiguration' halten jetzt die Fehlerzeile und der sichtbare Setup-Zustand auf /connections
- [Phase 05]: Keine Herleitung der oeffentlichen Adresse aus NEXTCLOUD_URL (Assumption A2): AppAPI setzt sie mit herabgesetztem Schema und moeglicherweise intern, ein hergeleiteter Wert waere ein stiller Default mit kaputter Discovery
- [Phase 05]: Der Startzeit-Lesevorgang bringt seinen eigenen kurzlebigen httpx-Client mit (read_values und admin_overlay nehmen ihn als Parameter): shared_client bindet seinen Pool an den Event-Loop des ersten Aufrufs, und dieser Loop ist geschlossen, bevor uvicorn seinen eigenen oeffnet
- [Phase 05]: Ein Credential-Flood wird in Nextcloud-PHP-Runden pro Angreifer-Request gemessen, nicht in Millisekunden: gemessener Quotient 1,00 in beiden Laeufen (200 von 200 Requests erzeugen eine harp/user-info-Anfrage), waehrend 20 Requests ohne Authorization-Header null Nextcloud-Requests kosten
- [Phase 05]: Die Bruteforce-Eintraege eines Basic-Floods landen auf der Adresse von HaRP und nicht auf der des Angreifers (27 bis 28 je 200 Requests auf 172.29.42.131, null auf Gateway, Caddy und ExApp-Container), weil Nextcloud nur den Caddy-Container als Proxy vertraut; damit teilen alle Nutzer aller ExApps hinter diesem Proxy einen Zaehler, und die Formulierung 'pro Quell-IP' aus dem Research ist zu schwach
- [Phase 05]: 200 abgelehnte Basic-Logins erzeugen nur 27 bis 28 Zaehler-Eintraege und Lauf B ist schneller als Lauf A: ab der Maximalverzoegerung lehnt Nextcloud ohne Anmeldepruefung ab, die PHP-Runde pro Request bleibt aber; der Bearer-Flood ist damit der teurere Angriff, weil er nie einen Zaehler fuellt, der ihn bremst
- [Phase 05]: Die Bremse gegen einen Credential-Flood steht im Reverse Proxy des Admins (Rate-Limit-Regel auf /exapps/mcp_connector/ mit Beispiel fuer Caddy und nginx), nicht auf /mcp: nur dort kann ein Request abgewiesen werden, bevor HaRP Nextcloud fragt, und D-37 plus T-02-21 bleiben unveraendert
- [Phase 05]: Ein Test, der Instanzzustand aendert, liest den Vorzustand und stellt ihn im finally zurueck: der Lasttest schaltet den vom Bootstrap deaktivierten Bruteforce-Waechter fuer die Messung ein, weil ein leerer Zaehler sonst ein Artefakt der Fixture waere, und setzt danach alle Zaehler mit Nachweis zurueck (T-05-24)
- [Phase 05]: Der Lasttest spricht mit docker exec und den festen Containernamen statt mit docker compose exec: jeder compose-Aufruf gegen compose.exapp.yml verlangt HP_SHARED_KEY in der Umgebung (WR-11), und der messende Prozess hat mit diesem Schluessel nichts zu tun; genau daran scheiterte der erste Bootstrap-Lauf still ("Nextcloud is still not installed", obwohl occ status installed: true meldete)
- [Phase 05]: Alle dreizehn Routen des Manifests sind seit CR-01 PUBLIC; das Installations-Runbook fuehrte /authorize/decide noch als user-Route und kannte /connections nicht, und die Zugriffsklasse in dem Dokument, mit dem ein Admin installiert, ist mehr als eine veraltete Zahl
- [Phase 05]: Der Purge-Handler bekommt keine Route im Manifest: der occ-Aufruf kommt ueber PublicFunctions und braucht keine, waehrend eine Deklaration eine unumkehrbare instanzweite Loeschung fuer jeden im Internet aufrufbar machte, weil der PHP-Proxy gueltige AppAPI-Header selbst anhaengt (T-02-20, T-05-26)
- [Phase 05]: Die Loesch-Reihenfolge lebt im Handler und nicht in der Doku: erst jedes App-Passwort zurueckgeben, dann die Tabellen leeren, dann den Datenschluessel löschen; ein Test prueft die Aufrufreihenfolge auf dem Draht (T-05-30)
- [Phase 05]: all_authorizations filtert nicht auf revoked_at IS NULL: die Frage des Purge ist, welches Nextcloud-App-Passwort noch gueltig sein kann, und eine widerrufene Zeile antwortet darauf mit ja
- [Phase 05]: Der enabled=0-Zweig bleibt leer: derselbe Hook feuert bei jedem Update (lib/Command/ExApp/Update.php), ein Aufraeumen dort loeschte bei jedem Update jede Verbindung jeder Nutzerin (T-05-28)
- [Phase 05]: Die force-Pruefung akzeptiert jede plausible Draht-Form der occ-Option, weil ihre genaue Form Assumption A5 ist und ein still nichts tuender Purge einen Admin mit falscher Sicherheit in die Deinstallation schickt
- [Phase 05]: Das Destruktiv-Gate bekommt eine dritte enge, gegengeprobte Ausnahme fuer den einen HTTP-DELETE in oauth/crypto.py: geloescht wird ein Wert, den die App ueber sich selbst geschrieben hat, TOOL-09 ist ein Versprechen ueber Nutzerdaten in Nextcloud
- [Phase 05-hardening-und-store-einreichung]: Die FAQ ist einsprachig kanonisch (docs/faq.md, Englisch) plus dreisprachige Kurzform mit Link; bei fuenf Fragen kostet jede Aenderung sonst sechs Textstellen (05-RESEARCH Open Question 2)
- [Phase 05-hardening-und-store-einreichung]: Die Store-Beschreibung traegt die Antwort auf die Abschalt-Frage selbst und verlinkt nur zusaetzlich: sie ist der einzige Text, den ein Nutzer ohne Repository-Besuch sieht
- [Phase 05-hardening-und-store-einreichung]: Alle drei Store-Beschreibungen stehen auf dem kleineren gemeinsamen Nenner der Instanz-Ansicht (Absaetze durch Leerzeilen, kein Backtick, keine Tabelle, kein Bild, keine Linie, kein HTML), weil dompurify dort alles andere entfernt statt es zu degradieren
- [Phase 05-hardening-und-store-einreichung]: Das Text- und Vokabular-Gate liest den geparsten Manifest-Baum ohne Kommentarknoten statt die Rohdatei: das Manifest erklaert in Kommentaren genau die Faelle, die ein grep als Verstoss lesen wuerde
- [Phase 05-hardening-und-store-einreichung]: Das Variablen-Gate verbietet nur das leere <default>, nicht das Element: ein befuellter Default bleibt erlaubt, und ein eigener Test haelt diese Haelfte fest (AppAPI 34.0.3 exportiert das leere Element als Zeichenkette Array, der Store antwortet mit 500)
- [Phase 05-hardening-und-store-einreichung]: Der Status-Abschnitt der drei READMEs nennt Fakten mit Fundstelle statt einer Phasennummer; phase 1 (server core) stand nach vier Phasen noch in der ersten Zeile, die ein Besucher liest
- [Phase 05]: Assumption A5 ist live geschlossen und hat zwei fail-closed Fehler aufgedeckt: AppAPI verpackt eine occ-Option als {occ: {arguments, options}}, also lag die force-Pflicht eine Ebene tiefer als geprueft, und der Loesch-Zweig der ExApp-Konfiguration nimmt configKeys als Liste statt configKey
- [Phase 05]: Nextcloud 34.0.2 zeigt kein ExApp in der Verwaltungsoberflaeche (appstore 1.0.0 fuellt nur aus dem Core-AppFetcher, ruft initialize des External-Apps-Stores nie, alte AppAPI-Route antwortet 500), also gibt es weder Install- noch Remove-Knopf; Linie A wurde ueber occ app_api:app:disable gemessen und die Gleichheit mit der Route des Knopfes aus dem Quelltext belegt
- [Phase 05]: Die gelistete Version 0.1.0 ist per Klick nicht installierbar (Exit 2, RestartCount 12, NC_MCP_PUBLIC_URL wird auf dem Store-Pfad nie gesetzt); der Fix liegt seit 05-01/05-04 im Code und ist das Argument fuer Release 0.1.1 in 05-10
- [Phase 05]: Der Purge ist der letzte Schritt vor dem Entfernen, weil er den Datenschluessel loescht, waehrend der laufende Prozess seine beim Start gelesene Kopie weiterbenutzt: danach entstandene Verbindungen sind beim naechsten Neustart unlesbar
- [Phase 05]: Release 0.1.1 ist im Store und behebt die Ein-Klick-Luecke: die Store-Installation ohne jede Umgebungsvariable kommt mit 0 restarts hoch und nennt ihren Setup-Zustand, wo 0.1.0 mit Exit 2 crash-loopte
- [Phase 05]: Ein Update behaelt die Verbindungen, gemessen an einem Zugriffstoken der Vorversion, das nach dem Update 16 Werkzeuge und einen echten Tool-Aufruf bediente
- [Phase 05]: Der AppAPI-Store-Cache wird durch Ueberschreiben mit timestamp 0 verworfen, nie durch Loeschen der Datei: sonst endet jedes folgende AppAPI-Kommando mit GenericFileException
- [Phase 05]: Ein Kommentar in appinfo/info.xml darf das Versionselement nicht in spitzen Klammern wiederholen, weil build_store_release.sh und release.yml die Version per grep auf dieses Tag lesen
- [Phase 05-hardening-und-store-einreichung]: config.normalize_base_url bleibt unveraendert, die Issuer-Regel (https ausser Loopback, RFC 8414) steht in exapp/config_values._public_url: dieselbe Funktion prueft NC_MCP_URL, und dort ist http auf einem internen Host legitim
- [Phase 05-hardening-und-store-einreichung]: Ein Issuer-Refusal beim Bau der Anwendung ist der einzige erholbare Startfehler: entry_exapp.main verwirft NC_MCP_PUBLIC_URL, baut genau einmal neu und laeuft mit dem Default weiter; ein zweiter Fehlschlag bleibt SystemExit(2)
- [Phase 05-hardening-und-store-einreichung]: Der gespeicherte Admin-Wert wird im Rettungszweig NICHT geloescht (T-05-44 accept): er bleibt im Formular sichtbar und korrigierbar
- [Phase 05-hardening-und-store-einreichung]: Der 401 des Startzeit-Lesevorgangs der Admin-Werte haengt allein am Aktivierungszustand der ExApp, nicht am Kanal und nicht am Zeitpunkt. Gemessen in 05-12: M1 antwortet 200 und liefert einen gesetzten Wert zurueck, M2 und M3 starten ohne die 401-Zeile, M3b und M3c isolieren das enabled-Flag als einzige Variable (401, OCS 997, AppAPI authentication failed); die Quelltext-Gegenprobe in AppAPIService::validateExAppRequestToNC bestaetigt es
- [Phase 05-hardening-und-store-einreichung]: Plan 05-13 geht Zweig N: keine Selbstneustart-Mechanik am enabled=1-Hook, sondern eine ehrliche Logzeile fuer das Fenster vor der Aktivierung plus der dokumentierte Disable/Enable-Zyklus. Ein zweiter Lesevorgang samt Cache waere ohne Wirkung, weil jeder Start einer aktivierten App die Werte bereits vollstaendig liest (M1, M2, M3); die Restart-Policy des Deploy-Daemon-Containers ist gemessen unless-stopped, ein Selbstneustart waere also machbar, loest aber nichts
- [Phase 05-hardening-und-store-einreichung]: Der Purge bricht bei null gelungenen Rueckgaben ab (WR-01): Tabellen und Datenschluessel bleiben unangetastet, weil die Tabellen die einzige Zuordnung Verbindung zu App-Passwort sind; ein Teilfehlschlag laeuft weiter und wird gezaehlt
- [Phase 05-hardening-und-store-einreichung]: purge._is_set ist eine Positivliste (TRUE_WORDS) und der Query-Parameter-Zweig entfaellt (WR-02): die gemessene AppAPI-Form ist ein JSON-Boolean und bleibt per Regressionstest angenommen, ein unbekanntes Wort ist ein Tippfehler mit Logzeile
- [Phase 05-hardening-und-store-einreichung]: require_url_shape pinnt NC_EXAPP_PUBLIC_URL vor json_info (WR-03) und laeuft mit grep -Eqz, weil ein Wert mit Zeilenumbruch sonst auf seiner ersten Zeile bestehen wuerde
- [Phase ?]: 05-16: option-b, EXAPP-05 wird mit der dokumentierten, gefuehrten MUCGPT-Luecke abgenommen (2026-08-20); gefuehrt ueber BL-12 und deferred-items.md, einloesbar per Protokoll in docs/client-setup.md
- [Phase 05]: Zweig N aus 05-12 ausgefuehrt: der 401 des Fensters vor der Aktivierung ist eine INFO-Zeile mit Ausweg, jeder andere Fehlschlag desselben Lesevorgangs bleibt ERROR; Overlay-Cache, vierte Registrierung am enabled=1-Hook und Selbstneustart wurden bewusst nicht gebaut, weil M1, M2 und M3 sie als wirkungslos belegen
- [Phase ?]: 05-14: Der Live-Nachweis fuer admin-gesetzte Werte braucht eine Registrierung ohne NC_MCP_PUBLIC_URL; AppAPI 34 kennt kein occ-Kommando dafuer, also unregister plus register ohne environment-variables-Block
- [Phase 06]: Der Default-Resolver von cimd.resolve_addresses ruft loop.getaddrinfo aus der Standardbibliothek statt anyio.getaddrinfo: docs/dependency-audit.md verlangt, dass ein direkt importiertes Paket direkt deklariert wird, und anyio liegt nur transitiv im Lock; der Plan-Wortlaut hätte pyproject.toml und uv.lock geaendert, was T-06-SC ausschliesst
- [Phase 06]: Der Typalias des injizierbaren Resolvers heisst AddressLookup und nicht Resolver: das Contract-Gate test_no_destructive_calls.py verbietet die Zeichenkette Resolve in src (MCP-Reference-Resolution haelt Zustand ueber einen Aufruf hinaus); der Parametername resolver bleibt klein, das Gate bleibt unangetastet
- [Phase 06]: Das Groessenlimit des CIMD-Abrufs bleibt in exapp/responses.py (bounded_response neben bounded_body) und wird von oauth/cimd.py importiert: zwei Groessenlimits in zwei Modulen sind genau die Kopie, die dieses Modul einmal abgeschafft hat
- [Phase 06]: MAX_DOCUMENT_BYTES (5120) und FETCH_TIMEOUT_SECONDS (5.0) sind Modulkonstanten ohne Env-Schalter: ein Schalter waere eine Grenze, die ein Admin versehentlich aufweichen kann (T-06-06); ein Test haelt fest, dass os.environ im Modul nicht vorkommt
- [Phase 06]: resolve_addresses verwirft den ganzen Namen, sobald EINE Adresse durchfaellt, und lehnt zusaetzlich eine Antwort ab, die keine Adresse ist, sowie einen leeren Hostnamen ohne den Resolver zu fragen: waehlte die Funktion die gute Adresse, waere die Regel per DNS-Antwort umschaltbar (T-06-02)
- [Phase 06]: Die RFC-8252-7.3-Portregel wirkt in consent.py an einer Stelle, aber der SDK-Handler vergleicht ein zweites Mal (authorize.py:180); provider.also_accepting(address) traegt die eine gematchte Adresse als Sicht fuer genau eine Anfrage dorthin, ohne etwas in die Registrierung zu schreiben
- [Phase 06]: loopback_match benutzt LOOPBACK_HOSTS (127.0.0.1, localhost, ::1) statt nur der IP-Literale des RFC: Claude Code schickt zur Laufzeit localhost, und D-35 laesst alle drei Namen ohnehin registrieren; frei ist nur der Port, ein Host-Wechsel bleibt eine Absage
- [Phase 06]: cimd_enabled ist ein eigener Schalter (NC_MCP_OAUTH_CIMD, Default an) mit harter Kopplung an DCR: die Kopplung schlaegt den explizit gesetzten Schalter, ein abgeschaltetes DCR ist ueber CIMD nicht umgehbar (T-06-15)
- [Phase 06]: Der CIMD-Abruf pinnt auf die gepruefte Adresse und haelt Name und Zertifikatspruefung ueber sni_hostname; genau eine Aufloesung pro Aufruf, kein Negativ-Cache (Drosselung liegt bei throttle.py).
- [Phase 06]: Das AS-Dokument kuendigt CIMD ueber client_id_metadata_document_supported = cimd_enabled or None an: bei abgeschaltetem Schalter FEHLT das Feld statt false zu sagen, weil der Spec-Rueckfall auf DCR nur greift, solange die Faehigkeit abwesend ist
- [Phase 06]: NC_MCP_OAUTH_CIMD ist als fuenfter environment-variables-Eintrag im Manifest deklariert (ohne default-Element), und ein Gate haelt die deklarierten Namen als Mengengleichheit gegen die Namen, die der Code liest: eine undeklarierte NC_MCP_-Variable wird vom Deploy-Daemon still verworfen
- [Phase 06]: Der CIMD-Zweig liegt in provider.get_client zwischen 'row is None' und _client_information, mit EINEM Aufrufpunkt fuer alle drei Faelle (keine Zeile, abgelaufene Frische, frische Zeile): _resolve_cimd fragt den Schalter zuerst, damit auch eine bestehende CIMD-Zeile bei abgeschaltetem DCR nicht mehr durchkommt
- [Phase 06]: _has_expired gilt nicht fuer Zeilen mit gesetztem cimd_fetched_at, und store.expired_clients nimmt sie ebenfalls aus: die Registrierungs-TTL wuerde ueber die Kaskade eine Nutzerverbindung beenden, die niemand beendet hat (Pitfall 4, T-06-31); purge_expired bleibt der Backstop fuer Zeilen ohne Verbindung
- [Phase 06]: Die Cache-Frist kommt aus dem Cache-Header der Antwort, gekappt auf 300 bis 3600 s; dafuer bekommt cimd.py fetch_document_and_lifetime als Grenze und fetch_document als Projektion davon, weil nur der Fetch den Header sieht
- [Phase 06]: Aus einem fremden Dokument werden nur client_name, redirect_uris, grant_types und response_types uebernommen; logo_uri und jedes andere Feld landen nicht im Datensatz, token_endpoint_auth_method wird auf none gesetzt (T-06-13, T-06-30)
- [Phase 06]: Die Herkunft eines Clients auf der Zustimmungsseite wird aus der Form der client_id erkannt (cimd.is_cimd_client_id) und nicht aus der Store-Spalte: ein zweiter Store-Zugriff hätte den einen Nextcloud-Roundtrip pro Request gekostet (T-06-39)
- [Phase 06]: Die Loopback-Warnung der Zustimmungsseite gilt auch fuer DCR-Clients: die Impersonationsgefahr haengt an der Rueckadresse und nicht am Registrierungsweg; eine leere Adressliste ist bewusst NICHT 'nur Loopback'
- [Phase ?]: 06-07: Die Messtopologie laeuft auf nextcloud:34.0.3-apache (occ status 34.0.3.2) und dem Connector aus dem Arbeitsbaum; der gleitende Tag 34-apache trug lokal 34.0.2.1, also nennt die Topologie-Tabelle Versionen und Digests statt Tags
- [Phase ?]: 06-07: Der Repository-Stand kommt nur durch Abmelden und Neuregistrieren in den Container: bootstrap_exapp.sh ueberspringt die Registrierung fuer eine bekannte App und hätte 0.1.1 weiterlaufen lassen; unregister ohne --rm-data laesst Volume und oc_appconfig_ex stehen, also ueberleben jane und die zwei Verbindungen
- [Phase ?]: 06-07: EXAPP-06 positiv beantwortet: auf 34.0.3 zeigt die Store-Oberflaeche die ExApp mit ihrem Deploy-Daemon, der Installationsknopf heisst Deploy and enable, und Remove steht im Aktionsmenue nur solange die App abgeschaltet ist (AppAPI: canUnInstall = !active && removable)
- [Phase ?]: 06-07: Der 34.0.3-Fix ist statisch nur als Aufruf sichtbar (Promise.allSettled mit e.isEnabled ? e.initialize() in dist/appstore-main.mjs, 95762 -> 95841 Bytes), nicht als neues exapp-Vorkommen; darum war die Gegenprobe der Recherche ergebnislos
- [Phase ?]: 06-07: Ein Browser-Schritt ohne Playwright-Werkzeug laeuft ueber das DevTools-Protokoll gegen das installierte Chrome, mit einem WebSocket-Client aus der Standardbibliothek: ein Paket zu installieren ist ausgeschlossen (T-06-SC)

- [Phase ?]: 06-08: CLIENT-04 ist gemessen und NICHT erfuellt: Cursor 3.2.16 registriert sich gegen 0.1.2 mit 201 und den zwei zulaessigen Adressen, schickt dann aber cursor://anysphere.cursor-mcp/oauth/callback an /authorize und wird mit 400 und der Seite E5 abgewiesen. Die Teilregistrierung hat den Fehlschlag von /register nach /authorize verschoben, nicht beseitigt
- [Phase ?]: 06-08: Die Ursache liegt belegt auf der Client-Seite: Cursor behaelt nach dem 201 seine eigenen drei Adressen statt die registrierten aus der Antwort zurueckzulesen (RFC 7591 3.2.1), also kann es nicht wissen, dass es die verworfene nimmt. Drei Gegenproben mit derselben client_id schliessen Instanz, Loopback-Portregel (loopback_match nimmt denselben Loopback mit anderem Port an) und Teilregistrierung als Ursache aus
- [Phase ?]: 06-08: Der Anmeldeknopf in Cursor ist ein Abmelden mit Neuregistrierung (LogoutServer + ReloadClient, 'No stored client information found'): er erzeugt eine neue client_id und laesst die alte Zeile unbenutzt zurueck, zwei Klicks also zwei DCR-Zeilen ohne Verwendung
- [Phase ?]: 06-08: Kein Fix in diesem Plan, die Entscheidung steht in BL-14 (Schema doch registrieren gegen D-35, wieder ganz abweisen wie 0.1.1, das Verworfene fuer den Client sichtbar machen, oder so lassen und auf das App-Passwort verweisen). CLIENT-04 bleibt in REQUIREMENTS.md unangehakt, weil sein Wortlaut eine durchlaufende Autorisierung verlangt
- [Phase ?]: 06-08: Fremde GUI-Software des Owners wird fuer eine Messung nicht neu gestartet und nicht mit Debug-Port angefahren: der Lauf hat bei needsAuth gehalten und gefragt, statt Cursor zu beenden (dasselbe Prinzip wie T-06-52)
- [Phase ?]: 06-08: jane's Passwort steht nirgends im Repository und occ user:resetpassword wurde NICHT benutzt, weil es die App-Passwoerter ihrer zwei OAuth-Verbindungen entwertet hätte (Demo-Substanz fuer CONF-01); die Frage wurde gegenstandslos, weil die Abweisung vor jeder Anmeldeseite liegt
- [Phase ?]: 06-09: Der CIMD-Live-Nachweis laeuft mit dem echten claude mcp login ueber eine Pseudo-Konsole (CreatePseudoConsole per ctypes): der Client verlangt ein Terminal, winpty lehnt ohne eigenes tty ab und ein Paket-Install ist ausgeschlossen (T-06-SC)
- [Phase ?]: 06-09: Der Beleg fuer ein AUSBLEIBEN braucht eine Positivkontrolle mit demselben Messwerkzeug: 0 Sockets auf Port 443 bei abgeschaltetem DCR gegen 4 Socket-Zustaende im identischen Lauf mit Schalter an, /proc-Zaehlung im Container
- [Phase ?]: 06-09: Drei der vier OAuth-Schalter sind Admin-Werte und brauchen nur occ app_api:app:config:set plus disable/enable; nur NC_MCP_OAUTH_CIMD steht nicht in CONFIG_KEYS und verlangt unregister (ohne --rm-data) plus register mit der Variable im json-info
- [Phase ?]: 06-10: Der Assistent des Demo-Drehbuchs ist ein echter MCP-Client, weil die Stationen Per-User-Schalter und Widerruf einen Akteur brauchen, der seine Verbindung ueber einen menschlichen Klick hinweg haelt
- [Phase ?]: 06-10: Die Probe der Schalter-Stationen ist claude mcp list und nicht der Werkzeugaufruf, weil dieser Client nach einem 403 einen eigenen Vermerk haelt; der Beleg mit Inhalt laeuft zusaetzlich am Draht mit Token in der Hand
- [Phase ?]: 06-10: Die stehengebliebene Werkzeugzahl in scripts/acceptance_all_tools.py (15 gegen 16) bleibt unangetastet und steht in deferred-items.md
- [Phase ?]: 06-11: Der neue E5-Satz nennt den App-Passwort-Weg, aber kein Client-Scheme, keine Adresse und keinen Protokollwert, und er gilt fuer alle vier Aufrufstellen in consent.py gleich: ein Satz, der nur fuer eine davon wahr waere, waere genau die Auskunft, die T-03-24 verbietet
- [Phase ?]: 06-11: Der Ausweg auf einer Fehlerseite steht in Worten und nie als Link (E8-Muster): der eine ausgehende Link dieser App ist die Anmeldeadresse, die Nextcloud selbst liefert, ein erfundener Link waere die Phishing-Form, vor der der Fusstext jeder Seite warnt
- [Phase ?]: 06-11: Kein Zusatzfeld in der DCR-Antwort: OAuthClientInformationFull lehnt ein nicht deklariertes Attribut ab und model_validate verwirft einen unbekannten Schluessel still (mcp 2.0.0, gemessen 2026-08-20); der Weg dorthin waere ein Eingriff in den Auth-Pfad fuer ein Feld, das kein gemessener Client liest
- [Phase ?]: 06-11: CLIENT-04 und ROADMAP SC3 mit Owner-Freigabe vom 2026-08-20 auf das Gemessene umformuliert und CLIENT-04 abgehakt; D-35 bleibt unveraendert, BL-14 ist mit Option, Datum, Messverweis und SDK-Rohbeleg geschlossen
- [Phase 08-erreichbarkeits-spike-und-tables]: MAIL-04 ist beantwortet: alle vier Mail-Wege (accounts 200, mailboxes 500, messages 403, OCS-Volltext 404) antworten unter reiner AppAPI-Impersonation mit JSON aus App-Code; MAIL-01 bis MAIL-03, CTX-02, SEC-01 und die Toolzahl in TOOL-15 bleiben wie geschnitten
- [Phase 08-erreichbarkeits-spike-und-tables]: Spike-Stufe 1 reicht ohne IMAP-Server: das Spike-Konto zeigt auf imap.invalid, weil occ mail:account:create-imap die Verbindung nicht prueft und jede Antwort aus App-Code den erreichten Controller beweist; GreenMail bleibt Vorlage in docs/spike-mail.md, compose.exapp.yml unveraendert
- [Phase 08-erreichbarkeits-spike-und-tables]: ensure_mail_account prueft die Ausgabe von occ mail:account:export und nicht dessen Exit-Code: der Befehl endet auch ohne jedes Konto mit 0, eine Exit-Code-Pruefung hätte bei jedem Lauf ein zweites Konto angelegt
- [Phase 08-erreichbarkeits-spike-und-tables]: Die drei Mail-Listen-Routen tragen SCOPE_IGNORE und bleiben ersetzbar; der Ausweg ist der Suchprovider mail plus die OCS-Volltextroute, und der Hinweis wandert in Phase 10 in den Modul-Docstring von clients/mail.py
- [Phase 08-erreichbarkeits-spike-und-tables]: Die v2-Tables-GETs bauen ihre URL über ocs.ocs_url, senden aber TABLES_HEADERS statt über ocs_get zu laufen: OCS_HEADERS traegt kein Content-Type, D-18 verlangt beide Pflichtheader auch auf einem GET dieser Familie
- [Phase 08-erreichbarkeits-spike-und-tables]: limit ist im Tables-Client ein Keyword ohne Default und wird auf 1 bis 200 gekappt, offset auf mindestens 0: eine Zeilen-URL ohne limit kann konstruktiv nicht entstehen, ein Weglassen ist ein Fehler beim Entwickler und kein Volltabellenlesen beim Nutzer
- [Phase 08-erreichbarkeits-spike-und-tables]: tables_available kommt aus tables.enabled und nicht aus der Sektionspraesenz: eine installierte, aber abgeschaltete Tables-App antwortet auf keinen Request und gilt fuer diesen Server als nicht vorhanden (Abweichung von Deck, das kein enabled veroeffentlicht)
- [Phase 08-erreichbarkeits-spike-und-tables]: Auf dem Tables-POST gibt es keinen Retry und nie einen Origin-Header: eine doppelte Zeile ist Datenkorruption, die dieser Server nicht aufraeumen kann, und mit Origin verlangt Nextclouds CORS-Middleware eine Basic-Reauthentifizierung, die unter Impersonation nicht existiert
- [Phase ?]: Plan 08-03: _may_create lebt in einer Funktion für beide Zwecke (can_create in der Projektion und die Vorprüfung von create_row), weil zwei Fassungen derselben Rechteregel zwei Wahrheiten wären
- [Phase ?]: Plan 08-03: TABLES-01 und TABLES-02 bleiben Pending bis zur Registrierung in 08-04; beide Anforderungstexte versprechen ein aufrufbares Werkzeug, und tools/list bleibt in diesem Plan bei 16
- [Phase ?]: Plan 08-03: kein clientseitiger Typvalidator für Zellwerte; der 400 der Tables-App wird mit ihrer eigenen Meldung durchgereicht, weil ein eigener Validator bei jedem neuen Spaltentyp veraltet
- [Phase ?]: Plan 08-03: der Tables-Block in vulture_whitelist.py ist aufgelöst statt erweitert; das Gate ist ohne jeden Eintrag grün, weil vulture namensbasiert arbeitet, und ein Eintrag ohne Wirkung verletzt die Regel der Datei
- [Phase 08]: Das Budget-Gate steht auf einer datierten Messung plus 15 Prozent (12801 Bytes bei 18 Werkzeugen, Gate 15000) und traegt zusaetzlich MAX_TOOL_BYTES = 1400 je Werkzeug. Eine Aggregatzahl mit Luft meldet keine Regression: calendar_create_event liegt bei 1351 Bytes, ein neues Werkzeug mit Absatzbeschreibung faellt ueber 1400 und wird damit sichtbar
- [Phase 08]: Die fuenf Tables-Nadeln des Destruktiv-Gates sind auf die Anfuehrungszeichen-Form eines Pfadliterals verankert, weil die erlaubten Routen tables/{id}/rows und rows/simple sonst mitgetroffen würden; je Nadel eine Gegenprobe plus der Nachweis, dass die erlaubten Formen durchgehen
- [Phase 08]: TABLES-01 und TABLES-02 werden mit der Registrierung abgehakt, wie 08-03 es angekuendigt hat; der Live-Nachweis gegen eine echte Instanz bleibt Gegenstand von 08-05
- [Phase 08]: Ein Status ab 400 ohne JSON-Koerper wird an seinem Status erklaert und nicht als Loginseite; die echte 404-Antwort auf eine unbekannte Tabelle traegt Content-Type text/html und einen leeren Koerper, und der alte Hinweis schickte das Modell zum App-Passwort statt zur Id
- [Phase 08]: Annahme A2 ist gemessen statt angenommen: Auswahl-Label und ISO-Datum gehen ohne clientseitige Umformung durch (ein Create mit allen vier Werten, Antwort 200); ungemessen bleiben usergroup, relation und die datetime-Untertypen
- [Phase 08]: Eine Tables-Textspalte ohne subtype macht jeden Zugriff auf die ganze Tabelle zu einem 500 (ColumnsHelper loest die Business-Klasse aus type plus subtype auf, TextBusiness existiert nicht); das Testgeruest legt Textspalten immer mit subtype line an
- [Phase 08]: Der Zwei-Konten-Beweis fuer Tables laeuft auf der Impersonation-Naht mit zwei Credential-Objekten im Modus appapi; Nextcloud beantwortet den Zugriff auf eine fremde Tabelle mit 404 und leerem Koerper statt mit 403 und gibt ihre Existenz damit nicht preis
- [Phase 09-talk]: get_messages gibt tuple[list[dict], int | None] zurück: Nachrichten plus Fortsetzung aus dem Antwort-Header X-Chat-Last-Given; ein fehlender oder nicht numerischer Header ergibt None, also kein Angebot einer nächsten Seite
- [Phase 09-talk]: Die 304 des leeren Verlaufs wird im Talk-Client vor parse_ocs abgefangen; _check_transport bleibt unverändert, weil 304 nur an dieser einen Route eine Bedeutung hat
- [Phase 09-talk]: _OK_STATUS trägt 201, weil OCS v2 den rohen Status in ocs.meta.statuscode schreibt und die Talk-Sende-Route 201 als einzigen Erfolg dokumentiert
- [Phase 09-talk]: Die spreed-Sektion gilt nur als vorhanden, wenn sie nicht leer ist: ein für den Nutzer abgeschaltetes Talk antwortet mit einem leeren Array
- [Phase 09-talk]: spreed_chat_max_length liest config.chat.max-length, DEFAULT_CHAT_MAX_LENGTH 32000 als Rückfall; die Zahl gehört der Instanz
- [Phase 09-talk]: TALK-01 bis TALK-03 bleiben Pending: dieser Plan liefert den Transport, die Anforderungen sprechen von talk_browse und talk_send und sind erst mit Plan 09-02 und 09-03 wahr
- [Phase 09-talk]: Drei Namen des Talk-Transports und zwei Capabilities-Felder stehen vorübergehend in vulture_whitelist.py, nach dem Vorbild von Plan 08-02; sie verlassen die Liste mit Plan 09-02
- [Phase 09-talk]: talk_send kommt hinter einen Admin-Schalter nach Weg A der Recherche: der aufgeloeste Wert wird beim Start nach os.environ geschrieben (genau ein Schluessel, entry_exapp.main Zeile 323), und talk_send_enabled liest ihn pro Aufruf: ein Werkzeug hat kein resolved-Mapping in der Hand; Weg B (pro Sendevorgang aus Nextcloud lesen) kostet einen Roundtrip je Nachricht und muesste fail closed sein, Weg C (Wert per Header) haengt am Bereinigen eines von aussen setzbaren Headers
- [Phase 09-talk]: talk_send_enabled prueft not in _FALSE_VALUES und nicht in _TRUE_VALUES, weil der Default an ist: ein leerer und ein unverstaendlicher Wert duerfen eine zugesagte Faehigkeit nicht still entfernen (T-09-13); dns_rebinding_protection macht es umgekehrt, weil dort die Variable abschaltet
- [Phase 09-talk]: os.environ ist kein Modulzustand im Sinne von D-20, sondern die Prozessumgebung: ALLOWED_MODULE_STATE bleibt bei zwei Eintraegen, tests/contract/test_no_destructive_calls.py ist unveraendert, und ein Quelltext-Test belegt genau eine Schreibstelle samt Kommentarblock
- [Phase 09-talk]: talk_send ist der sechste und letzte Eintrag von CONFIG_KEYS: die vier OAuth-Werte bleiben beieinander, weil registry.client_policy zwei davon als eine Antwort liest, und ein Talk-Schalter dazwischen wuerde diese Gruppierung zerreissen
- [Phase 09-talk]: TALK-04 bleibt Pending: der Wortlaut verlangt die Wirkung am Werkzeug samt Fehlersatz, und das Werkzeug entsteht erst mit Plan 09-03; Schicht 1 (Formular) und Schicht 2 (Overlay-Lesepfad) sind hier belegt
- [Phase 09-talk]: tools/talk.py liest auf der Nachrichtenebene zuerst die Konversationsliste: Sie ist die einzige Quelle des Anzeigenamens fuer den Envelope und macht ein erfundenes Token zu unserem eigenen Satz, ohne dass Nextcloud es je in einem Pfad sieht (T10 gilt damit auch beim Lesen)
- [Phase 09-talk]: Eine Erwaehnung wird an mention-id oder am Platzhalternamen erkannt, nicht am Typ allein: {actor} traegt in Talk ebenfalls type=user, ein Praefix darauf hätte jede Nachricht so aussehen lassen, als erwaehne sie ihren eigenen Autor
- [Phase 09-talk]: Keine Kappungsmarkierung im Nachrichtentext, sondern das Feld truncated daneben: Ein Marker im fremden Text ist ein Angriffsweg (ME-03), und eine Chatnachricht ist der billigste Ort dafuer, weil jeder Teilnehmer schreiben darf
- [Phase 09-talk]: TALK-01 bis TALK-04 bleiben Pending: Der Wortlaut aller vier spricht von den Werkzeugen talk_browse und talk_send; registriert werden sie erst mit Plan 09-04, TALK-02 braucht zusaetzlich die Live-Messung
- [Phase 09-talk]: BUDGET_BYTES bleibt 15000: 14312 Bytes bei 20 Werkzeugen gemessen ,  Eine Anhebung erfolgt nur gegen eine Messung, die sie braucht; die Messzeile steht trotzdem im Skript, damit TOOL-15 in Phase 11 auf einer lesbaren Zahl fortschreibt
- [Phase 09-talk]: spreed 24.0.4 bringt kein listendes occ-Room-Kommando mit: die Idempotenz der Testkonversationen laeuft nach Namen ueber GET /apps/spreed/api/v4/room mit dem Konto selbst, und der Name wird auf seinem ASCII-Praefix gematcht, weil PHP jeden Umlaut einer JSON-Antwort als \uXXXX-Escape schreibt
- [Phase 09-talk]: Werte in .env.test und .env.exapp tragen keine Leerzeichen: die Dateien werden mit set -a und . gelesen, und ein unquotierter Wert mit Leerzeichen laesst die Shell sein zweites Wort als Kommando ausfuehren (im ersten Lauf von 09-05 gemessen)
- [Phase 09-talk]: Erfolgskriterium 3 ist live gemessen: lastReadMessage 23 zu 23, unreadMessages 0 zu 0, unreadMention False zu False, lastCommonReadMessage 23 zu 23 um einen Verlauf-Lesevorgang mit einer Nachricht im Fenster; die Messung fuellt vorher, weil setReadMarker nur einen Marker bewegen kann, der ein Ziel hat
- [Phase 09-talk]: Bobs Zugriff auf eine fremde Talk-Konversation: die Instanz antwortet GET 404 und POST 404 und gibt die Existenz nicht preis; der Connector kommt nie so weit, seine Absage entsteht aus der eigenen Konversationsliste vor jedem Talk-Pfad
- [Phase 09-talk]: Der Admin-Schalter talk_send ist auf beiden Topologien an (NC_MCP_TALK_SEND ungesetzt); der Integrationstest stellt den Zustand fest und behauptet zusaetzlich beide Enden des Schalters, weil ein einmal gespeicherter Wert jedes Neubauen des Containers ueberlebt
- [Phase 10]: Byte-Kappe des Volltexts auf 32 KiB (32768 Bytes) entschieden statt der 16 KiB des Startwerts: der gemessene Newsletter ergibt nach der Wandlung 25582 Bytes und waere bei 16 KiB gekappt, obwohl er der Normalfall ist; gesetzt wird die Zahl in Plan 10-05
- [Phase 10]: tags: der Mail-Filtergrammatik nimmt die numerische Tag-Id, nicht das IMAP-Label; MessageMapper vergleicht tags.tag_id, gemessen: tags:1 trifft, tags mit $label1 trifft nicht (korrigiert 10-RESEARCH.md)
- [Phase 10]: start: mit ISO-Datum liefert NULL Treffer statt praktisch allem (Zeichenkettenvergleich gegen die Integer-Spalte sent_at); K4 bleibt richtig, nur schaerfer: ein ISO-Wert gehoert abgelehnt
- [Phase 10]: MAIL-01 bis MAIL-03 bleiben nach Plan 10-01 Pending: der Plan liefert Messwerte, kein Werkzeug; dieselben Requirement-Ids stehen in sechs weiteren Plaenen der Phase
- [Phase 10]: previewText ist an echten Daten immer gesetzt und von der App selbst bei etwa 250 Zeichen gekappt; die leere Zeichenkette heisst 'kein Textkoerper' und nicht 'Vorschau fehlt'
- [Phase 10-mail]: get_message gibt (Nutzlast, body_missing) zurueck; body_missing ist genau bei HTTP 206 True, also Erfolg ohne body, und ist bewusst kein Sentinel im Dictionary, weil eine Mail ohne Textkoerper body als leeren String liefert
- [Phase 10-mail]: Der zweite Erkennungskanal heisst load_mail, laeuft ueber /core/navigation/apps und fuellt dieselbe Cache-Zeile mit dem urspruenglichen Zeitstempel; ein eigener Cache waere ein dritter Modulzustand und damit eine Review-Entscheidung (D-20)
- [Phase 10-mail]: ocs._OK_STATUS bleibt frozenset({100, 200, 201}); 206 wird lokal im Mail-Client behandelt, wie Phase 9 die 304 lokal gehalten hat
- [Phase 10-mail]: Eine leere oder deformierte Navigationsliste ist ein ToolError mit Ausweg und nie die Aussage Mail fehlt; jede Instanz hat Navigation
- [Phase 10-mail]: Der HTML-zu-Text-Wandler heisst html_text.to_text(html: str) -> str, kappt nie und wirft nie: die Byte-Kappe gehoert zur Aufrufstelle, wo der Schnitt markiert werden kann
- [Phase 10-mail]: Fremdes Mail-HTML wird aus UTF-8-Bytes mit HTMLParser(no_network=True, encoding=utf-8) geparst statt aus dem String: gemessen identisches Ergebnis, aber eine XML-Deklaration wirft dann nicht mehr und ein widersprechendes meta charset luegt nicht mehr
- [Phase 10-mail]: Der dritte Marker heisst FINAL_TRUNCATION und nennt kein Werkzeug und keinen Offset; er steht ab der ersten Zeile in _PATTERNS, damit without_marks ihn ohne Aenderung am Filter mitentfernt (ME-03)
- [Phase 10-mail]: Der Rest eines internen DTD-Subsets (die Zeichen ]>) und ein Non-Breaking-Space bleiben im Text: eine zweite Reinigungsregel ueber fremdem Text waere eine zweite Wahrheit
- [Phase 10-mail]: MAIL-02 bleibt Pending: Plan 10-03 baut nur die zwei Bausteine, das Volltext-Werkzeug entsteht in Plan 10-05
- [Phase 10-mail]: MAX_PREVIEW_BYTES steht auf 400 Bytes; die App kappt previewText selbst bei rund 250 Zeichen (gemessen 10-01), die Kappe ist die Absicherung gegen eine Fassung, die das nicht mehr tut
- [Phase 10-mail]: der Filter wird gegen eine Positivliste FILTER_TYPES geprueft, vor der App-Erkennung und damit bei null Requests: der Parser der Mail-App verwirft einen unbekannten Typ still und antwortet mit der ungefilterten Liste
- [Phase 10-mail]: Cursor-Scope-Schluessel der Mail-Familie ist m (mailbox_id), Position o ist der dateInt der aeltesten Nachricht der Seite; ohne positiven Zeitstempel wird kein next ausgegeben, weil Cursor 0 die erste Seite wiederholen wuerde
- [Phase 10-mail]: die strikte Sekundengrenze des App-Cursors (sent_at kleiner) wird benannt und nicht repariert, wie schon beim halboffenen Kalenderfenster; eine eigene Korrektur waere eine zweite Wahrheit ueber die Reihenfolge der App
- [Phase 10-mail]: MAIL-01 und MAIL-03 bleiben nach Plan 10-04 Pending; das Werkzeug existiert, aber die Registrierung gehoert zu 10-06 und der Live-Nachweis zu 10-08
- [Phase 10-mail]: 10-05: MAX_MAIL_BYTES = 32768 als eigene Byte-Kappe des Mail-Volltexts, begruendet durch die Messung aus 10-01
- [Phase 10-mail]: 10-05: Vertrauens-Signale flach in metadata und nie im text; fehlendes dkimValid ergibt unchecked
- [Phase 10-mail]: 10-05: url einer Mail ist die Mail-App-Route, nie eine Adresse aus der Antwort
- [Phase ?]: Phase 10-06: BUDGET_BYTES 15000 -> 18500 auf der Messung 15736 Bytes bei 21 Werkzeugen (plus 15 Prozent, aufgerundet); ausdruecklich Zwischenstand, TOOL-15 in Phase 11 verankert neu
- [Phase ?]: Phase 10-06: mail_browse war 1585 Bytes und damit ueber MAX_TOOL_BYTES 1400; gekuerzt wurde die Beschreibung, nicht die Grenze (A5); Endstand 1377 Bytes, groesstes Werkzeug der Oberflaeche
- [Phase ?]: Phase 10-06: das Mail-Schreibverbot besteht aus neun Nadeln mit je einer Gegenprobe durch _violations, der Positivliste ALLOWED_MAIL_ROUTES mit vier Formen und dem Nur-GET-Test ueber clients/mail.py und tools/mail.py; CREATE_TOOLS bleibt bei sechs
- [Phase ?]: 10-07: Trifecta-Text in drei Laengen (lang in docs/privacy.md, gekuerzt in den READMEs, nur der Ausgangskanal-Absatz im Store-Text)
- [Phase ?]: 10-07: Store-Beschreibung nennt Mail-Ebenen statt Postfachnamen; die Vokabular-Falle ist als Test mit Begruendung eingefroren
- [Phase ?]: 10-07: Werkzeugzahlen in der Doku als Wort, weil der Zaehlwaechter Ziffern vor 'tools' liest
- [Phase ?]: 11-01: Id-Kinds heissen message:<token>:<messageId> und table:<tableId> (eine Id adressiert ein Objekt, keine App); PROVIDER_KINDS hat jetzt sechs Eintraege inklusive talk-message-current, belegt statt vermutet (CurrentMessageSearch erbt performSearch von MessageSearch)
- [Phase ?]: 11-01: Ein Tables-Treffer auf eine View, jeder Mail-Treffer und talk-conversations bleiben bewusst kind=url; der Grund steht je namentlich im Modul-Docstring von provider_map.py
- [Phase ?]: 11-02: Genau eine Talk-Nachricht wird ueber GET .../chat/{token}/{messageId}/context gelesen, nie ueber lastKnownMessageId-Arithmetik: die Kontextroute liefert die Zielnachricht mit (includeLastKnown=true), die Arithmetik gaebe bei geloeschter oder gefilterter Zielnachricht unsichtbar eine Nachbarnachricht aus
- [Phase ?]: 11-02: READ_ONLY_PARAMS steht nicht in get_message_context, weil die Route sie nicht annimmt; die Nebenwirkungsfreiheit kommt aus der Route selbst (Timeout 0, markNotificationsAsRead false, kein updateLastReadMessage in spreed 24.0.4) und wird in 11-06 ueber die Konversationsliste gemessen
- [Phase ?]: 11-02: get_message_context ist eine Welle vor seinem Aufrufer im vulture_whitelist geparkt (Muster Tables 08-02, Talk 09-01, Mail 10-02); Plan 11-03 entfernt den Eintrag mit dem fetch-Zweig, der ihn aufruft
- [Phase 11]: 11-03: fetch loest jetzt message:<token>:<messageId> und table:<tableId> auf; TABLE_ROWS=20 und MAX_TABLE_BYTES=4096 sind ausdrueckliche Setzungen, MESSAGE_CONTEXT_LIMIT=1 traegt die spreed-Rechnung aus 11-02
- [Phase 11]: 11-03: eine fehlende, geloeschte oder ausgefilterte Zielnachricht ist ein ToolError mit beiden Gruenden und talk_browse level=messages als Ausweg, nie eine Nachbarnachricht (T-11-13); ein leeres Fenster (304) ist derselbe Satz
- [Phase 11]: 11-03: der Nachrichten-Zweig haengt keinen zweiten Kappungsmarker an (Phase 9, ME-03), die Kappung erscheint als metadata[truncated]=true; der Tabellen-Zweig kappt in der Reihenfolge Marker-Filter je Zelle, Byte-Kappe, FINAL_TRUNCATION
- [Phase 11]: 11-03: TOOL-16 bleibt Pending, weil prepare_context dieselben Treffer noch als resolvable false ausweist (Pitfall 1) und die Live-Messung zu 11-06 gehoert
- [Phase ?]: Phase 11-04: KIND_BUCKETS bleibt bei drei Kinds und _short liest die Aufloesbarkeit nur aus dem Treffer; der Talk-Digest ist die einzige Talk-Aussage im Buendel, ein Talk-Bucket waere eine zweite Wahrheit ueber dieselbe App
- [Phase ?]: Phase 11-04: EXCERPT_KINDS existiert getrennt von KIND_BUCKETS; die Gruppierung der Antwort und die Frage, wessen Inhalt der Server ungefragt liest, sind zwei Entscheidungen (T-11-24)
- [Phase ?]: Phase 11-04: DIGEST_PREVIEW_BYTES misst Bytes statt Zeichen (gegen den Wortlaut von CTX-01), TALK_BUDGET=5.0 ist als Setzung markiert und wird in 11-06 live geprueft
- [Phase ?]: Phase 11-04: der Antwortschluessel talk ist immer da und immer eine Liste; leer ohne degraded heisst nichts Ungelesenes, leer mit degraded heisst konnte nicht gelesen werden
- [Phase ?]: 11-05: das Mail-Bein liefert einen Envelope {results, total} statt einer Liste, weil der Kappungssatz die Gesamtzahl nennt, die eine gekappte Liste nicht mehr traegt
- [Phase ?]: 11-05: MAIL_BUDGET = 10.0 ist eine Setzung und weiter als TALK_BUDGET, weil das Bein 1+N ist und nicht ein Request; MAX_MAIL_ACCOUNTS = 3 kappt fremdes Mengenwachstum mit eigenem degraded-Eintrag
- [Phase ?]: 11-05: die Mail-Zaehler kommen ausschliesslich aus der Postfachliste; das unread-Feld des Navigationseintrags ist verboten und im Docstring mit der Messung begruendet (0 bei sechs ungelesenen Nachrichten)
- [Phase ?]: 11-05: eine fehlende Inbox bleibt ein fehlendes Feld plus ein benannter degraded-Satz, niemals inbox_unread 0; beide Mail-Ebenen fragen mit limit=MAX_LIMIT, damit die Kappe dieser Antwort immer die eigene ist
- [Phase ?]: 11-05: die prepare_context-Beschreibung nennt alle vier Quellen und kostet gemessene 33 Bytes (625 auf 658, Oberflaeche 15736 auf 15769); Plan 11-07 braucht fuer ein Gate bei 18000 jetzt 117 statt 84 Bytes Diaet
- [Phase ?]: 11-06: Keine der vier Zeitbudget-Konstanten wird geaendert: jedes gedeckelte Bein liegt mehr als hundertfach unter seiner Decke (Kalender 0,07 s bei 10 s, Talk 0,04 s bei 5 s, Mail 0,06 s bei 10 s), und eine Absenkung wuerde bei der ersten langsamen Instanz Degradation im Normalfall erzeugen
- [Phase ?]: 11-06: Die Obergrenze der Wanduhr-Messung ist CALENDAR_BUDGET (10 s) und nicht die Referenz 0,84 s: eine Grenze an der Referenz wuerde den Entwicklungsrechner messen statt den Code, die groesste Einzeldecke faengt genau den sequenziellen Regress (T-11-40)
- [Phase ?]: 11-06: Ein Buendel zahlt bei kaltem Capabilities-Cache drei Erkennungsrequests und nicht zwei (zweimal /cloud/capabilities, einmal /core/navigation/apps); zwei gehoeren dem Mail-Bein, der dritte entsteht aus dem Rennen des Talk-Beins um denselben leeren Cache-Eintrag. Das Rennen wird nicht behoben (eine Cache-Sperre waere strukturell), der Befund steht im Messdokument
- [Phase ?]: 11-06: truncated auf der Talk-Nachrichtenebene heisst "die App hat eine Fortsetzungs-Id mitgegeben" und nicht "es gibt mehr zu lesen"; es taugt deshalb nicht als Vollstaendigkeitspruefung, und eine Divergenz zwischen unread und den lesbaren Nachrichten gilt nur, wenn ein Fenster sie entscheidet
- [Phase ?]: 11-06: Die Falle T12 (unread == 1 bei leerer Historie) ist auf der Messtopologie nicht vorhanden; der Beweis "unread ist kein Nachrichtenzaehler" laeuft ueber den umgekehrten und staerkeren Fall (sechs lesbare Nachrichten, unread 0)
- [Phase 11]: 11-07: Verschieben ist keine Diaet: Tool-Docstring und Field-Beschreibung sind zwei Schluessel desselben tools/list-Payloads, ein Docstring-Umbruch kostet zwei Bytes; nur Komprimieren spart (die vom Plan verlangte Verschiebung war gemessen +4 Bytes)
- [Phase 11]: 11-07: BUDGET_BYTES 18500 -> 18000, verankert auf 15612 gemessenen Bytes bei 21 Werkzeugen; 17500 hätte 395 Bytes mehr gebraucht, also 23 Prozent der verbliebenen Prosa der fuenf Werkzeuge
- [Phase 11]: 11-07: MAX_TOOL_BYTES bleibt 1400 mit eigener Messzeile; groesstes Werkzeug ist jetzt calendar_create_event (1351) statt mail_browse (1331), und die 15-Prozent-Regel ergaebe hier eine verbotene Anhebung auf 1553
- [Phase ?]: 11-08: Die Werkzeugoberflaeche hat eine Wahrheit: das Abnahmeskript liest die erwartete Menge aus client.list_tools(), die literale 21er-Liste und EXPECTED_TOOLS sind weg; die Zahl lebt in tests/contract/test_tool_surface.py
- [Phase ?]: 11-08: Ein Antwortschluessel traegt je Ebene genau eine Bedeutung: die Eintragsebene der Mail-Antwort heisst preview_truncated, die Antwortebene behaelt truncated (IN-01); dieselbe Doppelbedeutung in talk.py ist als DF-11-01 zurueckgestellt
- [Phase ?]: 11-08: Ein Docstring nennt keine Zahl, die ein Test derselben Datei pinnt: variable_problems verweist auf die Gate-Funktion statt auf vier oder sechs Variablen (IN-03)
- [Phase ?]: 11-09: Release-Nummer ist 0.1.8 (0.1.4 bis 0.1.7 liegen im Store); die 0.1.6 im Phasentitel ist ueberholt
- [Phase ?]: 11-09: IN-02 geschlossen durch die nachgetragene CHANGELOG-Sektion 0.1.5, nicht durch Linkkorrektur: der Tag v0.1.5 existiert (Run 32569019469)
- [Phase ?]: 11-09: uv.lock wird bei einem Versions-Bump mitcommittet: uv schreibt die eigene Projektversion hinein, so wie in den Release-Commits 0.1.5, 0.1.6 und 0.1.7
- [Phase 11-b-ndelung-budget-und-release-0-1-6]: Release 0.1.8: der Tag entstand erst nach ausdrücklicher Owner-Freigabe, und die Freigabe umfasste auf Vorlage hin auch den Branch-Push, weil 42 Commits der Phase nur lokal lagen und die Store-Beschreibung Doku- und Screenshot-URLs auf main verlinkt
- [Phase 11-b-ndelung-budget-und-release-0-1-6]: Release 0.1.8: signiert wurde das heruntergeladene Release-Asset (45546 Bytes) und nicht das lokal gebaute (45710 Bytes); die Signatur steht in keiner Datei und wird bei Bedarf neu berechnet
- [Phase 11-b-ndelung-budget-und-release-0-1-6]: Release 0.1.8: die verzögerte Sichtbarkeit im Katalog-Endpunkt wurde als Cache-Verhalten notiert und abgewartet, nicht mit einer weiteren Version beantwortet
- [Phase ?]: 12-01: TOOL-17 benennt die Eintragsebene um (message_truncated) und nicht die Antwortebene: die Antwortebene ist in vier Tests, der cursor-Field-Description und context._digest verankert
- [Phase ?]: 12-01: metadata['truncated'] in fetch bleibt woertlich, weil fetch genau eine Nachricht und damit genau eine Ebene antwortet
- [Phase ?]: 12-01: keine Gegenkompression in reg_talk.py (858 von 1400 Bytes Luft, Mail hatte 24); nach dem Edit 912 Bytes und 15711 von 18000, kein Gate angehoben
- [Phase ?]: Phase 12 TOOL-18: Whitespace im url-Rest ist gegen encode_url ausgelegt: whitespace-only und fuehrender Whitespace werden von ids.parse abgelehnt, inneres Whitespace bleibt erlaubt, weil encode_url('https://a b') genau diesen Wert baut
- [Phase ?]: Phase 12 TOOL-18: neue Funktion ids.encode_card_short, weil ids.parse die Kurzform card:cardId seit Phase 1 akzeptiert, der Codec sie aber nicht bauen konnte und provider_map sie deshalb von Hand baute (zweiter Handbau, den 12-02-PLAN nicht kannte)
- [Phase ?]: Phase 12 TOOL-18: die Mail-Id-Ausgabe ist byte-identisch geblieben (Filter _number(databaseId) grosser 0 vor der Projektion); weder die Umstellung noch die neuen url-Ablehnungen gehen in den Changelog von 0.1.9
- [Phase ?]: Phase 12-03 (SEC-02c): die Wortliste FORBIDDEN_VOCABULARY bleibt in tests/unit/test_exapp_env_setup.py und das Gate waechst um sie herum; zwei Stellen mit demselben Wort waeren zwei Wahrheiten (IN-03), ein Umzug hätte an einem gruenen Sicherheits-Gate gebaut
- [Phase ?]: Phase 12-03 (SEC-02c): LICENSE ist die zweite benannte Ausnahme des Vokabular-Gates (AGPL-Volltext traegt das Wort in LICENSE:653); Fremdtext im Store-Archiv, eine Bearbeitung wuerde den Lizenztext verfaelschen
- [Phase ?]: Phase 12-03: ab jetzt steht CHANGELOG.md unter dem Vokabular-Gate, relevant fuer den 0.1.9-Block in Phase 13
- [Phase ?]: Phase 12-03 (SEC-02b): die Nicht-leer-Behauptung eines Quelltext-Gates darf nicht auf der Zeile ankern, die die Gegenprobe manipuliert; Anker ist level=accounts, nicht level=mailboxes
- [Phase ?]: Phase 12-03: Gegenproben, die eine echte Datei manipulieren, lesen und schreiben Bytes (write_bytes); read_text/write_text dreht auf diesem Windows-Host die Zeilenenden und hinterlaesst einen unsauberen Baum
- [Phase ?]: Phase 12 TOOL-19: der oeffentliche Name ist one_room und nicht room_of (IN-06); one_message ist die vorhandene Konvention fuer 'genau ein Objekt aus einer gelesenen Menge', ein zweiter Namensstil im gleichen Modul waere eine Konvention mit zwei Formen
- [Phase ?]: Phase 12 TOOL-19: Modulgrenze als AST-Gate in tests/contract/test_module_boundaries.py statt ruff --select SLF; die Messung im Modul-Docstring begruendet es (3 SLF-Treffer in src/, davon 2 legitime Klassen-Interna, 53 in tests/), und AST sieht die vier Prosa-Nennungen in tools/context.py konstruktionsbedingt nicht
- [Phase ?]: Phase 12 TOOL-19: die Umbenennung _room zu one_room gehoert NICHT in den Changelog von 0.1.9 (kein Werkzeugname, kein Antwortschluessel, keine Id-Form, tools/list bleibt 15711 Bytes bei 21 Werkzeugen); die README-Korrektur spreed zu talk-conversations gehoert als Doku-Korrektur hinein
- [Phase ?]: Phase 12 TOOL-19: REAL_BUT_UNREGISTERED lebt im Test und nicht in provider_map.py, weil das Produktionsmodul eine Uebersetzungstabelle fuehrt und keine Liste der Ids, die es nicht uebersetzt
- [Phase ?]: Phase 13 Plan 01: die uv.lock-Selbstangabe (Zeile 472) wird beim Bump mitgezogen wie beim 0.1.8-Vorbild 8392680, aber per Texteditierung statt per uv lock: kein Gate haelt sie, ein Lock-Lauf hätte Dependency-Zeilen bewegt
- [Phase ?]: Phase 13 Plan 01: CRLF-Dateien (appinfo/info.xml, drei READMEs) werden byte-exakt per Python rb/wb ersetzt, mit Vorab-Zaehlung der Treffer je Datei; belegt durch Ein-Zeilen-Diffs statt Massen-Diffs
- [Phase ?]: Phase 13 Plan 01: der 0.1.9-Changelog-Block nennt nur die zwei nutzersichtbaren Phase-12-Uebergaben (message_truncated, talk-conversations); die Rubrik Added bleibt leer und gehoert Plan 13-02 (Enterprise-Fake-Door)
- [Phase ?]: Phase 13 Plan 02: Enterprise-Fake-Door in vier Fassungen (drei READMEs plus drei Manifest-Beschreibungen); Ueberschrift unuebersetzt, Ehrlichkeitssatz je Fassung eigenstaendig, kein Preis und kein free/kostenlos
- [Phase ?]: Phase 13 Plan 02: Owner-Entscheid 26.08. zu D-07: KEIN Enterprise-Issue, keine Enterprise-Interna im Repo; Issue-Entwurf + Go-Kriterium aus dem Repo entfernt und nur noch lokal in scripts/docs/specs/ideation-isv-monetarisierung-2026-08-25/ (issue-entwurf-enterprise-signals.md, issue-go-kriterium.md); Enterprise-Abschnitt in READMEs/Store-Beschreibung bleibt (die Fake-Door selbst)
- [Phase ?]: Phase 13-03: CIMD-Nachmessung ueber Messweg A gefahren (echter Client Claude Code 2.1.233 gegen 127.0.0.1:5000/mcp_connector:0.1.9, Digest sha256:1183f845); damit ist die Client-Wahl belegt und nicht nur die Serverseite
- [Phase ?]: Phase 13-03: occ mcp_connector:purge --force bewusst nicht gefahren, weil es jede Verbindung der Instanz beendet und zwei lebende Verbindungen des Kontos jane bestehen; claude mcp logout ruft /revoke und erfuellt beide Haelften der Vorgabe
- [Phase ?]: Phase 13-03: alle vier .planning-Verweise in docs/oauth-setup.md geschlossen (Plan nannte zwei); jede Stelle traegt die Aussage jetzt selbst, mit Datum und Ergebnis
- [Phase ?]: Phase 13-03: ConPTY per ctypes braucht STARTF_USESTDHANDLES mit den Konsolen-Handles 0x3/0x7/0xB, sonst haengt das Kind an der Pseudo-Konsole und schreibt trotzdem auf die Pipes des Elternprozesses
- [Phase ?]: Phase 13 Plan 04: die Werkzeugoberflaeche traf den Erwartungswert 15711 Bytes ueber 21 Werkzeuge exakt; BUDGET_BYTES bleibt 18000 und MAX_TOOL_BYTES bleibt 1400 (D-04)
- [Phase ?]: Phase 13 Plan 04: die Proof-Zeile zu Runbook-Schritt 3 nennt weder Signatur noch Bytezahl; 47546 Bytes und sha256 4f2a05fe stehen nur in der SUMMARY als Vergleichswert fuer Plan 13-06
- [Phase ?]: Phase 13 Plan 04: die Testzahl 2812 bei 163 deselektiert kam aus einem zweiten Lauf ohne zusaetzliches -q, weil addopts bereits -q traegt und -qq die Summenzeile unterdrueckt; das Runbook-Kommando blieb woertlich
- [Phase ?]: Phase 13: der Tag v0.1.9 entstand erst nach der woertlichen Owner-Antwort freigeben (2026-08-25T18:27Z), Branch-Push davor; Weg fuer Schritt 7 ist die angemeldete Store-Sitzung im Browser
- [Phase ?]: Phase 13: die Proof-Zeile zu Runbook-Schritt 4 wurde geteilt, eine Zeile fuer den Push vor dem Checkpoint und eine fuer Tag und Workflow nach dem gruenen Lauf
- [Phase ?]: Phase 14-01: DOC-01b per Entfernung der [Unreleased]-Linkdefinition gelöst, weil CHANGELOG.md keinen solchen Abschnitt führt; Regel für Phase 15: eine Definition entsteht erst wieder mit dem Abschnitt, der sie referenziert
- [Phase ?]: Phase 14-01: der Ampersand-Kommentar in appinfo/info.xml beschreibt jetzt den Zustand (keine der beiden Spendenadressen trägt einen Ampersand) plus die Entity-Regel für eine künftige Adresse; keine URL und keine Elementfolge angefasst
- [Phase ?]: Phase 15-01: der Changelog-Block 0.1.10 trägt die Kopfzeile 2026-08-28 (lokaler Kalendertag; in UTC war beim Commit noch der 2026-08-27); Plan 15-03 prüft das Datum vor dem Tag und hebt es, falls der Tag an einem anderen Kalendertag entsteht
- [Phase ?]: Phase 15-01: EXAPP-10 bleibt Pending, weil die Anforderung Release 0.1.10 im Store verlangt; alle vier Pläne der Phase tragen sie, abgehakt wird sie erst am Ende von Plan 15-04 nach Tag, Signatur und Upload
- [Phase ?]: Phase 15-01: die WR-02-Korrektur am 0.1.9-Block bekommt keinen eigenen Changelog-Eintrag; sie fährt als Prosa des Vorversions-Blocks mit dem 0.1.10-Asset mit und schließt damit W-1 des v1.3-Audits
- [Phase ?]: Phase 15-01: uv.lock ist die sechste Versionsstelle und wird per Texteditierung gehoben, nie per uv lock oder uv sync; alle Prüfläufe der Phase laufen mit uv run --no-sync
- [Phase 15-release-0-1-10]: Werkzeugoberflaeche misst 15712 statt 15711 Bytes; Ursache ist die serverInfo-Versionszeichenkette im tools/list-Envelope (0.1.9 auf 0.1.10 = ein Zeichen mehr), per Gegenprobe auf 15711 zurueckgerechnet; kein Grenzwert angehoben, Erwartungswert fuer den naechsten Lauf ist 15712
- [Phase 15-release-0-1-10]: das lokal gebaute 0.1.10-Archiv misst 47299 Bytes (sha256 4682e06d) und ist NICHT das signierte Artefakt; Plan 15-04 signiert das heruntergeladene Asset
- [Phase 15-release-0-1-10]: Plan 15-03: die Owner-Freigabe fuer den Tag v0.1.10 kam am 2026-08-28 04:49Z woertlich als freigeben; Weg fuer Runbook-Schritt 7 in Plan 15-04 ist die angemeldete Store-Sitzung im Browser
- [Phase 15-release-0-1-10]: Plan 15-03: die Changelog-Kopfzeile 2026-08-28 blieb vor dem Tag unangetastet, weil das Datum der Tag-Tag sein muss und der Tag wegen der ausstehenden Freigabe fruehestens am 2026-08-28 entstehen konnte; er entstand um 04:50Z
- [Phase 15-release-0-1-10]: Plan 15-03: das veroeffentlichte Asset misst 46973 Bytes gegen die 47299 des lokalen Baus; Plan 15-04 signiert die heruntergeladenen Bytes unter https://github.com/street1983nk/nextcloud-mcp-connector/releases/download/v0.1.10/mcp_connector-0.1.10.tar.gz
- [Phase 16]: Der Changelog-Block trägt die Kopfzeile ## [0.1.11] - 2026-08-28. Lokal (10:35 Europe/Berlin) und in UTC (08:35Z) derselbe Kalendertag; Plan 16-03 prüft die Zeile vor dem Tag erneut, weil ein Release-Notes-Datum im signierten Asset unveränderlich ist
- [Phase 17]: die Kubernetes-Aussage von OD-01 wird in der korrigierten Fassung geführt: nicht 'AppAPI kann kein Kubernetes', sondern auf app_api 33 existiert kubernetes-install nicht (KubernetesActions.php HTTP 404) und auf app_api 34 existiert es (HTTP 200, DEPLOY_ID Zeile 37, über HaRP); damit ist OD-01 eine Terminfrage an ZenDiS und keine Absage
- [Phase 17]: Versionspin und Kubernetes-Hürde sind dieselbe Hürde und fallen mit demselben Schritt (openDesk auf Nextcloud 34 oder höher); die Zielumgebung 33.0.7 gilt als ungetestet, nicht als unzulässig, weil appinfo/info.xml Zeile 235 min-version 32 bis max-version 34 erlaubt, alle Nachweise dieses Projekts aber auf 34.0.x stehen
- [Phase 17]: die Betriebsart von integration_openproject in openDesk bleibt unbehauptet (der Bootstrap-Job ist Indiz, nicht Beleg) und geht als Frage 7 an den ISV-Call; die Formulierung 'manual-install ist ausdrücklich für Entwicklung' wird nicht geführt, weil sie auf der heutigen Nextcloud-Doku-Seite nicht mehr auffindbar ist
- [Phase ?]: 17-02: Stufenschnitt der Messumgebung als compose-Profile (op, oidc); ein blankes up startet nur Stufe A
- [Phase ?]: 17-02: gemessen, dass compose die ganze Datei vor der Profilauswahl interpoliert; HP_SHARED_KEY und SECRET_KEY_BASE muessen vor jedem Kommando exportiert sein, WR-11 bleibt
- [Phase ?]: 17-02: der Deploy-Daemon benennt den ExApp-Container global nc_app_<appid>; nur eine Topologie dieses Repositories kann die ExApp betreiben, die ExApp-Topologie ist fuer die Phase mit stop angehalten
- [Phase ?]: 17-02: S0 gemessen, die Ein-Klick-Kette haelt auf Nextcloud 33.0.7; der geerbte Nachweis auf 34.0.x ist ersetzt
- [Phase ?]: 17-02: Annahme A5 bestaetigt, app_api 33.0.0 in der laufenden 33.0.7; die Kubernetes-Aussage aus 1.2 steht unveraendert
- [Phase ?]: 17-03: OpenProject 17.7.2 läuft; erster Start gemessen mit 95 Sekunden und 1,964 GiB statt der erwarteten 30 bis 90 Minuten und mindestens 4 GB, das Speicherrisiko aus 17-02 ist nicht eingetreten und keine `.wslconfig` war nötig
- [Phase ?]: 17-03: Fassung dreifach belegt (Digest, `/app/lib/open_project/version.rb` im Container, `coreVersion` der API); die Fußleiste der Anmeldeseite trägt in 17.7.2 keine Fassung, deshalb ist die Quelldatei im Container die dritte Belegstelle
- [Phase ?]: 17-03: Namensfalle in beide Richtungen gemessen; `localtest.me` hat einen AAAA-Eintrag auf `::1` und der `extra_hosts`-Eintrag ist IPv4, PHP-curl im Nextcloud-Container nimmt `172.29.43.10` und antwortet 200 (erste Fehlerquelle für 17-05)
- [Phase ?]: 17-03: Grundzustand des Zwei-Konten-Negativbeweises steht (opa, opb, privates Projekt `spike-privat-b`, Arbeitspaket 38, Mitglied nur opb), ist aber als Aufbau und ausdrücklich nicht als Messung gekennzeichnet; der Beweis selbst läuft in 17-04 und 17-06 unter den Konten
- [Phase ?]: 17-03: OAuth-Anwendung als nicht vertraulicher Client mit leerem Feld `Client Credentials User ID`, damit `force_pkce` aus `doorkeeper.rb:90` greift und der Berechtigungsdurchgriff nicht unauffällig bricht (Pitfall 2, T-17-03)
- [Phase ?]: 17-03: das Seed-Passwort `admin` wurde von der Instanz abgelehnt (`failed_login_count` 6, `force_password_change` true, Konto nicht gesperrt); per `rails runner` gesetzt, **Ursache nicht untersucht**. Passwortregel dieser Fassung: alle vier Zeichenklassen
- [Phase ?]: 17-03: OpenProject 17.7.2 bringt einen eigenen MCP-Server unter `/mcp` mit (`routes.rb:48`); in dieser Phase ungemessen und als DI-17-01 in `deferred-items.md` zurückgestellt, mit Behandlungsvorschlag für 17-08 und 17-09
- [Phase ?]: 17-04: Weg 1 ist vollständig gemessen (D-04): PKCE Pflicht mit Gegenprobe (400 ohne code_challenge), expires_in 7200, Erneuerung ohne jeden Cookie
- [Phase ?]: 17-04: Der Consent-Fluss von Weg 1 ist per Formular automatisierbar, ohne Browser und ohne Owner-Schritt; der Browser-Rückfall des Plans wurde nicht gebraucht. Zwei Fallen: `POST /login` endet auf `/two_factor_authentication/request` und braucht `curl -L`, und `curl -4` ist Pflicht wegen des AAAA-Eintrags von `localtest.me`
- [Phase ?]: 17-04: Der Zwei-Konten-Negativbeweis auf Weg 1 ist geführt (D-05): opb 200, opa 404 mit `NotFound`, erfundene Id 999999999 Byte für Byte dieselbe Antwort; zusätzlich auf Projekt- und Listenebene gemessen (total 34 gegen 33), damit ein Listenleck ausgeschlossen ist
- [Phase ?]: 17-04: Der vorherige `refresh_token` stirbt erst mit dem ersten Gebrauch des neuen `access_token`, nicht mit der Erneuerung und nicht mit der Zeit; mit zwei Ketten gemessen, Belegstelle `previous_refresh_token` in `/app/db/structure.sql:4383`. Als DI-17-02 für OD-04 zurückgestellt, kein Code in dieser Phase (D-12)
- [Phase ?]: 17-04: OD-02 bleibt Pending, weil dieser Plan Weg 0 mit keinem Wert misst und OD-02 beide Wege nebeneinander verlangt; 17-09 hakt ab
- [Phase ?]: 17-05: Weg A des Einrichtungswegs ist gemessen nicht gangbar (SSRF-Schutz von OpenProject); gelaufen ist Weg B, Weg A bleibt ungemessen statt verworfen
- [Phase ?]: 17-05: allow_local_remote_servers=true als dokumentierter Eingriff in die Messumgebung; beide Produkte sperren Loopback in der Vorgabe
- [Phase ?]: 17-05: OD-02 bleibt Pending, von Weg 0 fehlen S3 bis S6; abgehakt wird es von 17-09
- [Phase 17]: S4 steht auf zwei Beinen: der gestellte Ablauf (`token_expires_at 0`, bob) und der natürlich verstrichene (19623 s, alice) liefern denselben Ausgang, damit ist der künstliche Ablauf als Messweg selbst gegengeprobt und die Erneuerung hängt nicht am Wert 0
- [Phase 17]: die Byte-Kosten einer Weg-0-Antwort sind keine Budgetgröße, sondern eine Zahl mit zwei Abhängigkeiten (Berechtigung des Nutzers, Modulsatz des Projekts): dieselbe Fläche liefert 4746 Bytes als bob und 2542 als alice, davon 87 Prozent HAL-Relationen
- [Phase 17]: Abschnitt 3 des Berichts trifft ausdrücklich keine Entscheidung über den Werkzeugschnitt; die Wahl gehört 17-09 und OD-04, und die Diät macht der Server über `select` (15831 gegen 88 Bytes) und nicht eine Projektion in unserem Code
- [Phase 17]: OD-02 bleibt Pending, weil von Weg 0 noch S5 fehlt; abgehakt wird es von 17-09. Fortsetzung der Entscheidung aus 17-01 bis 17-05
- [Phase ?]: 17-07: S5 gemessen, Weg 0 traegt im Modus oidc nur so lange wie der zwischengespeicherte Token
- [Phase ?]: 17-07: isLoggedIn() liefert unter AppAPI-Impersonation true; der Bruch liegt an der Sitzungsfrage und nicht davor, damit ist die Diagnose aus research/SUMMARY.md bestaetigt statt ersetzt (S5c)
- [Phase ?]: 17-07: Der Pfad nextcloud_hub ist angelaufen und ungemessen, nicht widerlegt (DI-17-05); der Entwurf zu user_oidc#925 liegt nach geglueckter Live-Repro unversendet in docs/contrib/, gesendet wird ausschliesslich vom Owner (D-08); OD-02 bleibt Pending bis 17-09
- [Phase ?]: 17-08: Die Reihenfolge der neun ISV-Fragen ist an bestehende Berichtsverweise gebunden (1.2, 1.3, 1.4, 2.2, 2.5 zeigen auf 1, 5, 6, 7, 9) und nicht nach Wichtigkeit sortiert
- [Phase ?]: 17-08: Vier zurueckgestellte Funde (DI-17-01, DI-17-03, DI-17-04, DI-17-05) sind als Nachfragen an die Fragen 6 und 7 gehaengt statt als eigene Fragen, damit die Liste bei neun bleibt
- [Phase ?]: 17-08: Drei von dieser Phase beantwortete Fragen sind aus der Liste entfernt und mit Beleg in einer Streichtabelle gefuehrt; Freigabe des Owners am 2026-08-29 ohne inhaltliche Aenderung, drei Entwuerfe bleiben unversendet
- [Phase ?]: 17-09: Die Folgerung in 2.4 traegt ihre Bedingung im selben Satz (Modus oauth2 gegen oidc); der Satz 'Weg 0 traegt unter OIDC nicht' ist bewusst nicht geschrieben, weil der Pfad nextcloud_hub ungemessen ist
- [Phase ?]: 17-09: Abschnitt 5 nicht umnummeriert; die Reihenfolge S0 bis S6, Weg 1, SSRF steht als neue Tabelle 5.0 davor, damit die Verweise auf 5.1 bis 5.6 gueltig bleiben
- [Phase ?]: [Phase 18]: auto_vacuum = INCREMENTAL muss die erste Anweisung auf einer frischen Audit-Verbindung sein, nicht nur vor executescript(SCHEMA); das Umschalten auf WAL schreibt den Dateikopf und friert den Modus auf 0 ein (eigene Messung beider Reihenfolgen)
- [Phase ?]: [Phase 18]: die Feldreihenfolge CANONICAL_FIELDS (17 Namen, seq zuerst, ohne prev_hash und hash) steht ab Plan 18-01 fest; INSERT und Digest bauen beide auf _row_values auf, damit ein Pruefkommando den Hash allein aus der Zeile nachrechnen kann
- [Phase 18]: 18-03: Der AST-Lauf prüft nur reason= an Fehlerkonstruktionen; audit/store.py baut Entry(reason=row[11]), und dieser Wert kommt zur Laufzeit aus einer Zeile und kann nie eine Konstante sein
- [Phase 18]: 18-03: Zwölf Statuszweige statt der erwarteten sieben bis zehn, weil dav, caldav und carddav je einen Schreib- und einen Lesepfad führen
- [Phase 18]: 18-03: Die sechs Kennungen in errors.REASONS sind eingefroren; eine siebte ist ein Entscheid und gehört in ein Review, gehalten von einem AST-Lauf über src/
- [Phase 18]: Die Obergrenze des Audit-Logs fährt gegen used_bytes = (page_count - freelist_count) * page_size; os.stat und page_count * page_size fallen nach einem DELETE nicht und würden bis zur leeren Tabelle löschen
- [Phase 18]: Die Löschanweisungen des Aufräumlaufs heissen _DROP_*, weil der Vertragstest zwei exakte SQL-Formen ausnimmt und nicht die Datei; eine Ausweitung hätte auch ein künftiges HTTP-DELETE in audit/store.py verdeckt
- [Phase 18]: 18-05: Der Client-Name reist im claims-Feld des Tokens mit, gefuellt aus dem Client, den verify_token fuer die Sperrpruefung ohnehin laedt; ein spaeter aufgeloester Name waere nach occ mcp_connector:purge weg
- [Phase 18]: 18-05: Der Erfassungspfad nimmt resolve_caller und nie resolve_credentials; Caller traegt vier Felder ohne Geheimnis und antwortet None statt zu werfen (D-13), und params-_meta bleibt ungelesen
- [Phase 18]: 18-06: Der Erfassungspunkt ist der finally-Zweig von graceful mit einem awaiteten record.note; note faengt Exception selbst, weil ein await im finally sonst die laufende Ausnahme ersetzt (D-13, T-18-17)
- [Phase 18]: 18-06: Die gesetzten Parameternamen kommen aus params-arguments-keys() geschnitten mit PARAM_ALLOWLIST; kwargs taugt nicht, weil das SDK Vorgabewerte materialisiert
- [Phase 18]: 18-06: __mcp_audited__ als ausdruecklicher Marker statt einer Pruefung auf fn.__code__.co_name; der Vertragstest misst ihn ueber alle 21 Werkzeuge
- [Phase 18]: 18-07: Die zwei Vorgabezahlen des Audit-Logs stehen doppelt in config.py statt importiert zu werden: der Import waere ein Ring ueber audit/__init__, und ein Test haelt beide Paare gleich
- [Phase 18]: 18-07: audit_log_enabled ist die positive Richtung mit Vorgabe aus (D-14) und ausdruecklich nicht das Vorbild von talk_send_enabled; der Recorder entsteht nur hinter dem Schalter
- [Phase 18]: 18-07: Der Startlauf schreibt die Schaltzeile aus D-15 nur bei einem Zustandswechsel und raeumt eine abgeschaltete Ablage genau dann einmal auf, wenn die Datei schon vor dem Start da war
- [Phase 18]: 18-08: Das Prüfkommando antwortet immer mit 200 und trägt das Urteil im Rumpf, weil AppAPI den Rumpf bei jedem anderen Status verwirft; --json ist der Weg für ein Überwachungsskript
- [Phase 18]: 18-08: Die Zählungen der Prüfausgabe kommen aus AuditStore.overview und nicht aus einem SweepReport, weil eine Prüfung nicht löschen darf, um zu erfahren, wie viel da ist
- [Phase ?]: 18-09: Eine leere Kontoliste ergibt None und nie ein leeres frozenset, weil eine Ablage mit einer Kette zu einer Instanz mit Nutzern gehoert
- [Phase ?]: 18-09: Die Loeschung eines Kontos wird im CI-Job exapp wirklich gemessen (occ user:delete); lokal bleibt A1 ungemessen, der fail-safe traegt unabhaengig davon
- [Phase ?]: 18-10: Erfolgskriterium 5 steht getrennt in getestet (purge, vier Faelle) und hergeleitet (Trennen, Pausieren, Entfernen ueber die Oberflaeche; Beleg ist ein grep ueber die drei Aufraeumpfade, T-18-25 accept)
- [Phase ?]: 18-10: Die Grenze aus D-18 steht woertlich im Abschlussbericht: occ app_api:app:unregister --rm-data entfernt das Volume und mit ihm das Log; docs/uninstall.md bleibt Phase 19 (AUDIT-06)
- [Phase ?]: [Phase 19]: die drei Namensreiniger sind eine Regel in audit/text.py (printable, isprintable statt C0+DEL, Steuerzeichen werden ersetzt statt getilgt); R-18-06 geschlossen, die vierte Fassung in exapp/ui/layout.py bleibt bewusst stehen
- [Phase ?]: [Phase 19]: eine angekündigte content-length wird wie in config.py gelesen (isascii vor isdigit) UND die Länge des Ziffernlaufs vor seinem Wert entschieden, weil int() seit Python 3.11 auch einen Lauf über 4300 Ziffern ablehnt; R-18-08 geschlossen
- [Phase 20-01]: PyJWT 2.14.0 vor der Herausloesung in Plan 20-02 gelockt: Der JWKS-Umbau soll auf der Zielversion stattfinden; drei Befunde der Freigabe vom 11.09.2026 treffen den geerbten Code in oauth/oidc.py
- [Phase 21-02]: audience_holds weist eine aud-Liste mit einem Nicht-String-Eintrag komplett ab (fail closed), statt den Eintrag zu ueberspringen: Ein Angreifer bestimmt Form und Inhalt der Liste; eine teilweise lesbare Liste ist keine belastbare Aussage
- [Phase 21-02]: azp-Vergleich ohne fruehen Abbruch ueber alle Allowlist-Eintraege, compare_digest auf UTF-8-Bytes je Eintrag: Aus der Dauer der Pruefung ist weder Treffer noch Trefferposition zu lernen
- [Phase 22-01]: Der Exchange-Pfad bekommt einen eigenen Namensraum NC_MCP_EXCHANGE_* mit ausdrücklichem Schalter und steht ab Werk aus: die Richtung von audit_log_enabled und ausdrücklich nicht die von talk_send_enabled, weil ein zweiter Prüfpfad, der wegen eines Tippfehlers anspringt, genau der Fehlschlag ist, gegen den CONF-01 geschrieben wurde
- [Phase 22-01]: Keine Discovery beim Start: die JWKS-URL wird aus dem Issuer und DEFAULT_JWKS_PATH zusammengesetzt und von der Gleich-Origin-Regel der Phase 21 geprüft; ein ausgehender Abruf beim Start würde eine Anbieterstörung zu einem Startfehler machen
- [Phase 22-01]: Eine gesetzte, aber leere Variable des Namensraums ist bei bewaffnetem Schalter eine Startabweisung und kein Default; bei ausgeschaltetem Schalter zählt sie weiterhin als nicht gesetzt
- [Phase 22-01]: Die Audience hat als Default die Resource-URL dieser Instanz und nie ein generisches nextcloud (T-22-03)
- [Phase 22]: die Weiche zwischen Store-Zweig und Exchange-Zweig fällt strukturell über die Tokenform (`looks_like_jws`: zwei Punkte, drei nicht-leere Segmente), vor jeder Prüfung und ohne Rückfallebene; beide Richtungen sind mit einer Attrappe belegt, die beim Aufruf sofort auffliegt (22-02)
- [Phase 22]: der geprüfte fremde Claim-Satz reist unter genau einem verschachtelten Schlüssel (`EXCHANGE_CLAIM`), damit ein fremder Claim `auth_id` nicht in den Store-Zweig von `resolve_identity` zeigen kann; `subject` bleibt leer, bis Phase 23 den kanonischen Principal baut (22-02)
- [Phase 22]: der Widerruf geht an die Kette und nicht an den Store-Verifier, damit ein herausrotierter Schlüssel ihn nicht überlebt; `KeySet.forget` leert nur den Cache und lässt Abkühlzeit und Wiederholsperre stehen (22-02)
- [Phase 22]: EXCHANGE_LIMIT = 30 als eigenes Limit zwischen FAILURE_LIMIT (10) und PATH_CEILING (200); die Decke der Klasse bleibt PATH_CEILING und wird bewusst nicht angehoben (22-03): eine Ablehnung des Exchange-Pfades kostet eine Signaturpruefung und bei unbekanntem kid einen ausgehenden Abruf, ist also teurer als ein abgelehnter Token-Grant; die Decke ist geteiltes Schicksal, und das ist auf einem Pfad, den ein Fremder ohne Schluessel erreicht, der richtige Handel, weil der bestehende Pfad gar nicht in dieser Klasse liegt
- [Phase 22]: Die Formbedingung der Drossel steht in chain.exchange_shaped_request und nicht in throttle.py: die Formregel darf es nur einmal geben, sonst driften Weiche und Drossel auseinander; throttle.py bekommt ein Callable hereingereicht und nennt den Exchange-Pfad nirgends, ein grep haelt das fest (22-03)
- [Phase 22]: Im Aus-Zustand haengt an der MCP-Route gar kein Drossel-Wrapper, nicht einer, der alles durchlaesst: ein solcher waere heute nicht unterscheidbar und morgen ein anderer Codepfad; im bewaffneten Fall sitzt er aussen um die Transportgrenze, weil die gezaehlte Ablehnung der 401 dieser Grenze ist (22-03)

### Pending Todos

- **AUTH-04 (Plan 03-09, Owner):** Claude.ai und ChatGPT gegen eine oeffentlich erreichbare Staging-Instanz. Alles, was ohne oeffentliche Domain messbar war, ist mit 03-08 gemessen; offen bleibt genau der Teil, der eine erreichbare Instanz und die beiden gehosteten Oberflaechen braucht.

- **Owner-Schritt 01-13:** PR an nextcloud/context_agent#227 einreichen. Branch und DCO-Commit liegen im Fork street1983nk/context_agent (fix/stateless-http-session-compat, def1425), der PR-Text in docs/contrib/227-pr-body.md. Kommando und Pruefpunkte stehen in .planning/phases/01-server-kern/01-13-SUMMARY.md. Vorher `git push origin main` im Connector-Repo, damit der verlinkte Regressionstest oeffentlich sichtbar ist. Danach PR-URL nachtragen, ROADMAP 01-13 abhaken, CONTRIB-01 auf Complete.
- **Owner-Schritt 01-14:** Ein Durchgang mit Claude Desktop selbst nach docs/client-setup.md. Die Anleitung ist gegen die Referenz-Clients der Testsuite verprobt (mcp 2.0 und mcp 1.29 gegen denselben laufenden Endpoint, plus scripts/acceptance_all_tools.py ueber alle 15 Tools per stdio); die Konfigurationspfade fuer Claude Desktop stammen aus der offiziellen Dokumentation und sind auf diesem Rechner nicht verifiziert.
- **Nextcloud-AIO-Smoke (D-31): in 05-08 bewusst DESCOPED, nicht offen und nicht erledigt.** Die fehlende Voraussetzung ist eine Host-Eigenschaft (oeffentlich aufloesbare Domain, gueltiges oeffentliches TLS, eingehend 80 und 443), die der AIO-Mastercontainer prueft, bevor er einen Container startet; dazu kommt der Docker-Socket neben der taeglich genutzten Owner-Instanz. Der Punkt geht als descopte Zeile in die Phasen-Verifikation, mit den sechs offenen Schritten in docs/exapp-install.md. Kein Teil des Projekts behauptet AIO-Abdeckung. Historischer Wortlaut der Uebergabe aus Phase 2: Er scheitert auf diesem Rechner an AIOs Domain-Validierung (oeffentliche Domain plus gueltiges TLS). Die fehlenden Schritte stehen in docs/exapp-install.md, Abschnitt Nextcloud AIO: Host mit oeffentlicher Domain und Zertifikat, AIO-Mastercontainer starten, optionalen HaRP-Container aktivieren (Annahme A6 unverifiziert), App als ExApp installieren, den Permission-Fidelity-Smoke wiederholen und occ app_api:app:list festhalten.
- **WR-12 Linux-socat-Loop (Phase 5):** Die Linux-Variante des --manual-Entwicklungsloops (socat auf das Compose-Gateway) ist dokumentiert, aber auf diesem Windows-Host nicht durchgespielt; Entwicklungs-Komfort, nicht der ausgelieferte Pfad.
- **Browser-Blick auf /settings/user/security (Assumption A1, Phase-4-Verifikation):** Gemessen ist, dass Nextcloud die Link-only-Form ausliefert (forms-Endpoint, Initial-State der Seite, Mount-Punkt `<div id="mcp_connector_mcp_connector_settings">`). Der gerenderte Pixel ist nicht gemessen, im Live-Lauf war kein Browser beteiligt. Schadensfall waere ein fehlender Wegweiser, keine Funktionsstoerung. Details in 04-04-MEASUREMENTS.md, Beweis 1.
- **ExApp-Topologie: Stand nach 06-07 (dies ist der gueltige Stand; die zwei Absaetze darunter sind Geschichte).** Die Topologie LAEUFT: Compose-Projekt `nc-mcp-exapp`, `compose.exapp.yml` jetzt auf `nextcloud:34.0.3-apache` gepinnt, `occ status` meldet 34.0.3.2, `app_api` 34.0.0, `appstore` 1.0.0. Der ExApp-Container `nc_app_mcp_connector` fährt `127.0.0.1:5000/mcp_connector:0.1.2` (Digest `sha256:3ba4a2ce1921`), also den Arbeitsbaum-Stand nach 06-06, `RestartCount` 0, `NC_MCP_PUBLIC_URL` gesetzt. Nutzer `jane` und ihre ZWEI nicht widerrufenen OAuth-Verbindungen leben, dazu alice, bob und die 05-03-Fixture (Suffix `04d2eb7d6d`). `.env.exapp` ist von diesem Lauf neu geschrieben (frische App-Passwoerter fuer alice und bob, `APP_SECRET` und Suffix wiederverwendet). Wieder anfahren nach einem `down`: `HP_SHARED_KEY` aus dem HaRP-Container ZURUECKLESEN, solange die Container laufen, sonst neu erzeugen; `up -d --wait`; und wenn der Container den Repository-Stand tragen soll, `occ app_api:app:unregister mcp_connector` **ohne** `--rm-data` und danach `bash scripts/bootstrap_exapp.sh`, weil `ensure_exapp` die Registrierung fuer eine bekannte App ueberspringt und sonst das alte Image weiterlaeuft (gemessen in 06-07). Volume-Sicherung des Laufs: `C:/Users/Student/nc-mcp-exapp-backup-20260820/` (zwei tar-Dateien plus die zwei `oc_appconfig_ex`-Zeilen dieser App).
- **ExApp-Topologie: Stand nach 05-08.** Die Topologie ist heruntergefahren (`down` mit erhaltenen Volumes), das Netz ist weg, und die App ist **vollstaendig entfernt**: 05-08 hat den Beweislauf mit `occ mcp_connector:purge --force` und `occ app_api:app:unregister mcp_connector --rm-data` beendet, also gibt es kein `nc_app_mcp_connector_data`, keine Registrierung, keinen ExApp-Container und keine Config-Zeile mehr. `.env.exapp` beschreibt damit eine Installation, die nicht mehr existiert; APP_SECRET und der Fixture-Suffix darin werden beim naechsten Bootstrap wiederverwendet. Die Volumes `nc-mcp-exapp_nextcloud-exapp-data` und `nc-mcp-exapp_registry-exapp-data` tragen die Instanz mit alice, bob, der 05-03-Fixture (Suffix `04d2eb7d6d`, in 05-08 neu erzeugt, weil Task 1 eine Instanz ohne Vorgeschichte verlangte) und deaktiviertem Bruteforce-Waechter. Wieder anfahren: `HP_SHARED_KEY` erzeugen (die Container sind weg, es gibt nichts zurueckzulesen), `up -d --wait`, dann `bash scripts/bootstrap_exapp.sh` ohne vorheriges Abmelden, weil nichts registriert ist. Die zwei Images `127.0.0.1:5000/mcp_connector:0.1.0` und `ghcr.io/street1983nk/mcp_connector:0.1.0` (je 330 MB) liegen absichtlich noch da; AppAPI loescht ein gezogenes Image nie.
- **ExApp-Topologie (Stand vor 05-08, historisch):** Nach 05-07 wieder heruntergefahren (`down` mit erhaltenen Volumes, danach `docker stop`/`docker rm nc_app_mcp_connector` und `docker network rm nc-mcp-exapp-net`); der Wegwerf-Container `nc-mcp-owui-probe` ist entfernt, das Image `ghcr.io/open-webui/open-webui:main` (7,16 GB) liegt absichtlich noch da. Zuvor nach 05-05 ebenso heruntergefahren (`down` mit erhaltenen Volumes, danach `docker stop`/`docker rm nc_app_mcp_connector` und `docker network rm nc-mcp-exapp-net`). Die Volumes tragen die Fixture von 05-03 (read-only geteilter Ordner plus ungeteilte Datei); die zugehoerigen vier Werte stehen in `.env.exapp` und werden beim naechsten Bootstrap wiederverwendet, nicht neu erzeugt. `auth.bruteforce.protection.enabled` steht auf `false` und alle Bruteforce-Zaehler auf 0, also im Zustand, den der Bootstrap herstellt (05-05). Wieder anfahren: `export HP_SHARED_KEY=$(openssl rand -hex 32)` und in DERSELBEN Zeile weiterarbeiten (die Shell-Env ueberlebt einen Aufruf nicht, und jedes `docker compose` gegen diese Datei braucht die Variable), `up -d --wait`, `occ app_api:app:unregister mcp_connector --silent --force`, `occ app_api:daemon:unregister harp_proxy_docker`, dann `bash scripts/bootstrap_exapp.sh` (baut das Image neu und setzt NC_MCP_PUBLIC_URL). Ohne das Neubauen laeuft ein veraltetes Image. **Ab dem zweiten Aufruf gegen bereits laufende Container den Schluessel zurueckLESEN statt neu erzeugen** (gemessen in 05-05): `export HP_SHARED_KEY=$(docker inspect nc-mcp-exapp-harp --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^HP_SHARED_KEY=' | cut -d= -f2)`. Fehlt die Variable, scheitert JEDER compose-Aufruf an der Interpolation, und im Bootstrap sieht das wegen `2>/dev/null` in der Warteschleife wie "Nextcloud is still not installed" aus, obwohl `occ status` `installed: true` meldet.
- **Aufraeumen (optional):** Die Docker-Testinstanz traegt jetzt zusaetzlich die Calendar-App 6.5.3 und die Abnahme-Artefakte. Fuer einen sauberen Stand: `docker compose -f compose.test.yml down -v` und danach `bash scripts/bootstrap_test_nc.sh`.

### Blockers/Concerns

- v1.5 Termin: der ISV-Call am 14.09. ist der harte Anker für Phase 17; die Fragenliste (OD-03) muss auch dann vorliegen, wenn OD-01 oder OD-02 ergebnislos bleiben, denn ein ungemessener Punkt ist selbst eine Frage für den Call
- v1.5 offene Architekturfrage: Weg 0 hängt an einer einzigen ungemessenen Tatsache (trägt die serverseitige Token-Erneuerung von `integration_openproject` auch in openDesks OIDC-gebundenem Betrieb, oder fällt sie nach Ablauf des zwischengespeicherten Tokens auf 401); fällt sie, ist Weg 1 der Rückfall, nicht ein Ausweichen
- v1.5 Textkollision: EXAPP-11 (Phase 16) und AUDIT-06 (Phase 19) fassen dieselben Dateien an; wird Phase 19 vor dem Tag v0.1.11 fertig, darf ihr Text NICHT in das 0.1.11-Asset geraten
- v1.5 Wortanspruch: sobald das Audit-Log existiert, wird der Satz "heute in keiner Form vorhanden" im Enterprise-Absatz falsch; die Grenzbeschreibung "was es nicht leistet" ist Pflichtbestandteil (D-v1.5-02), und die vier verbotenen Wörter gehören unter ein Gate
- v1.5 Volumen-Risiko: Audit-Log und OAuth-Speicher liegen auf demselben Volume; ohne Obergrenze und Aufbewahrungsfrist macht ein volles Volume SQLite im WAL-Modus schreibunfähig und jede Token-Rotation scheitert (AUDIT-03)
- Harte Deadline: Nextcloud Conference September 2026 (Demo und Talk-Entwurf liegen bereit; v1.2 darf den Termin nicht gefaehrden, Scope kuerzen statt schieben)
- Offene Unbekannte v1.2: Mail-Erreichbarkeit unter reiner AppAPI-Impersonation ist nur aus Quellcode gelesen, nie in dieser Topologie gemessen; ein negatives Ergebnis aendert den Schnitt von Phase 10 und 11 (MAIL-01..03, CTX-02, SEC-01, Tool-Zahl in TOOL-15). Deshalb blockierender erster Plan in Phase 8
- Talk-"Lesen" schreibt per Default in den Nutzerzustand (Lesemarker, Benachrichtigungs-Quittung, Online-Status) und es gibt keinen Reparaturweg, weil DELETE per Gate verboten ist; die vier Parameter gehoeren in den Client, nicht ins Tool, mit positiv behauptendem Test
- Mails Listen-Routen tragen SCOPE_IGNORE und sind nicht zugesagt; das Rueckgrat bleibt die OCS-Volltext-Route, die interne Route bleibt ersetzbar
- Budget-Gate: eine einmalige Anhebung ohne gemessene Neu-Verankerung macht es wieder zur Dekoration (Erfahrung aus Phase 1)
- Tables-Zellwert-Formate je column_types sind unvollstaendig dokumentiert, wahrscheinlichste Quelle fuer einen 400 in Phase 8

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Quick Tasks Completed

| Date | Task | Commits | Directory |
|------|------|---------|-----------|
| 2026-09-23 | BL-15 Rest: ehrliche Tool-Beschreibung von unified_search, Contract-Pin umgedreht, Backlog geschlossen | 9a32764, 6ee0a03, 5c4c043 | .planning/quick/260923-bl15-honest-search-note/ |
| 2026-09-23 | BL-17: Public-URL aus NEXTCLOUD_URL abgeleitet (AIO-No-Config), Präzedenzkette Formwert > Variable > Ableitung > Default gepinnt, Rescue fällt auf Ableitung, Doku umgestellt | dac73f5, cfb74aa, 62ed52b, 5063a9f, 6b215f8 | .planning/quick/260923-bl17-public-url-derivation/ |
| 2026-09-23 | BL-01 Rest: RAG-Akronym aus den drei Store-Descriptions (neues Gate, Rot-Beweis), Retrieval-Schicht-Satz im n8n-Guide, README-Banner verifiziert, BL-01 STATUS DONE | ff5685b, fdac6f5, fe4929e | .planning/quick/260923-bl01-findling-banner/ |

## Session Continuity

Last session: 2026-09-19T09:56:28.357Z
Stopped at: Completed 22-03-PLAN.md
Nächster Schritt: /gsd:verify-work 22, danach /gsd:plan-phase 23 (Konto-Mapping, MAP-01/MAP-02). Die eine benannte Stelle für Phase 23 ist der EXCHANGE_CLAIM-Zweig von ChainedVerifier.resolve_identity; die Drossel muss dafür nicht angefasst werden.
Resume file: None

## Operator Next Steps

- Roadmap v1.6 gegenlesen und freigeben (5 Phasen 20-24, 15 Requirements, Coverage 15/15)
- Danach: /gsd:plan-phase 20 (JWKS-Schicht und PyJWT-Stand, EXCH-01 und DEP-01)
- Recherche je Phase: 20 bis 22 sind laut research/SUMMARY.md überspringbar, 23 (Credential-Wege) und 24 (Nachweis, Header-Größe über HaRP) brauchen tiefere Recherche in der Planung
- Owner-Gate bleibt: ein Tag auf `v*` entsteht nur nach ausdrücklicher, wörtlicher Freigabe; die Auslieferung als Store-Release ist EXAPP-12 und ausdrücklich nicht Teil von v1.6
- Extern getaktet und kein Blocker: die vier F13-Entscheidungen (Audience-Konvention, Konto-Claim, Beispiel-Token und Realm-Export, Exchange-Ziel-Eintrag); alles daran Hängende bleibt Konfiguration mit dokumentiertem Default

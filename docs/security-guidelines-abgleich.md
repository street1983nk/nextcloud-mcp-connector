# Abgleich mit den Nextcloud-Sicherheitsrichtlinien (MCP Connector)

Anhang zum Sicherheitsdossier. Stand: 16.11.2026, geprüft gegen die
Security guidelines des Nextcloud 35 Developer Manual
(developer_manual/prologue/security.html) und die App-Store-Regeln
(app_publishing_maintenance/publishing.html). Prüfweg: Code-Sweep über
src/ am 16.11.2026 (eval, exec, os.system, Shell-Aufrufe mit Eingaben:
0 Treffer) plus die CI-Gates (ruff-Vollsatz, pyright, vulture, pytest,
Security scans). Der Connector ist eine Python-ExApp ohne eigene
PHP-Oberfläche; Browser-Regeln (XSS, CSRF, Clickjacking) betreffen ihn
nur mittelbar.

## Developer-Guidelines

| Regel | Stand | Beleg |
|---|---|---|
| SQL-Injection | n. a. | Keine eigene Datenbank; Zugriffe laufen über die Nextcloud-APIs (OCS/WebDAV) |
| XSS | n. a. | Keine eigenen Templates/Webseiten; Ausgaben gehen als Daten an den MCP-Client |
| Clickjacking | n. a. | Keine eigene Weboberfläche |
| Code execution / file inclusion | erfüllt | Sweep 0 Treffer; keine dynamische Code-Ausführung |
| Directory traversal | erfüllt | Datei-Operationen nur über die Nextcloud-WebDAV/OCS-APIs mit serverseitiger Rechteprüfung; keine eigenen Pfadbauten aufs Dateisystem |
| Shell injection | erfüllt | Keine Shell-Aufrufe (Sweep) |
| Auth bypass / privilege escalation | erfüllt | Authentifizierung über AppAPI; jede Aktion läuft als der angemeldete Nutzer über die NC-APIs, der Server prüft die Rechte; Werkzeuge einzeln abschaltbar (NC_MCP_DISABLED_TOOLS), sensible Werkzeuge nur per Opt-in (z. B. profile_fields read-only hinter NC_MCP_PROFILE_FIELDS_READ=on, PR #49) |
| Sensitive data exposure | erfüllt | Keine Inhalte an Dritte; keine Telemetrie; Logs ohne Inhaltsdaten |
| CSRF | erfüllt | MCP-Verkehr Server-zu-Server mit AppAPI-Signatur bzw. OAuth-Token; der OAuth-Flow nutzt PKCE S256 (bindet den Code an den Client) |
| Unvalidated redirects | erfüllt | Relevant im OAuth-/authorize-Flow: redirect_uri wird gegen die registrierten URIs des Clients UND die Allowlist-Regel geprüft (oauth/consent.py validate_redirect_uri + redirect_uri_allowed), sonst Abbruch ohne Redirect |
| CORS | n. a. | Keine CORS-Freigaben |

## Store-Regeln (Auszug)

| Regel | Stand | Beleg |
|---|---|---|
| AGPL-3.0-or-later | erfüllt | LICENSE, info.xml |
| Kein "Nextcloud" im Namen | erfüllt | mcp_connector |
| Zeitnahe Reaktion auf Sicherheitsmeldungen | erfüllt | SECURITY.md (GitHub private reporting + Mail, 7 Tage) |
| Sauberes Auf-/Abräumen, Up-/Downgrade | erfüllt | ExApp-Lebenszyklus über AppAPI; Canary-Job gegen neue NC-Versionen (canary-nc35) |
| Keine Daten an Dritte, Datenschutz | erfüllt | Der Connector spricht nur mit der eigenen Nextcloud-Instanz; MCP-Clients erhalten nur, was der Nutzer über seine Rechte ohnehin sieht |
| Klare Kommunikation des Zwecks, keine unerwarteten Änderungen | erfüllt | Werkzeugliste dokumentiert DE/EN/FR; destruktive Aktionen bewusst weggelassen (Owner-Entscheid 12.11.: kein Löschen); schreibende Werkzeuge einzeln benannt |
| Kontaktweg | erfüllt | GitHub Issues, SECURITY.md, Forum-Thread |

## Über die Richtlinien hinaus

- Fremd-PRs mit Workflow-Freigabe je Lauf, Review vor Merge (PR-#49-Prozess)
- Vulture/ruff/pyright/pytest als Pflicht-Gates; Security scans in CI
- Volltest DE/EN/FR vor jedem Store-Release (Owner-Regel)

## Offene Punkte

- Nach Merge von PR #49 (Profile Fields read-only) den Opt-in-Abschnitt um die Live-Validierung ergänzen.

[English](README.md) | **Deutsch** | [Français](README.fr.md)

> Die englische README (README.md) ist die maßgebliche Fassung; diese Übersetzung wird nachgezogen.

# MCP Connector für Nextcloud

Ein kuratierter MCP Server, der Ihr Nextcloud (Dateien, Kalender, Notizen, Deck, Kontakte,
Tables, Talk und Mail) mit KI-Assistenten wie Claude, Cursor, ChatGPT oder Ihren eigenen
Agenten verbindet. Als Nextcloud-ExApp installiert, ist er zugleich sein eigener
OAuth-2.1-Autorisierungsserver.

**Findling + Nextcloud MCP Connector = die Retrieval-Schicht für Ihr eigenes RAG.**
[Findling](https://apps.nextcloud.com/apps/findling) macht den Inhalt Ihrer Dokumente
durchsuchbar, Scans eingeschlossen. Der Connector reicht diese Treffer an jeden MCP-Client
weiter, mit genau den Rechten des fragenden Nutzers; gemessen in
[tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py).
Das Modell bringen Sie mit, und kein Inhalt verlässt Ihren Server.

## Was er kann

- 21 Tools über neun App-Familien: Dateien, Kalender, Notizen, Deck, Kontakte, Tables, Talk,
  Mail und die cloud-weite Suche
- OAuth 2.1 nach der MCP-Autorisierungsspezifikation: dynamische Client-Registrierung,
  PKCE S256, zielgebundene Token, Refresh-Rotation mit Wiederverwendungserkennung und
  sofortigem Entzug. Claude.ai und ChatGPT bekommen eine URL und sehen nie ein Passwort
- Jede Anfrage läuft mit den Rechten des angemeldeten Nutzers, die Nextcloud-Berechtigungen
  gelten unverändert, und der Assistent sieht nie mehr als Sie
- Verwaltung je Nutzer: Jedes Konto pausiert oder aktiviert seinen eigenen Zugang und trennt
  einen einzelnen Assistenten, auf der Verbindungsseite unter Einstellungen, Sicherheit,
  MCP Connector
- `prepare_context` bündelt eine Suche, die kommende Woche an Terminen, die wartenden
  Talk-Gespräche und die Zahl ungelesener Mails in einem Aufruf, jede Quelle mit eigenem
  Zeitbudget
- Ein bewusst kleiner Tool-Satz, damit dieser Server neben Ihre anderen MCP Server passt,
  selbst in Clients mit harter Tool-Obergrenze
- Kein Cron, keine Indexierung, keine Telemetrie, keine Kopie Ihrer Daten, und keine
  Zugangsdaten werden je protokolliert

## Was dieser Server nicht kann

- Nichts löschen: kein Tool setzt ein DELETE auf Dateien, Termine, Notizen, Karten oder
  Kontakte ab
- Nichts überschreiben: Schreiben legt nur neu an, und `files_upload` lehnt einen vorhandenen
  Pfad mit klarem Fehler ab, statt ihn zu ersetzen
- Kein Verschieben, kein Umbenennen, keine Änderung von Freigaben oder Berechtigungen
- Mail ist strikt lesend: kein Senden, kein Entwurf, kein Verschieben, kein Markieren, kein
  Löschen, kein Anhang-Download
- Kein Admin-Zugriff: Der Server handelt als ein Nutzer und erbt genau dessen Rechte
- Keine Volltextsuche in Dateiinhalten, solange keine Such-App wie Findling installiert ist

Das ist eine Design-Einschränkung und kein Versprechen guten Verhaltens: Ein Contract-Test
liest die Module und wird beim ersten zerstörenden Aufruf rot,
[tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py).

## Tools

**read** heißt, das Tool liest nur, **create-only** heißt, es kann neue Objekte anlegen, aber
bestehende nie ändern oder entfernen. Die Tabelle wird nicht von Hand gepflegt: Ein
Contract-Test liest die laufende Registry und wird rot, sobald ein Name oder eine Stufe
abweicht.

| Tool | Permission | Was es tut |
|------|------------|------------|
| `files_search` | read | Dateien und Ordner nach Namen über WebDAV search; Inhalte sind nicht indexiert |
| `files_list` | read | Die direkten Kinder eines Ordners, mit Größe und Änderungszeit |
| `files_read` | read | Der Inhalt einer Datei |
| `files_upload` | create-only | Eine neue Datei; ein vorhandener Pfad wird abgelehnt, nie überschrieben |
| `calendar_list_events` | read | Termine in einem expliziten Zeitraum, mit expliziter Zeitzone |
| `calendar_create_event` | create-only | Ein neuer Termin; bestehende Termine werden nie geändert |
| `notes_search` | read | Notizen nach Titel und Inhalt, über den Notes-Suchprovider von Nextcloud |
| `notes_read` | read | Eine Notiz |
| `notes_create` | create-only | Eine neue Notiz; bestehende Notizen werden nie geändert |
| `deck_browse` | read | Deck-Boards, Stapel und Karten |
| `deck_create_card` | create-only | Eine neue Karte in einem Stapel; bestehende Karten werden nie geändert |
| `tables_browse` | read | Tables: die Tabellen, die Spalten einer Tabelle oder ihre Zeilen |
| `tables_create_row` | create-only | Eine Zeile über Spaltentitel; bestehende Zeilen werden nie geändert |
| `talk_browse` | read | Talk-Gespräche und der Verlauf eines davon; Lesen hinterlässt keine Spur |
| `talk_send` | create-only | Eine Nachricht in ein Gespräch; nie bearbeitet oder gelöscht, instanzweit abschaltbar |
| `mail_browse` | read | Mail-Konten, ihre Postfächer und Nachrichtenköpfe; strikt lesend |
| `contacts_search` | read | Kontakte in den Adressbüchern |
| `unified_search` | read | Die Unified Search von Nextcloud über alle Provider, rechtegeprüft |
| `prepare_context` | read | Dateien, Notizen, Karten, die nächste Terminwoche, wartende Talk-Gespräche und ungelesene Mails in einem Aufruf |
| `search` | read | OpenAI-kompatibler Sucheinstieg, delegiert an die Unified Search |
| `fetch` | read | OpenAI-kompatibler Abruf, löst eine ID zu Datei, Notiz, Karte, Termin, Mail, Talk-Nachricht oder Tabelle auf |

`search` und `fetch` gibt es, weil das ChatGPT-Connector-Profil genau diese zwei Namen und
Schemata verlangt. Sie sind dünne Hüllen um die Tools darüber, keine zweite Implementierung.

Eine Antwort von `unified_search`, mit beiden ehrlichen Fällen darin: ein Treffer, dessen ID
die lesenden Tools auflösen, und ein Provider, dessen Einträge eine URL bleiben statt einer
erfundenen ID. Ein Provider, der ausfällt oder hängt, wird unter `degraded` genannt, damit
eine Teilantwort sichtbar eine Teilantwort ist. Notes, Deck, Tables, Talk und Mail sind
optionale Apps; die Tool-Liste bleibt überall dieselbe, und eine fehlende App wird in einem
Satz beantwortet, nie mit einem leeren Ergebnis.

```json
{"query":"budget","count":2,"results":[{"id":"file:4711","title":"Budget 2026.md","url":"https://cloud.example.org/index.php/f/4711","provider":"files","kind":"file"},{"id":"url:https://cloud.example.org/index.php/call/abc123","title":"Khaled","url":"https://cloud.example.org/index.php/call/abc123","provider":"talk-conversations","kind":"url","resolvable":false}]}
```

## Sicherheit

Dieser Server hält **private Daten**, er nimmt **nicht vertrauenswürdige Inhalte** auf (eine
Mail oder eine Talk-Nachricht schreibt jemand anderes, und für eine Mail braucht dieser
Jemand nicht einmal ein Konto auf Ihrer Instanz), und er hat einen **Ausgangskanal**,
`talk_send`. Diese drei zusammen sind das, was Simon Willison die
[Lethal Trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) nennt, und ein
Sprachmodell trennt Daten nicht zuverlässig von Anweisungen. Deshalb sitzt `talk_send` hinter
dem Administrationsschalter `NC_MCP_TALK_SEND`, der den Ausgangskanal für die ganze Instanz
schließt, während das Lesen unberührt bleibt, und Mail bringt Reichweite mit, bewusst ohne
eigenen Ausgang. Beides macht Prompt Injection nicht unmöglich. Die lange Fassung, mit jeder
Gegenmaßnahme und dem ehrlichen Rest, steht in [docs/privacy.md](docs/privacy.md). Die
Schalter liegen unter Einstellungen, Administration, Sicherheit:

![Admin-Einstellungen des MCP Connectors](docs/screenshots/admin-settings.png)

## Installation

Im Nextcloud App Store gelistet als
[MCP Connector](https://apps.nextcloud.com/apps/mcp_connector) und als ExApp installiert:
AppAPI aktivieren, einen Deploy-Daemon registrieren, dann die App ausrollen und aktivieren.
Nextcloud 32 bis 34. Auf 34.0.3 erledigt das die Apps-Verwaltung für Sie, auf älteren
Versionen ist occ der verlässliche Weg. Der Durchlauf mit den genauen Befehlen und den
Fallstricken, die wirklich vorkommen: [docs/exapp-install.md](docs/exapp-install.md).

[![MCP Connector im Nextcloud App Store](docs/screenshots/app-store.png)](https://apps.nextcloud.com/apps/mcp_connector)

## Clients

Claude.ai und ChatGPT verbinden sich über OAuth mit einer URL. Claude Desktop, Claude Code,
Cursor und andere lokale Clients starten denselben Server über stdio, mit einem
Nextcloud-App-Passwort:

```bash
uv tool install nextcloud-mcp-connector

export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

Derselbe Server spricht Streamable HTTP für entfernte Clients, unter `POST /mcp`, wobei
`NC_MCP_ALLOWED_HOSTS` in der Praxis Pflicht ist. Einrichtung Schritt für Schritt, jede
Umgebungsvariable und die drei Fehler, die wirklich vorkommen:
[docs/client-setup.md](docs/client-setup.md). OAuth für die Administration:
[docs/oauth-setup.md](docs/oauth-setup.md). Automatisierungsplattformen sind auch Clients,
mit einer OAuth-Verbindung je Person: [docs/n8n-setup.md](docs/n8n-setup.md).

![Verbindungsseite mit zwei verbundenen Assistenten](docs/screenshots/connections-page.png)

## Datenschutz

Jeder Aufruf geht an Ihr Nextcloud und kommt zurück: Nichts läuft im Hintergrund, kein
Ergebnis wird zwischengespeichert, kein Index gehalten. In den HTTP-Modi reisen die
Zugangsdaten pro Anfrage und werden nie gespeichert. Fragen, die Nutzer stellen:
[docs/faq.md](docs/faq.md).

## Enterprise

Das Audit-Log gehört zu dieser App und nicht zu einem Add-on. Eingeschaltet hält es jeden
Werkzeugaufruf fest: das Konto, für das er lief, das Werkzeug, die Zeit, die aufrufende App
und das Ergebnis, nie einen Parameterwert und nie einen Teil eines Ergebnisses. Es ist ab
Werk aus, die Administration schaltet es in den Admin-Einstellungen dieser App ein, und
gelesen wird es mit `occ mcp_connector:audit:read`. Jeder Eintrag ist mit dem vorigen
hash-verkettet, und `occ mcp_connector:audit:verify` prüft die Ketten und nennt die erste
Stelle, an der eine gebrochen ist.

Geplant, aber noch nicht verfügbar, sind Gruppen-Policies und die Anmeldung über den
Identitätsanbieter, den Ihre Organisation ohnehin betreibt.

Angebot anfordern: admin@infranode.dev

## Entwicklung

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest` startet nichts und braucht nichts. `uv run pytest -m matrix` startet den
HTTP-Server als Subprozess, `uv run pytest -m integration` braucht das lokale Test-Nextcloud
aus `compose.test.yml`.

App-ID, Paketnamen und Repository-Name sind eingefroren, siehe
[docs/app-id-freeze.md](docs/app-id-freeze.md).

## Lizenz

AGPL-3.0-or-later, siehe [LICENSE](LICENSE). Spenden: [PayPal](https://www.paypal.com/paypalme/KhaledCherifDev)
und [Stripe](https://buy.stripe.com/3cI14n2ke6AbdTPfG22VG00).

[English](README.md) | **Deutsch** | [Français](README.fr.md)

> Die englische README (README.md) ist die maßgebliche Fassung; diese Übersetzung wird nachgezogen.

# MCP Connector für Nextcloud

Ein kuratierter MCP Server, der Ihr Nextcloud (Dateien, Kalender, Notizen, Deck, Kontakte, Tables, Talk
und Mail) mit KI-Assistenten wie Claude, Cursor, ChatGPT oder Ihren eigenen Agenten verbindet.

**Findling + Nextcloud MCP Connector = die Retrieval-Schicht für Ihr eigenes RAG.**
[Findling](https://apps.nextcloud.com/apps/findling) macht den Inhalt Ihrer Dokumente
durchsuchbar, Scans eingeschlossen, und 1.0.0 bringt die semantische Suche mit. Der
Connector reicht diese Treffer an jeden MCP-Client weiter, mit genau den Rechten des
fragenden Nutzers. Das Modell bringen Sie mit, und kein Inhalt verlässt Ihren Server.
Gemessen statt versprochen:
[tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py)
belegt, dass ein Inhaltstreffer nie ein fremdes Konto erreicht.


**Dieser Server kann niemals etwas löschen, überschreiben oder neu teilen.**

Dieser Satz ist die Design-Einschränkung, kein Versprechen guten Verhaltens. Der Server implementiert
keinen einzigen destruktiven Aufruf: kein DELETE, kein MOVE, kein Überschreiben, keine Änderung von
Freigaben. Schreibende Tools legen nur neu an, und eine Namenskollision wird mit einer klaren Ablehnung
beantwortet statt mit einem stillen Überschreiben.

Zwei weitere Eigenschaften folgen aus derselben Idee:

- **Der Assistent sieht nie mehr als Sie.** Jede Anfrage läuft mit Ihren eigenen Nextcloud-Zugangsdaten,
  sodass die Nextcloud-Berechtigungen unverändert gelten.
- **Ein bewusst kleiner Tool-Satz.** Die 21 Tools sind so kuratiert, dass dieser Server neben Ihre
  anderen MCP Server passt, selbst in Clients mit einer harten Tool-Obergrenze.

Lizenz: AGPL-3.0-or-later. App-ID, Paketnamen und Repository-Name sind eingefroren, siehe
[docs/app-id-freeze.md](docs/app-id-freeze.md).

## Status

Version 0.1.12. Die App ist im Nextcloud App Store gelistet und als Nextcloud-ExApp über AppAPI
installierbar. Was heute vorliegt und wo jede dieser Aussagen festgehalten ist:

- Alle 21 Tools des v1-Satzes sind implementiert, und die Tool-Tabelle weiter unten wird nicht
  mehr von Hand gepflegt: ein Contract-Test liest die aktive Tool-Registry und schlägt fehl,
  wenn ein Name oder eine Berechtigungsstufe in der Tabelle davon abweicht.
- Die OAuth-2.1-Anmeldung ist Ende zu Ende gegen die zwei gehosteten Konnektoren belegt, für
  die sie gebaut wurde, Claude.ai und ChatGPT, samt dynamischer Client-Registrierung und
  Refresh-Rotation. Der Ablauf und die Messungen stehen in
  [docs/oauth-setup.md](docs/oauth-setup.md).
- Verwaltung pro Konto: jedes Konto pausiert oder setzt seinen eigenen MCP-Zugriff fort und
  trennt jede einzelne verbundene Assistenz auf der Verbindungsseite dieser App, die Nextcloud
  unter Einstellungen, Sicherheit, MCP Connector verlinkt.
- `prepare_context` bündelt eine Suche, die kommende Woche an Terminen, die wartenden
  Talk-Konversationen und die Ungelesen-Zähler der Mail-Konten in einem Aufruf, eine Frage kostet
  damit einen Rundlauf statt mehrerer. Jede Quelle hat ihr eigenes Zeitbudget und ihren eigenen
  `degraded`-Eintrag, eine langsame Quelle kürzt also das Bündel und nie die Antwort. Drei
  Kappungen halten die Größe vorhersagbar: höchstens drei Konversationen, eine Chat-Vorschau
  geschnitten bei 200 Bytes, und höchstens drei Mail-Konten. Mail kommt als Zähler, und genau das
  ist der Punkt: im Standardbündel steht kein Betreff und kein Mailinhalt.

Seit 0.1.4: Tables und Talk. Eine Assistenz durchsucht die Tabellen des Kontos und legt in
einer davon eine Zeile an, über die Spaltentitel, sie liest die Unterhaltungen des Kontos und
den Verlauf einer davon, und sie schreibt eine Nachricht in eine Unterhaltung. Das Lesen einer
Unterhaltung hinterlässt keine Spur: keine Lesemarke wird verschoben, keine Benachrichtigung
bestätigt, und der Online-Status bleibt, wie er war. Talk ist die einzige Familie, in der eine
Assistenz anderen Menschen etwas vorlegen kann, deshalb kann eine Administratorin das Senden
für die ganze Instanz abschalten, und eine Nachricht, die alle, eine ganze Gruppe oder ein
ganzes Team auf einmal erwähnt, wird nie gesendet.

Schritt-für-Schritt-Einrichtung für Claude Desktop, Claude Code und Remote-HTTP-Clients, inklusive der
drei Fehler, die tatsächlich auftreten: **[docs/client-setup.md](docs/client-setup.md)**.

### OAuth 2.1

Als Nextcloud-ExApp installiert, ist dieser Server zugleich sein eigener OAuth-2.1-Autorisierungsserver,
gemäß der MCP-Autorisierungsspezifikation: dynamische Client-Registrierung, PKCE S256, an die
Zielgruppe gebundene Tokens, Refresh-Rotation mit Wiederverwendungserkennung und sofortigem Widerruf.
Ein Client wie Claude.ai oder ChatGPT erhält eine URL, meldet den Nutzer auf den eigenen Seiten von
Nextcloud an und sieht niemals ein Passwort oder ein App password. Die Verbindung erscheint unter
Einstellungen, Sicherheit, Geräte und Sitzungen und kann dort beendet werden.

Seit 0.1.3: Eine Assistenz-App kann sich auch
über die Adresse eines Metadaten-Dokuments ausweisen, das sie selbst veröffentlicht, statt sich
hier zuerst zu registrieren. Das ist der Weg, den die aktuelle MCP-Spezifikation bevorzugt, und
der Weg, über den Claude Code sich verbindet. Beide Wege laufen nebeneinander, und eine
Administratorin kann jeden von beiden abschalten.

Was eine Administratorin einstellen muss, was ein Nutzer eingibt und die Messungen hinter beidem:
**[docs/oauth-setup.md](docs/oauth-setup.md)**.

## Im Nextcloud App Store

Die App ist als **MCP Connector** gelistet:
**[apps.nextcloud.com/apps/mcp_connector](https://apps.nextcloud.com/apps/mcp_connector)**

[![MCP Connector im Nextcloud App Store](docs/screenshots/app-store.png)](https://apps.nextcloud.com/apps/mcp_connector)

Die Installation läuft als Nextcloud ExApp: AppAPI aktivieren, einen Deploy-Daemon
registrieren, dann die App deployen und aktivieren. Unter **Nextcloud 34.0.3** nimmt die
Apps-Verwaltung einem das ab: die App-Liste zeigt die ExApp samt ihrem Deploy-Daemon, der
Installationsknopf einer ExApp heißt "Deploy and enable", und "Remove" steht im Aktionsmenü
einer abgeschalteten ExApp (gemessen auf 34.0.3.2 am 2026-08-20). Unter 34.0.2 und älter
listet die Verwaltung gar keine ExApp, und occ ist auf jeder Version der verlässliche Weg. Der
vollständige Weg mit den exakten occ-Kommandos und den Stolperstellen, die wirklich auftreten,
steht in **[docs/exapp-install.md](docs/exapp-install.md)** (auf Englisch).

Nach der Installation registriert die App ihre Einstellungen unter Einstellungen,
Verwaltung, Sicherheit:

![Admin-Einstellungen des MCP Connectors](docs/screenshots/admin-settings.png)

Jedes Konto verwaltet seine eigenen Verbindungen auf der Verbindungsseite der App, die
Nextcloud unter Einstellungen, Sicherheit, MCP Connector verlinkt:

![Verbindungsseite mit zwei verbundenen Assistenten](docs/screenshots/connections-page.png)

## FAQ

**Mein Administrator hat diese App installiert. Kann ich sie für mich abschalten?**

Ja, und Sie brauchen Ihren Administrator dafür nicht. Im Hintergrund läuft nichts: der
Connector handelt ausschließlich auf Anfrage einer Assistenz, die Sie selbst verbunden haben, es
gibt keinen Cron, keine Indizierung und keine Telemetrie. Ihr eigenes Konto hat einen Schalter
auf der Verbindungsseite dieser App, die Nextcloud unter Einstellungen, Sicherheit, MCP
Connector verlinkt, und jede verbundene Assistenz lässt sich einzeln trennen, wobei der
Connector ihr Nextcloud-App-Passwort an Nextcloud zurückgibt.

Die vollständige Antwort samt der Grenze zwischen dem, was diese App steuert, und dem, was der
Anbieter Ihrer Assistenz entscheidet: **[docs/faq.md](docs/faq.md)** (englisch).

## Schnellstart (stdio)

Sie benötigen ein Nextcloud-App password, nicht Ihr Anmeldepasswort. Erstellen Sie eines in Nextcloud
unter Einstellungen, Sicherheit, Geräte und Sitzungen.

```bash
uv tool install nextcloud-mcp-connector   # or: uv run nc-mcp inside a checkout

export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

Client-Konfiguration, zum Beispiel für Claude Desktop oder Cursor:

```json
{
  "mcpServers": {
    "nextcloud": {
      "command": "nc-mcp",
      "env": {
        "NC_MCP_URL": "https://cloud.example.com",
        "NC_MCP_USER": "alice",
        "NC_MCP_APP_PASSWORD": "xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
      }
    }
  }
}
```

## HTTP-Modus

Derselbe Server spricht auch Streamable HTTP für Remote-Clients:

```bash
export NC_MCP_URL=https://cloud.example.com
export NC_MCP_ALLOWED_HOSTS=mcp.example.com
uv run uvicorn mcp_connector.entry_http:app --host 127.0.0.1 --port 8765
```

Der MCP-Endpunkt ist `POST /mcp`, und `GET /health` antwortet ohne Authentifizierung mit
`{"status":"ok","version":"..."}`. Ein Endpunkt bedient beide Protokoll-Generationen: Clients auf der
aktuellen Spezifikation und Clients auf Basis des MCP SDK 1.x werden anhand der Protokollversion ihrer
Anfrage weitergeleitet, und ein Neustart kann keine Konversation unterbrechen, weil der Server keinen
Sitzungszustand hält.

Zugangsdaten werden in diesem Modus nicht aus der Umgebung gelesen. Sie reisen pro Anfrage im
`Authorization`-Header (Basic, Nutzer und App password) und werden unverändert an Nextcloud
weitergereicht, das sie authentifiziert. Der Server behandelt den Header nie als eigene
Identitätsbehauptung und speichert nichts, sodass eine Bereitstellung mehrere Nutzer ohne einen
Zugangsdaten-Speicher bedienen kann.

Für Einzelnutzer-Bereitstellungen ist stattdessen ein statisches Bearer token verfügbar: setzen Sie
`NC_MCP_STATIC_BEARER`, und das Nextcloud-Konto wird wie im stdio-Modus aus der Umgebung genommen. Die
beiden HTTP-Modi schließen sich gegenseitig aus.

`NC_MCP_ALLOWED_HOSTS` ist in der Praxis nicht optional. Ohne den Wert akzeptiert die Transportschicht
nur `Host: localhost` und `Host: 127.0.0.1` und beantwortet jede andere Anfrage mit `421 Misdirected
Request`, bevor irgendein MCP-Code läuft. Beachten Sie, dass es sich um den `Host`-Header eingehender
Anfragen handelt, nicht um die Bind-Adresse: `--host 0.0.0.0` lässt niemanden herein.

## Umgebungsvariablen

| Variable | Modus | Erforderlich | Zweck |
|----------|------|----------|---------|
| `NC_MCP_URL` | alle | ja | Basis-URL Ihres Nextcloud, inklusive eines Unterpfads, falls Sie einen verwenden |
| `NC_MCP_USER` | stdio, statisches Bearer | ja | Nextcloud-Nutzer-ID |
| `NC_MCP_APP_PASSWORD` | stdio, statisches Bearer | ja | App password aus Einstellungen, Sicherheit, Geräte und Sitzungen |
| `NC_MCP_ALLOWED_HOSTS` | HTTP | in der Praxis ja | Komma-getrennte Allowlist der zulässigen `Host`-Header dieses Servers; ein Port-Wildcard wird je Name ergänzt |
| `NC_MCP_STATIC_BEARER` | HTTP | nein | Statisches Bearer token für Einzelnutzer-Bereitstellungen; ohne es authentifizieren sich Clients pro Anfrage |
| `NC_MCP_DISABLE_DNS_REBINDING_PROTECTION` | HTTP | nein | Nur hinter einem Proxy auf `true` setzen, der den `Host`-Header kontrolliert |
| `NC_MCP_PUBLIC_URL` | statisches Bearer, ExApp | ja für OAuth | Öffentliche URL dieses Servers. Im ExApp-Modus ist sie der Issuer des Autorisierungsservers und die Resource des Protected-Resource-Dokuments, sodass OAuth ohne sie nicht funktioniert |
| `NC_MCP_OAUTH_DCR` | ExApp | nein | Dynamische Client-Registrierung, an, sofern nicht abgeschaltet |
| `NC_MCP_OAUTH_CIMD` | ExApp | nein | Ein Client kann sich über die Adresse eines Metadaten-Dokuments ausweisen, das er selbst veröffentlicht, an, sofern nicht abgeschaltet; wird die Selbstregistrierung abgeschaltet, ist dieser Weg mit geschlossen |
| `NC_MCP_OAUTH_ALLOWLIST_ONLY` | ExApp | nein | Nur gelistete Clients dürfen autorisieren; eine leere Liste verschließt dann die Tür für alle |
| `NC_MCP_OAUTH_ALLOWED_CLIENTS` | ExApp | nein | Komma-getrennte Client-IDs oder Redirect-URIs, nur gelesen, wenn die Allowlist aktiv ist |
| `NC_MCP_TALK_SEND` | alle | nein | Der ausgehende Talk-Kanal dieser App, an, sofern er nicht auf off gesetzt ist. Mit off kann kein Assistent über diesen Connector eine Talk-Nachricht senden, ganz gleich, was ein Konto in Talk selbst darf; das Lesen von Konversationen und ihrer Historie ist nicht betroffen. Im ExApp-Modus schreibt das Administrationsformular den Wert |

Keine Zugangsdaten werden jemals protokolliert, in keinem Modus.

## Tools

Berechtigungsstufen: **read** bedeutet, das Tool liest nur, **create-only** bedeutet, das Tool kann
neue Objekte anlegen, aber niemals bestehende ändern oder entfernen.

| Tool | Berechtigung | Was es tut |
|------|------------|--------------|
| `files_search` | read | Sucht Dateien und Ordner nach Namen per WebDAV-Suche; Inhalte werden nicht indexiert |
| `files_list` | read | Listet die direkten Kinder eines Ordners, mit Größen und Änderungszeiten |
| `files_read` | read | Liest den Inhalt einer einzelnen Datei |
| `files_upload` | create-only | Lädt eine neue Datei hoch; ein bestehender Pfad wird abgelehnt, nie überschrieben |
| `calendar_list_events` | read | Listet Termine in einem expliziten Zeitraum, mit expliziter Zeitzone |
| `calendar_create_event` | create-only | Legt einen neuen Termin an; bestehende Termine werden nie geändert |
| `notes_search` | read | Findet Notizen nach Titel und Inhalt über den Nextcloud-Notes-Suchprovider |
| `notes_read` | read | Liest eine einzelne Notiz |
| `notes_create` | create-only | Legt eine neue Notiz an; bestehende Notizen werden nie geändert |
| `deck_browse` | read | Durchsucht Deck-Boards, -Stapel und -Karten |
| `deck_create_card` | create-only | Legt eine neue Karte in einem Stapel an; bestehende Karten werden nie geändert |
| `tables_browse` | read | Durchsucht Tables: die Tabellen, die Spalten einer Tabelle oder ihre Zeilen |
| `tables_create_row` | create-only | Legt eine Zeile über Spaltentitel an; bestehende Zeilen werden nie geändert |
| `talk_browse` | read | Durchsucht Talk: die Konversationen dieses Kontos oder den Verlauf einer davon |
| `talk_send` | create-only | Sendet eine Nachricht in eine Konversation; eine Nachricht wird nie bearbeitet oder gelöscht, und eine Administratorin kann das Senden instanzweit abschalten |
| `mail_browse` | read | Durchsucht Mail: die Konten dieses Nutzers, die Postfächer eines Kontos oder die Nachrichtenköpfe eines Postfachs; strikt lesend, es gibt keinen Weg zu senden, einen Entwurf anzulegen, zu verschieben, zu markieren oder zu löschen |
| `contacts_search` | read | Durchsucht Adressbuch-Kontakte |
| `unified_search` | read | Fragt die Nextcloud-Unified-Search über alle Provider ab, berechtigungsbewusst |
| `prepare_context` | read | Bündelt passende Dateien, Notizen und Karten mit den Terminen der kommenden Woche, den wartenden Talk-Konversationen und den Ungelesen-Zählern der Mail-Konten zu einer Frage |
| `search` | read | OpenAI-kompatibler Sucheinstiegspunkt, delegiert an die Unified-Search |
| `fetch` | read | OpenAI-kompatibler Abrufeinstiegspunkt, löst eine ID zu einer Datei, Notiz, Karte, einem Termin, einer Mail, einer Talk-Nachricht oder einer Tabelle auf |

`search` und `fetch` existieren, weil das ChatGPT-Connector-Profil genau diese beiden Namen und Schemata
verlangt. Sie sind dünne Hüllen über den obigen Tools, keine zweite Implementierung.

### Dateien: was die Suche tatsächlich trifft

`files_search` nutzt die WebDAV-Suche, die **Namen** trifft, nicht Dateiinhalte. Ein Wort, das nur
innerhalb eines Dokuments vorkommt, erzeugt keinen Treffer, und das ist das Verhalten des Protokolls,
kein Mangel dieses Servers. Jede Suchantwort trägt daher denselben Hinweis:

```json
{"query":"budget","folder":"/","count":1,"items":[{"path":"/Docs/budget-2026.md","name":"budget-2026.md","kind":"file","size":2048,"content_type":"text/markdown","modified":"Thu, 14 Aug 2026 10:00:00 GMT","id":"file:4711"}],"note":"matched on names only; contents are not indexed"}
```

Eine Volltextsuche bräuchte eine separat installierte Nextcloud-App, deshalb ist die ehrliche Antwort
der obige Hinweis statt eines stillen leeren Ergebnisses.

`files_list` gibt die direkten Kinder eines Ordners zurück, Ordner zuerst und dann Namen. Der Ordner
selbst ist nie Teil seiner eigenen Auflistung, und ein Pfad, der auf eine Datei zeigt, erhält eine
Erklärung statt einer leeren Liste.

### Lange Listen: Cursor-Handles statt Sitzungen

Eine Liste, die vorzeitig abbrechen musste, sagt das und gibt ein Handle aus:

```json
{"items": ["..."], "truncated": true, "next": "eyJmIjoiLyIsIm8iOjI1LCJxIjoiYnVkZ2V0In0"}
```

Geben Sie diesen Wert als Parameter `cursor` zurück, um fortzufahren. Das Handle ist base64url von
kompaktem JSON und hält die gesamte Position, sodass der Server keine Sitzung führt: ein Handle
funktioniert noch nach einem Server-Neustart und gegen einen anderen Prozess desselben Servers. Es ist
bewusst nicht signiert, weil es kein Geheimnis und keine Berechtigung trägt. Die Zugangsdaten kommen bei
jedem einzelnen Aufruf aus dem Auth-Kanal, sodass ein verändertes Handle nur anders durch die eigenen
Daten des Aufrufers blättern kann. Ein Handle aus einer anderen Abfrage wird abgelehnt, statt still die
falsche Seite zurückzugeben.

### Kalenderzeiten

CalDAV ist die eine Stelle, an der ein kleiner Zeitfehler eine selbstsicher falsche Antwort erzeugt,
deshalb sind die Kalender-Tools darin explizit:

- `start` und `end` sind erforderlich und müssen eine Zone tragen, zum Beispiel `2026-09-01T00:00:00+02:00`
  oder `2026-09-01T00:00:00Z`. Ein Wert ohne Zone wird abgelehnt statt geraten.
- Wiederkehrende Termine werden von Nextcloud selbst expandiert, sodass jede Instanz als absolute Zeit
  zurückkommt. Der optionale Parameter `timezone` (ein IANA-Name wie `Europe/Berlin`) ändert nur, wie
  die Antwort geschrieben wird, nie welche Termine sie enthält.
- Ganztägige Termine sind Datumsangaben ohne Uhrzeit und werden mit `all_day` markiert. Ihr Enddatum ist
  exklusiv, wie RFC 5545 es definiert: ein Termin am 24. Oktober endet am 25. Oktober.
- `calendar_create_event` liest den angelegten Termin einmal zurück und meldet die Zeiten, die der
  Server gespeichert hat, nicht die, um die er gebeten wurde.

### Kontakte

`contacts_search` ist reine Lesefunktion und bleibt es in dieser Version: es gibt überhaupt keinen
CardDAV-Schreibpfad.

- Der Suchbegriff wird von Nextcloud selbst gegen den vollständigen Namen und die Mail-Adressen einer
  Karte abgeglichen, groß-/kleinschreibungs- und akzentunabhängig. Eine Telefonnummer wird zurückgegeben,
  aber nicht durchsucht.
- Jedes Adressbuch des Kontos wird gleichzeitig abgefragt. Eines, das ausfällt, wird unter `degraded`
  benannt, sodass eine Teilantwort sichtbar teilweise ist.
- Die beiden Sammlungen, die Nextcloud für jedes Konto erzeugt, werden ausgelassen: das
  Konten-Verzeichnis der Instanz (`z-server-generated--system`, angezeigt als "Accounts") und die
  Liste "kürzlich kontaktiert". Keine davon ist ein Adressbuch, das der Nutzer pflegt, und eine
  Namenssuche sollte nicht als Nebeneffekt das Verzeichnis einer ganzen Organisation herausgeben.
- Ein Konto ohne eigenes Adressbuch bekommt einen Fehler, der `occ dav:create-addressbook <user> contacts`
  benennt, nie ein leeres Ergebnis: "kein Adressbuch" und "kein passender Kontakt" sind
  unterschiedliche Antworten.

### Deck

Deck ist ein Browse-Tool mit einer Ebene, nicht ein Tool pro Ebene:

```json
{"level":"cards","count":2,"results":[{"id":"card:2:11:101","title":"Deck-Client bauen","stack":"To Do","url":"https://cloud.example.org/index.php/apps/deck/card/101"}]}
```

- `deck_browse(level="boards")` listet die Boards mit `can_edit`, `level="stacks"` braucht eine
  `board_id` und meldet, wie viele Karten ein Stapel enthält, `level="cards"` gibt die Karten selbst
  zurück. Eine ungültige Ebene wird vom Schema zurückgewiesen, und eine fehlende `board_id` benennt den
  Parameter, statt einen zu raten.
- `level="cards"` kostet genau **eine** HTTP-Anfrage pro Board, weil Nextcloud die Karten bereits in der
  Stapel-Antwort mitschickt. Ein Test zählt die Anfragen, gegen den Mock und gegen eine echte Instanz.
- Eine Karten-ID ist die kanonische Langform `card:<board>:<stack>:<card>`, die die Karte über die
  öffentliche Deck-API ohne Nachschlagen adressiert.
- `deck_create_card` legt nur an. Es gibt kein Update, kein Delete und keine Board- oder
  Stapel-Erstellung irgendwo im Deck-Codepfad. Ein Titel länger als 255 Zeichen oder ein Fälligkeitsdatum,
  das nicht ISO-8601 ist, wird vor der Anfrage abgelehnt, und ein Konto, dessen Nextcloud
  Board-Erstellung verbietet, wird gegen die eigenen Berechtigungen des Boards geprüft, sodass ein
  schreibgeschütztes Board erklärt wird statt mit einem 403 beantwortet.

### Mail

Mail ist ein Browse-Tool mit drei Ebenen und einer strikten Eigenschaft: es liest, und ein Zweites
kann es nicht.

- `mail_browse(level="accounts")` listet die Mail-Konten des angemeldeten Nutzers mit ihrer Adresse,
  `level="mailboxes"` braucht eine `account_id` und listet die Postfächer dieses Kontos mit ihrer
  Ungelesen-Zahl und ihrer IMAP-Rolle, und `level="messages"` braucht eine `mailbox_id` und gibt die
  Nachrichtenköpfe zurück, neueste zuerst. Keine der beiden IDs wird geraten: es gibt kein
  Standardkonto und kein "erstes Postfach", weil eine richtig aussehende Antwort über fremde Post der
  teuerste Fehler dieser Familie wäre. Ein Fenster umfasst 20 Nachrichtenköpfe, wenn kein größeres
  verlangt wird, höchstens 50, und eine Liste, die abbrechen musste, gibt ein `next`-Handle zurück wie
  jede andere lange Liste dieses Servers.
- **Den Volltext einer einzelnen Nachricht** liefert das bestehende `fetch` über die ID
  `mail:<databaseId>`, die jeder Nachrichtenkopf trägt, und kein zweites Tool. Der Body läuft immer
  durch die Wandlung nach Text, ob die Nachricht in HTML geschrieben wurde oder nicht, und er wird bei
  32 KiB gekappt, mit einer Markierung, die keine Fortsetzung verspricht: eine Mail hat keinen Offset,
  an dem man weiterlesen könnte. Neben dem Text, und bewusst nie darin, trägt `metadata`, was Nextcloud
  selbst über den Absender weiß: `sender_trusted`, `dkim`, `signature`, `encrypted`,
  `phishing_warning` und `phishing_checks`. `dkim` gleich `unchecked` heißt "es wurde nicht geprüft"
  und nicht "die Signatur ist ungültig", und dasselbe Wort deckt eine Mail ohne jede Signatur ab:
  keine von beiden ist ein geprüfter Absender, und beide führen zum selben nächsten Schritt.
- **Die Filtergrammatik**, genau so, wie sie getestet ist. Bedingungen werden `type:value`
  geschrieben und durch Leerzeichen getrennt:

  | Typ | Nimmt | Beispiel |
  |------|-------|---------|
  | `is:` | `unread`, `read`, `starred`, `answered`, `important` | `is:unread` |
  | `not:` | dieselben fünf Werte | `not:answered` |
  | `from:` | eine Adresse oder einen Teil davon | `from:rechnung@example.org` |
  | `subject:` | ein Wort des Betreffs | `subject:Rechnung` |
  | `tags:` | die **numerische** Tag-ID, nie das IMAP-Label | `tags:1` |
  | `start:` | **Unix-Sekunden** | `start:1756000000` |
  | `end:` | **Unix-Sekunden** | `end:1756600000` |

  Zwei Eigenschaften des Parsers der Mail-App gehören zur Grammatik, weil ein Aufrufer sie nicht
  erraten kann. Der Filter wird an **Leerzeichen** zerlegt, ein Wert mit einem Leerzeichen muss also
  prozentkodiert sein: `subject:Rechnung%20Mai` ist die einzige Schreibweise, die auf beide Wörter
  filtert, und `subject:Rechnung Mai` filtert auf `Rechnung` und lässt `Mai` fallen, ohne das zu
  sagen. Und jedes Token wird am **ersten** Doppelpunkt zerlegt, der Rest fällt weg, ein Doppelpunkt
  im Wert muss also `%3A` heißen. `start:` und `end:` werden gegen eine Ganzzahlspalte verglichen,
  nehmen also Unix-Sekunden und nichts sonst: `start:2026-08-01` filtert jede Nachricht weg, statt
  fehlzuschlagen, und `start:2026-08-01T10:00:00Z` würde obendrein am ersten Doppelpunkt abgeschnitten,
  weshalb ein ISO-Zeitstempel hier abgelehnt wird.

  Ein Typ, den dieser Connector nicht kennt, wird **abgelehnt** und nicht verworfen. Die Mail-App
  verwirft ihn still und antwortet mit der ungefilterten Liste, sodass `is:ungelesen` wie ein
  korrektes Filterergebnis aussähe und ein Modell den Unterschied nicht sehen kann. Ein Fehler kostet
  eine Runde, eine richtig aussehende falsche Antwort kostet das Gespräch.
- **Was bewusst fehlt.** Es gibt keinen `body:`-Filter: er ist die eine Bedingung, die die Datenbank
  verlässt und über IMAP sucht, also kostet er pro Aufruf eine Runde zum Mailserver des Nutzers.
  Anhänge werden nie heruntergeladen. Und es gibt überhaupt keinen Schreibweg, siehe den
  übernächsten Abschnitt.

### Cloud-weite Suche

`unified_search` fragt jeden Suchprovider ab, den die Instanz anbietet, gleichzeitig:

```json
{"query":"budget","count":2,"results":[{"id":"file:4711","title":"Budget 2026.md","subline":"in Dokumente","url":"https://cloud.example.org/index.php/f/4711","provider":"files","kind":"file"},{"id":"url:https://cloud.example.org/index.php/call/abc123","title":"Khaled","url":"https://cloud.example.org/index.php/call/abc123","provider":"talk-conversations","kind":"url","resolvable":false}],"note":"matched on names and metadata; file contents are not indexed","degraded":[{"provider":"search-deck-card-board","reason":"The provider did not answer within 15 seconds."}]}
```

- Die Provider-Liste kommt bei jedem Aufruf von Nextcloud und ist nie fest verdrahtet, weil sie den
  installierten Apps folgt. Eine vor einer Minute aktivierte App ist ohne Neustart durchsuchbar.
- Jeder Provider bekommt sein eigenes Timeout. Einer, der ausfällt oder hängt, wird unter `degraded` mit
  einem Grund benannt, sodass eine Teilantwort immer sichtbar teilweise ist, nie eine still verkürzte
  Liste.
- Berechtigungen sind Sache von Nextcloud: jeder Provider läuft als der authentifizierte Nutzer, und
  dieser Server hält keinen Index und cacht kein Ergebnis.
- Treffer aus Files, Notes und Deck tragen eine ID, die die Lese-Tools verstehen. Alles andere bekommt
  eine `url:`-ID und `resolvable: false`, weil eine erfundene ID zum falschen Objekt auflösen würde. Der
  Provider von Deck meldet nur eine Karten-ID, sodass seine kurze Form `card:<cardId>` ebenso markiert
  wird.
- `providers` verengt den Fan-out auf eine komma-getrennte Teilmenge, zum Beispiel `files,notes`. Ein
  Name, den die Instanz nicht kennt, wird unter `degraded` gemeldet, statt still ignoriert zu werden.
- `limit` gilt pro Provider und wird von Nextcloud selbst erneut gedeckelt. Wenn ein Provider paginiert,
  kommt sein Cursor unter `cursors` zurück.

### ChatGPT-Connector-Profil

`search` und `fetch` sind die beiden Namen, nach denen der OpenAI-Connector sucht. Ihre Parameter sind
`query` und `id`, ihre Feldnamen sind festgelegt, und beide sind die einzigen Tools dieses Servers, die
ein Output-Schema mitliefern, weil ChatGPT die Nutzlast als strukturierten Inhalt liest:

```json
{"results":[{"id":"file:4711","title":"Budget 2026.md","url":"https://cloud.example.org/index.php/f/4711","text":"in Dokumente"}]}
```

```json
{"id":"file:4711","title":"Budget 2026.md","text":"# Budget 2026 ...","url":"https://cloud.example.org/index.php/f/4711","metadata":{"kind":"file","path":"/Dokumente/Budget 2026.md","content_type":"text/markdown"}}
```

- `search` fügt keine zweite Suche hinzu. Es ruft `unified_search` auf und benennt die Felder um, sodass
  beide Tools dieselbe Frage auf dieselbe Weise beantworten.
- Jeder Treffer trägt eine nicht-leere, absolute URL auf der konfigurierten Instanz. ChatGPT erzeugt nur
  dann Zitations-Metadaten, solange `url` ein nicht-leerer String ist, sodass eine leere die Quelle still
  fallenlassen würde.
- `fetch` löst die sieben ID-Arten auf, die die Lese-Tools verstehen: `file:<fileid>` (nachgeschlagen
  über eine einzige WebDAV-Suche auf `oc:fileid`), `note:<id>`, `card:<board>:<stack>:<card>` inklusive
  der kurzen Form `card:<cardId>` aus dem Deck-Suchprovider, `event:<calendar>:<object>`,
  `mail:<databaseId>` (der Volltext einer einzelnen Nachricht, geschnitten bei 32 KiB, mit markiertem
  Schnitt), `message:<token>:<messageId>` (eine einzelne Talk-Nachricht, gelesen über dieselbe
  nebenwirkungsfreie Kontextroute; die Nachricht muss in dieser Konversation lesbar sein, sonst gibt es
  eine Ablehnung und nie eine Nachbarnachricht) und `table:<tableId>` (Titel, Zeilenzahl und die ersten
  Zeilen einer Tabelle; eine View ist keine Tabelle und bleibt eine URL).
- Ein Mail-Suchtreffer bleibt eine `url:`-ID, obwohl es die Volltextroute gibt, und das ist eine Messung
  und kein Versäumnis: ein Sucheintrag der Mail-App trägt einen Deep-Link mit einer RFC-Message-Id, und
  deren Auflösung auf die `databaseId`, die diese Route braucht, ist ungemessen. Eine ID, die meistens
  stimmt, ist in den übrigen Fällen eine Antwort über fremde Post.
- Eine `url:`-ID wird ehrlich beantwortet: dieser Server fordert nie eine URL an, die aus einem
  Sucheintrag stammt, und sagt das, statt Inhalt zu erfinden. Ein unbekanntes Präfix wird mit der Liste
  der gültigen abgelehnt, weil eine Chat-Nachricht als Notiz aufzulösen schlimmer ist als ein Fehler.
- Eine lange Datei wird an derselben Grenze abgeschnitten wie bei `files_read`. Der Schnitt wird
  innerhalb von `text` und erneut in `metadata` markiert, mit dem Offset zum Fortsetzen.

### Optionale Apps

Notes, Deck, Tables, Talk und Mail sind optionale Nextcloud-Apps, insgesamt zehn Tools. Die Tool-Liste
ist überall gleich: sie hängt nie davon ab, welche Apps eine Instanz hat, sodass sie cachebar und für
jeden Client vorhersagbar bleibt. Fehlt eine App, sagt das Tool das in einem Satz und nennt eine
Alternative, zum Beispiel "The Notes app is not installed on this Nextcloud.", "The Tables app is not
enabled on this Nextcloud.", "The Talk app is not available on this Nextcloud." oder "The Mail app is
not available on this Nextcloud." Kalender und Kontakte brauchen überhaupt keine App: CalDAV und
CardDAV sind Teil des Nextcloud-Kerns.

Mail wird anders erkannt als die anderen vier, und der Grund liegt nicht bei uns: die Mail-App
veröffentlicht keinen Capabilities-Eintrag, im Capabilities-Dokument ist also nichts zu finden.
Dieser Server fragt deshalb die Navigation des angemeldeten Nutzers ab, die die Apps auflistet, die
dieses Konto tatsächlich öffnen darf. Das kostet eine zusätzliche Anfrage pro Cache-Fenster, und nur
bei einem Mail-Aufruf.

## Was dieser Server nicht kann

- **Kein Löschen.** Kein Tool setzt ein DELETE gegen Dateien, Termine, Notizen, Karten oder Kontakte ab.
- **Kein Überschreiben.** Schreibvorgänge legen nur neu an. `files_upload` lehnt einen bestehenden
  Zielpfad mit einem klaren Fehler ab, statt ihn zu ersetzen, und die create-Tools rühren nie ein
  bestehendes Objekt an.
- **Kein Verschieben oder Umbenennen.** MOVE und COPY sind nicht implementiert.
- **Keine Freigabe-Änderungen.** Der Server erstellt, ändert oder entfernt keine Freigaben und ändert nie
  Berechtigungen.
- **Kein Admin-Zugriff.** Der Server handelt als ein Nutzer mit einem App password und erbt genau die
  Berechtigungen dieses Nutzers.
- **Keine Volltextsuche in Dateiinhalten**, sofern nicht die Nextcloud-Full-text-search-App installiert
  und konfiguriert ist. Ohne sie trifft die Dateisuche Namen und Metadaten.
- **Keine Hintergrundjobs, keine Synchronisation, keine lokale Kopie Ihrer Daten.** Jeder Aufruf geht an
  Ihr Nextcloud und kehrt zurück.
- **Kein Senden von Mail.** Kein Tool sendet eine Mail, legt einen Entwurf an, verschiebt eine
  Nachricht, setzt oder entfernt eine Markierung oder löscht etwas, und die Anhangsroute der Mail-App
  wird nie aufgerufen. Was diesen Satz hält, ist ein Contract-Test: er liest die beiden Mail-Module
  dieses Servers und behauptet, dass in ihnen kein einziger schreibender Aufruf steht, gegen eine
  Liste der Routen, die die Mail-App für genau diese Aktionen anbietet.

### Die Kette, die dieser Server hat, und der Schalter, der sie bricht

Mail zu lesen vervollständigt eine Kombination, die man benennen sollte, statt sie zu umschreiben.
Dieser Server hat Zugang zu **privaten Daten** (Dateien, Kalender, Notizen, Kontakte, Tables und jetzt
Mail), er nimmt **fremde Inhalte** auf (eine Mail und eine Talk-Nachricht sind von Dritten geschrieben,
und für eine Mail braucht dieser Dritte nicht einmal ein Konto auf Ihrer Instanz), und er hat einen
**Ausgangskanal**: `talk_send`, das eine Tool, das eine Nachricht direkt vor andere Menschen bringt,
und dahinter die nur anlegenden Schreibwege, die eine Datei, eine Karte oder eine Zeile in einem mit
anderen geteilten Container hinterlassen können. Diese drei zusammen sind das, was Simon Willison
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) nennt, und ein
Sprachmodell trennt Daten und Anweisungen nicht zuverlässig, also kann eine Mail einen Satz tragen,
der dem Modell gilt, und die Antwort kann den Weg nach draußen nehmen.

Zwei Dinge stehen dagegen. `talk_send` liegt hinter dem Admin-Schalter `NC_MCP_TALK_SEND`, der den
direkten Nachrichtenkanal für die ganze Instanz schließt, während das Lesen unberührt bleibt; die
nur anlegenden Schreibwege bleiben offen, weshalb, wer jeden Weg geschlossen braucht, auch prüft,
welche Ordner, Boards und Tabellen die verbundenen Konten teilen. Und **Mail ist strikt lesend**:
diese Familie fügt Reichweite hinzu und bewusst keinen eigenen Weg nach draußen. Keines von beidem
macht Prompt Injection unmöglich. Die lange Fassung, mit jeder Gegenmaßnahme und dem ehrlichen Rest,
steht in [docs/privacy.md](docs/privacy.md), Abschnitt "The chain that mail closes".

## Bekannte Einschränkungen

Dinge, die keine Mängel sind, Sie aber einmal überraschen werden. Jede davon ist ein bewusster Kompromiss,
und jede ist in der Antwort sichtbar, die das Tool gibt, statt hinter einem leeren Ergebnis verborgen.

| Einschränkung | Was Sie sehen | Was zu tun ist |
|------------|--------------|------------|
| **Suche trifft Namen, nicht Inhalte** | Jede Suchantwort trägt `"note":"matched on names only; contents are not indexed"` | Installieren und konfigurieren Sie die Nextcloud-Full-text-search-App, oder suchen Sie nach Dateinamen |
| **Ein mit `occ user:add` erstelltes Konto hat keinen Kalender** | `calendar_list_events` gibt einen Fehler zurück, der den fehlenden Kalender benennt | `occ dav:create-calendar <user> personal`, oder melden Sie sich einmal über die Web-UI bei Nextcloud an, was ihn erstellt |
| **Dasselbe gilt für das Adressbuch** | `contacts_search` benennt den Ausweg, statt nichts zurückzugeben | `occ dav:create-addressbook <user> contacts` |
| **Notes, Deck, Tables, Talk und Mail sind optionale Apps** | Die Tools bleiben überall in `tools/list` und antworten "The Notes app is not installed on this Nextcloud.", "The Tables app is not enabled on this Nextcloud.", "The Talk app is not available on this Nextcloud." oder "The Mail app is not available on this Nextcloud." | Installieren Sie die App, oder ignorieren Sie diese zehn Tools |
| **Zwei Mails derselben Sendesekunde können an einer Seitengrenze auseinanderfallen** | Die Paginierung der Mail-App vergleicht die Sendezeit strikt, von zwei Nachrichten mit derselben Sekunde fehlt die zweite auf der nächsten Seite, dauerhaft | Fragen Sie ein größeres `limit` an, das macht die Grenze seltener. Die Grenze gehört der App, und dieser Server korrigiert sie nicht heimlich: eine eigene Korrektur wäre eine zweite Wahrheit über die Reihenfolge, und zwei Aufrufer mit demselben Fenster sähen verschiedene Listen |
| **Keine Volltextsuche in Mail-Inhalten** | Es gibt keinen `body:`-Filter, und die Grammatik lehnt ihn ab wie jeden anderen unbekannten Typ | Nutzen Sie die Suche der Mail-App selbst. Dort gibt es `body:`, aber er verlässt die Datenbank und sucht über IMAP, was pro Aufruf eine Runde zum Mailserver des Nutzers kostet |
| **Ein nie synchronisiertes Postfach und ein nicht erreichbarer Mailserver** | Beide antworten als Fehler, dessen Satz auf das Konto in der Mail-App zeigt, nicht auf Nextcloud | Öffnen Sie das Konto einmal in der Mail-App und lassen Sie es synchronisieren, oder reparieren Sie das Konto dort. Keiner der beiden Fälle ist ein Nextcloud-Problem, und keiner wird mit einer leeren Liste beantwortet |
| **Nichts kann gelöscht oder überschrieben werden** | `files_upload` lehnt einen bestehenden Pfad mit einem Konflikt ab, und es gibt überhaupt kein Update- oder Delete-Tool | Wählen Sie einen anderen Namen. Das ist die Design-Einschränkung, kein fehlendes Feature |
| **Keine Sitzung, also kein serverseitiger Paging-Zustand** | Eine lange Liste gibt ein `next`-Handle zurück, das Sie erneut übergeben | Nichts. Das Handle übersteht einen Neustart, und genau das ist der Sinn |
| **Kalender brauchen ein explizites Zeitfenster mit Zone** | Ein `start` oder `end` ohne Zone wird abgelehnt | Senden Sie `2026-09-01T00:00:00+02:00` oder `...Z`. Eine geratene Zone ist eine selbstsicher falsche Antwort |
| **Eine IP für viele Nutzer löst den Brute-Force-Schutz aus** | `429` nach einem falschen App password, für alle hinter derselben Bereitstellung | Warten Sie und verwenden Sie ein korrektes App password; siehe den Troubleshooting-Abschnitt in der Client-Einrichtung |
| **Nicht jede Assistenz-App kann eine OAuth-Anmeldung abschließen** | Eine App, die auf eine Adresse ihres eigenen Schemas zurückgeschickt werden will, etwa Cursor, wird bei der Anmeldung abgelehnt, und die Seite nennt den Weg, der funktioniert | Verwenden Sie ein App password auf demselben Endpunkt `/exapps/mcp_connector/mcp`; der ExApp-Modus akzeptiert beides, siehe [docs/client-setup.md](docs/client-setup.md) |

Phase 2 machte den Server als Nextcloud-ExApp über AppAPI installierbar, wobei jede Anfrage unter der
eigenen Identität des aufrufenden Nutzers läuft. Drei Dokumente halten das fest sowie die beiden Spikes,
von denen es abhing:

- [docs/exapp-install.md](docs/exapp-install.md): die Installation der App als ExApp auf der
  HaRP-Topologie, die Belege, die bekannten Fallstricke und die Nextcloud-AIO-Übergabe an Phase 5.
- [docs/spike-discovery.md](docs/spike-discovery.md): die Discovery-Entscheidung für die
  OAuth-Topologie der Phase 3, mit der gemessenen Matrix und dem Reverse-Proxy-Fallback.
- [docs/spike-dav.md](docs/spike-dav.md): das DAV-Impersonation-Ergebnis, nämlich dass alle sechs
  API-Familien unter einem Impersonation-Modus laufen, sodass es keine Provider-Aufteilung je Familie
  gibt.

## Enterprise

Das Audit-Log gehört zu dieser App und nicht zu einem Add-on. Eingeschaltet hält es jeden
Werkzeugaufruf fest: das Konto, für das er lief, das Werkzeug, die Zeit, die aufrufende App und
das Ergebnis, nie einen Parameterwert und nie einen Teil eines Ergebnisses. Es ist ab Werk aus,
die Administration schaltet es in den Admin-Einstellungen dieser App ein, und gelesen wird es mit
`occ mcp_connector:audit:read`. Jeder Eintrag ist mit dem vorigen hash-verkettet, und
`occ mcp_connector:audit:verify` prüft die Ketten und nennt die erste Stelle, an der eine
gebrochen ist.

Zwei Dinge sind als kommerzielles Add-on geplant: Gruppen-Policies und die Anmeldung über den
Identitätsanbieter, den Ihre Organisation ohnehin betreibt. Für Evaluierung und Einsatz in
Ihrer Organisation stehen wir zur Verfügung: admin@infranode.dev

## Entwicklung

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest` startet nichts und braucht nichts. Die beiden schwereren Schichten sind opt-in:

- `uv run pytest -m matrix` startet den HTTP-Server als Subprozess und prüft, dass ein aktueller Client
  und ein Client auf MCP SDK 1.29 beide vom selben Endpunkt bedient werden, und dass die Konversation
  einen Neustart übersteht. Es braucht kein Nextcloud.
- `uv run pytest -m integration` braucht das lokale Test-Nextcloud aus `compose.test.yml`.

## Lizenz

AGPL-3.0-or-later, siehe [LICENSE](LICENSE).

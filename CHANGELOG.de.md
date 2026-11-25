<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Changelog

Alle wesentlichen Änderungen an dieser App stehen hier. Das Format folgt
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), und das Projekt hält
sich an [Semantic Versioning](https://semver.org/lang/de/spec/v2.0.0.html).
Deutsche Fassung ab 0.7.2; ältere Einträge stehen in [CHANGELOG.md](CHANGELOG.md).

## [Unreleased]

### Hinzugefügt

- `files_update` kann eine bestehende Datei bekannten Typs (docx, xlsx, pptx, OpenDocument,
  PDF, PNG, JPEG, GIF, WebP, UTF-8-Text) durch einen ChatGPT-Anhang (`file`) ersetzen, unter
  derselben ETag-Bedingung wie bei Text (`content`). ETag und Ausschluss-Tag werden vor dem
  Herunterladen des Anhangs und noch einmal unmittelbar vor dem Schreiben geprüft.
- Der Schalter "Allow replacing existing files with an attachment"
  (`NC_MCP_FILES_UPDATE_ATTACHMENT`) ist ab Werk aus und wirkt nur zusammen mit
  `NC_MCP_FILES_UPDATE`, sodass ein Admin Textänderungen erlauben kann, ohne binäres Ersetzen
  zu erlauben. Er steht unter Administrationseinstellungen, Sicherheit, MCP Connector und ist
  als Umgebungsvariable deklariert. Eine Änderung wirkt, nachdem Sie diese App einmal aus- und
  wieder eingeschaltet haben. Ist er aus, ist `files_update` in der Tool-Liste das aus 0.9.0.
- Der Anhang wird gegen den Typ der bestehenden Datei geprüft, nicht gegen den Typ, den er
  angibt. Eine docx-, xlsx-, pptx- oder OpenDocument-Datei wird geöffnet und ihre Struktur
  geprüft. Die ZIP-Datei darf höchstens 10.000 Einträge und ein zentrales Verzeichnis von
  höchstens 16 MiB haben, gezählt am Verzeichnis selbst, bevor sie geöffnet wird, und keine
  ZIP64-Einträge. Eine Office-Datei braucht eine `[Content_Types].xml`, die ihren Hauptteil
  (`word/document.xml`, `xl/workbook.xml`, `ppt/presentation.xml`) als Dokument, Arbeitsmappe
  oder Präsentation ausweist (eine Vorlage oder ein Makro-Typ ist ein anderer Typ), und das
  erste Element dieses Hauptteils, gesucht in seinen ersten 64 KiB, muss das Wurzelelement
  dieses Typs sein; der Teil wird nicht ganz geparst. Eine OpenDocument-Datei braucht
  `mimetype` physisch als erstes Element, unkomprimiert, ohne Extra-Feld und mit genau diesem
  Typ, eine `META-INF/manifest.xml`, deren Wurzelelement `manifest` ist und deren
  Wurzeleintrag denselben Typ nennt, und eine `content.xml` oder `styles.xml`.
  `[Content_Types].xml` und `manifest.xml` werden bis 4 MiB gelesen. Das XML wird mit einem
  Parser gelesen, der jede DTD und jede Entitätsdeklaration ablehnt. Ein PDF oder ein Bild
  wird nur an den ersten Bytes verglichen (`%PDF-`, PNG, JPEG, GIF, WebP) und nicht als Ganzes
  analysiert; ein abgeschnittenes passiert also. Eine Textdatei muss UTF-8 ohne NUL-Byte sein
  und darf nicht wie ein Binärformat beginnen. Die älteren Dateien doc, xls und ppt teilen
  eine Signatur und lassen sich an den ersten Bytes nicht unterscheiden; sie lassen sich daher
  nicht ersetzen. Eine bestehende Datei eines Typs ohne bekannte Signatur wird vor dem
  Herunterladen mit der Liste der ersetzbaren Typen abgelehnt.
- `files_download` liefert das ETag der Datei im ersten Abschnitt, damit eine Binärdatei einen
  Anhaltspunkt für `files_update` hat. Spätere Abschnitte tragen es nicht.

## [0.9.0] - 2026-11-20

### Hinzugefügt

- `profile_fields_browse`: ein optionales Tool nur zum Lesen für die Nextcloud-App Profile
  Fields, ab Werk aus. 27 Tools im Standard, 28 mit eingeschaltetem Schalter. Danke an
  Vitor Mattos (@vitormattos) für #49.
- Der Schalter "Allow reading Profile Fields" (`NC_MCP_PROFILE_FIELDS_READ`) steht unter
  Administrationseinstellungen, Sicherheit, MCP Connector und ist als Umgebungsvariable
  deklariert, damit eine Installation aus dem App Store das Tool einschalten kann. Eine
  Änderung wirkt, nachdem die App einmal deaktiviert und wieder aktiviert wurde.
- Ebenen: `me` für die eigenen sichtbaren Felder; `definitions`, `values` und `search`
  nutzen Routen, die die App Administratoren vorbehält. Nur OCS-GET-Anfragen mit den
  Berechtigungen des verbundenen Kontos; nichts wird angelegt, geändert oder gelöscht.
  Die UID `.` oder `..` wird abgelehnt, bevor eine Anfrage gesendet wird.
- Der Schalter steuert nur dieses Tool. Die Suche (`unified_search`, `search`,
  `prepare_context`) erreicht den Suchprovider der App mit und ohne Schalter und folgt den
  Berechtigungen der App: Ein Administrator findet private Werte, jedes andere Konto nur
  Werte, die die App ihm zeigt.
- Die CI installiert Profile Fields aus dem App Store und beweist das Tool live über einen
  echten MCP-Client im Job `integration`: 27 Tools ohne Schalter, 28 mit Schalter, kein
  fremder Wert für ein Konto ohne Administratorrechte.
- Fehlt die App Profile Fields, ist sie deaktiviert oder für keine Gruppe des Kontos
  aktiviert, meldet das Tool das und sagt, wie sich das beheben lässt.
- Gemessen auf Nextcloud 34 mit Profile Fields 4.0.0. Auf Nextcloud 35 gibt es Profile
  Fields nur als Nightly; dort meldet das Tool, dass die App fehlt.

### Geändert

- Tool-Beschreibungen und Fehlerhinweise nennen Vorbedingungen und Fehler statt
  Zusicherungen, damit eine Freigabeprüfung wie die in ChatGPT Business sie nicht als
  Versuch liest, die Risikoeinstufung zu senken (Issue #53, gemeldet von Excauboi). Das
  Verhalten ist unverändert, die Zusagen stehen weiter in README und Dokumentation.
- Die Beschreibung im App Store ist jetzt kurz und verweist für die Details auf das README
  der jeweiligen Sprache.

## [0.8.0] - 2026-11-14

### Hinzugefügt

- `files_create_folder` im Bundle `files`: legt einen Ordner an, mit `parents=true` auch
  die fehlenden Elternordner, höchstens 10 neue Ordner je Aufruf; ein vorhandener Ordner
  antwortet mit `created` false.
- Die Antwort nennt den Pfad, `created` und die Datei-ID (`file:<n>`), mit `parents=true`
  auch die Liste der tatsächlich angelegten Ordner. Ein Abbruch mittendrin nennt, was
  schon angelegt wurde, und lässt es stehen.
- Es gilt jede Grenze von `files_upload`: der Ausschluss `kein-ki` (abgewiesen wie bei
  einem fehlenden Elternordner; solange die Prüfung nicht beantwortet werden kann, wird
  nichts geschrieben), die Sandbox `NC_MCP_FILES_ROOT` (die Wurzel wird nie angelegt) und
  keine eigene Rechteprüfung (Nextcloud entscheidet; ein fehlendes Recht bekommt eine
  eigene Meldung).
- Ein Netzfehler mitten in einer Ordnerkette nennt die schon angelegten Ordner und sagt,
  dass der Zustand des gerade bearbeiteten Ordners unbekannt ist.
- Ein Ordnername mit Leerraum am Anfang oder Ende wird abgelehnt, bevor etwas geschrieben
  wird.
- Ein Name wie `x.part` wird nicht als vorhandene Datei gemeldet.
- Auf Nextcloud 35 bekommt ein Name, den Nextcloud nicht annimmt, in einer Kette mit
  `parents=true` die Meldung eines abgelehnten Namens statt eines Serverfehlers.
- Gemessen auf Nextcloud 32 und 35 unter AppAPI-Impersonation, siehe
  `docs/folder-evidence.md`.
- Drei Werkzeuge im neuen Bundle `tasks`, der zehnten App-Familie, abschaltbar über
  `NC_MCP_DISABLED_TOOLS`: `tasks_search`, `tasks_read` und `tasks_create`.
- `tasks_search` durchsucht eigene und geteilte Aufgabenlisten, standardmäßig offene
  Aufgaben; `status` nimmt open, completed oder all; 25 Treffer je Seite.
- Eine geteilte Liste erscheint ohne Namen und ohne Kennung der Person, die sie geteilt hat.
- `tasks_read` liefert eine Aufgabe mit ihren direkten Unteraufgaben.
- `tasks_create` legt nur an: ohne `list` nur, wenn es genau eine eigene Liste gibt und
  niemand sonst sie sieht, nie in eine Liste, die andere sehen, außer sie wird genannt
  (eine mit dem Konto geteilte Liste oder eine eigene, die an andere geteilt oder per Link
  veröffentlicht ist), und nie in einen Deck-Kalender.
- Eine Fälligkeit ohne Uhrzeit bleibt auf genau diesem Tag.
- `fetch` liest `task:`-IDs, und ein Treffer des Nextcloud-Suchproviders `tasks` führt
  auf dieselbe ID; für eine Aufgabe aus einer geteilten Liste verlinkt `fetch` nur die
  Startseite der Tasks-App. Wie `tasks_read` kennzeichnet `fetch` eine gekürzte
  Beschreibung und eine Zeit ohne Zeitzone.
- Gemessen auf Nextcloud 32 und 35 unter AppAPI-Impersonation, siehe
  `docs/tasks-evidence.md`.
- Drei Werkzeuge, die bestehende Aufgaben ändern, hinter dem neuen Admin-Schalter
  `NC_MCP_TASKS_UPDATE` ("Allow changing existing tasks", Bestehende Aufgaben ändern
  erlauben), ab Werk aus:
  `tasks_complete` hakt eine Aufgabe ab oder öffnet sie wieder, `tasks_update` ändert ihre
  Felder, `tasks_move` verschiebt sie samt Unteraufgaben in eine andere Liste. Alle drei
  gehören zum Bundle `tasks`.
- `tasks_read` liefert das ETag der Aufgabe, und jedes der drei Werkzeuge arbeitet nur mit
  ihm; ein veraltetes ETag wird abgelehnt. Wiederkehrende Aufgaben werden abgelehnt.

### Geändert

- Die Server-Instruktion sagt zusätzlich "Tasks are never deleted." (Aufgaben werden
  nie gelöscht).
- Die Dokumentation sagt genau, was Bestehendes ändert: `files_update` und die drei
  Aufgaben-Werkzeuge, jedes nur hinter seinem Admin-Schalter; nichts löscht, auch keine
  Aufgabe, und außer `tasks_move` verschiebt nichts. Die Admin-Anleitung
  (`docs/exapp-install.md`) erklärt beide Schreibschalter und dass ein Schalter auf
  einer laufenden Installation mit `occ app_api:app:config:set ... --update-only`
  geändert wird; ohne diese Option lehnt occ es ab, einen schon gesetzten Wert zu
  ändern.
- Die Beschreibung im App Store auf Englisch, Deutsch und Französisch nennt Ordner,
  Aufgaben, die Löschgrenze und den Schalter zum Ändern von Aufgaben.

### Behoben

- `unified_search` und `search` zeigen bei einem Treffer des Nextcloud-Suchproviders
  `tasks` aus einer geteilten Aufgabenliste den Namen der Person, die sie geteilt hat,
  nicht mehr; wo er sich nicht sicher entfernen lässt, fehlt die Zeile.

## [0.7.3] - 2026-11-13

### Sicherheit

- opentelemetry-api von 1.45.1 auf 1.45.2 angehoben, das behebt CVE-2026-126360
  (GHSA-mf5v-w3w3-f6cg, niedrig): ein langsamer regulärer Ausdruck beim Lesen des
  Headers `traceparent` eingehender Anfragen, erreichbar über das MCP-SDK.
  pip-audit über den ausgelieferten Paketsatz ist wieder sauber.

## [0.7.2] - 2026-11-06

### Behoben

- Die zehn Variablen `NC_MCP_EXCHANGE_*` sind in `appinfo/info.xml` deklariert.
  Vorher ließ der Deploy-Daemon sie ohne ein Wort fallen, sodass eine Installation
  aus dem App Store den Token-Exchange-Pfad nicht scharf schalten konnte:
  `occ app_api:app:register --env` nahm sie an, und der Container sah sie nie (#42).
  Ein Test hält die Deklarationen jetzt gleich mit der Liste, aus der der Code sie
  liest.

[Unreleased]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.7.3...v0.8.0

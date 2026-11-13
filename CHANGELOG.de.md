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

## [0.7.2] - 2026-11-06

### Behoben

- Die zehn Variablen `NC_MCP_EXCHANGE_*` sind in `appinfo/info.xml` deklariert.
  Vorher ließ der Deploy-Daemon sie ohne ein Wort fallen, sodass eine Installation
  aus dem App Store den Token-Exchange-Pfad nicht scharf schalten konnte:
  `occ app_api:app:register --env` nahm sie an, und der Container sah sie nie (#42).
  Ein Test hält die Deklarationen jetzt gleich mit der Liste, aus der der Code sie
  liest.

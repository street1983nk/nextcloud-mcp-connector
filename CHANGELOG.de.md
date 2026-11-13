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

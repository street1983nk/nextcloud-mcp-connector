<!--
  - SPDX-FileCopyrightText: 2026 street1983nk
  - SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Changelog

Toutes les modifications notables de cette app sont consignées ici. Le format
suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet
respecte [Semantic Versioning](https://semver.org/lang/fr/spec/v2.0.0.html).
Version française à partir de 0.7.2 ; les entrées plus anciennes se trouvent
dans [CHANGELOG.md](CHANGELOG.md).

## [Unreleased]

## [0.7.2] - 2026-11-06

### Corrigé

- Les dix variables `NC_MCP_EXCHANGE_*` sont déclarées dans `appinfo/info.xml`.
  Auparavant, le démon de déploiement les abandonnait sans un mot, si bien qu'une
  installation depuis l'App Store ne pouvait pas activer le chemin d'échange de
  jetons : `occ app_api:app:register --env` les acceptait et le conteneur ne les
  voyait jamais (#42). Un test maintient désormais les déclarations identiques à
  la liste dans laquelle le code les lit.

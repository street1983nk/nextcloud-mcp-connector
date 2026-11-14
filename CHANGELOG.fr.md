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

## [0.8.0] - 2026-11-14

### Ajouté

- `files_create_folder` dans le bundle `files` : crée un dossier, ou avec `parents=true`
  également les dossiers parents manquants, au plus 10 nouveaux dossiers par appel ; un
  dossier existant répond `created` false.
- La réponse contient le chemin, `created` et l'id du fichier (`file:<n>`), avec
  `parents=true` également la liste des dossiers réellement créés. Un arrêt en cours de
  route nomme ce qui a déjà été créé et le laisse en place.
- Toutes les limites de `files_upload` s'appliquent : l'exclusion `kein-ki` (refus comme
  pour un dossier parent manquant ; rien n'est écrit tant que la vérification reste sans
  réponse), le bac à sable `NC_MCP_FILES_ROOT` (la racine n'est jamais créée) et aucune
  vérification de droits propre (Nextcloud décide ; un droit manquant reçoit son propre
  message).
- Une panne réseau au milieu d'une chaîne de dossiers nomme les dossiers déjà créés et
  indique que l'état du dossier en cours d'écriture à ce moment est inconnu.
- Un nom de dossier qui commence ou se termine par un espace blanc est refusé avant toute
  écriture.
- Un nom comme `x.part` n'est pas signalé comme un fichier existant.
- Sur Nextcloud 35, un nom que Nextcloud n'accepte pas, dans une chaîne avec
  `parents=true`, reçoit le message d'un nom refusé au lieu d'une erreur du serveur.
- Mesuré sur Nextcloud 32 et 35 sous impersonation AppAPI, voir
  `docs/folder-evidence.md`.
- Trois outils dans le nouveau bundle `tasks`, la dixième famille d'applications,
  désactivable via `NC_MCP_DISABLED_TOOLS` : `tasks_search`, `tasks_read` et `tasks_create`.
- `tasks_search` cherche dans les listes de tâches propres et partagées, par défaut les
  tâches ouvertes ; `status` accepte open, completed ou all ; 25 résultats par page.
- Une liste partagée apparaît sans le nom ni l'identifiant de la personne qui l'a partagée.
- `tasks_read` renvoie une tâche avec ses sous-tâches directes.
- `tasks_create` ne fait que créer : sans `list` seulement s'il existe exactement une liste
  propre et que personne d'autre ne la voit, jamais dans une liste que d'autres voient sauf
  si elle est nommée (une liste partagée avec le compte, ou une liste propre partagée avec
  d'autres ou publiée par lien), et jamais dans un agenda Deck.
- Une échéance sans heure reste exactement sur ce jour.
- `fetch` lit les ids `task:`, et un résultat du fournisseur de recherche Nextcloud `tasks`
  mène au même id ; pour une tâche d'une liste partagée, `fetch` ne renvoie que vers la
  page d'accueil de l'app Tasks. Comme `tasks_read`, `fetch` signale une description
  tronquée et une heure sans fuseau horaire.
- Mesuré sur Nextcloud 32 et 35 sous impersonation AppAPI, voir
  `docs/tasks-evidence.md`.
- Trois outils qui modifient des tâches existantes, derrière le nouvel interrupteur
  d'administration `NC_MCP_TASKS_UPDATE` (« Allow changing existing tasks », autoriser
  la modification des tâches existantes), désactivé par défaut : `tasks_complete` coche une tâche ou la rouvre,
  `tasks_update` modifie ses champs, `tasks_move` la déplace avec ses sous-tâches dans une
  autre liste. Les trois font partie du bundle `tasks`.
- `tasks_read` renvoie l'ETag de la tâche, et chacun des trois outils ne fonctionne qu'avec
  lui ; un ETag périmé est refusé. Les tâches récurrentes sont refusées.

### Modifié

- L'instruction du serveur dit en plus « Tasks are never deleted. » (les tâches ne
  sont jamais supprimées).
- La documentation dit exactement ce qui modifie l'existant : `files_update` et les
  trois outils de tâches, chacun seulement derrière son interrupteur d'administration ;
  rien ne supprime, pas même une tâche, et rien ne déplace sauf `tasks_move`. Le guide
  d'administration (`docs/exapp-install.md`) explique les deux interrupteurs
  d'écriture et qu'un interrupteur se change, sur une installation en service, avec
  `occ app_api:app:config:set ... --update-only` ; sans cette option, occ refuse de
  modifier une valeur déjà définie.
- La description dans l'App Store en anglais, allemand et français nomme les dossiers,
  les tâches, la limite de suppression et l'interrupteur de modification des tâches.

### Corrigé

- `unified_search` et `search` n'affichent plus le nom de la personne qui a partagé une
  liste de tâches dans un résultat du fournisseur de recherche Nextcloud `tasks` issu de
  cette liste ; là où ce nom ne peut pas être retiré sans risque, la ligne est omise.

## [0.7.3] - 2026-11-13

### Sécurité

- opentelemetry-api passe de 1.45.1 à 1.45.2, ce qui corrige CVE-2026-126360
  (GHSA-mf5v-w3w3-f6cg, faible) : une expression régulière lente lors de la
  lecture de l'en-tête `traceparent` des requêtes entrantes, atteinte via le SDK
  MCP. pip-audit sur l'ensemble livré est de nouveau propre.

## [0.7.2] - 2026-11-06

### Corrigé

- Les dix variables `NC_MCP_EXCHANGE_*` sont déclarées dans `appinfo/info.xml`.
  Auparavant, le démon de déploiement les abandonnait sans un mot, si bien qu'une
  installation depuis l'App Store ne pouvait pas activer le chemin d'échange de
  jetons : `occ app_api:app:register --env` les acceptait et le conteneur ne les
  voyait jamais (#42). Un test maintient désormais les déclarations identiques à
  la liste dans laquelle le code les lit.

[Unreleased]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.7.3...v0.8.0

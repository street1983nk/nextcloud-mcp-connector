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
  propre, jamais en silence dans une liste partagée et jamais dans un agenda Deck.
- Une échéance sans heure reste exactement sur ce jour.
- `fetch` lit les ids `task:`, et un résultat du fournisseur de recherche Nextcloud `tasks`
  mène au même id ; pour une tâche d'une liste partagée, `fetch` ne renvoie que vers la
  page d'accueil de l'app Tasks.
- Mesuré sur Nextcloud 32 et 35 sous impersonation AppAPI, voir
  `docs/tasks-evidence.md`.

## [0.7.2] - 2026-11-06

### Corrigé

- Les dix variables `NC_MCP_EXCHANGE_*` sont déclarées dans `appinfo/info.xml`.
  Auparavant, le démon de déploiement les abandonnait sans un mot, si bien qu'une
  installation depuis l'App Store ne pouvait pas activer le chemin d'échange de
  jetons : `occ app_api:app:register --env` les acceptait et le conteneur ne les
  voyait jamais (#42). Un test maintient désormais les déclarations identiques à
  la liste dans laquelle le code les lit.

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

- `files_update` peut remplacer un fichier existant d'un type connu (docx, xlsx, pptx,
  OpenDocument, PDF, PNG, JPEG, GIF, WebP, texte UTF-8) par une pièce jointe ChatGPT (`file`),
  avec la même condition d'ETag que pour le texte (`content`). L'ETag et l'étiquette
  d'exclusion sont vérifiés avant le téléchargement de la pièce jointe, puis de nouveau juste
  avant l'écriture.
- Le commutateur « Allow replacing existing files with an attachment »
  (`NC_MCP_FILES_UPDATE_ATTACHMENT`) est désactivé par défaut et n'agit qu'avec
  `NC_MCP_FILES_UPDATE`, si bien qu'un administrateur peut autoriser les modifications de
  texte sans autoriser les remplacements binaires. Il figure dans Paramètres d'administration,
  Sécurité, MCP Connector et est déclaré comme variable d'environnement. Une modification
  prend effet après avoir désactivé puis réactivé cette app. Désactivé, `files_update` dans la
  liste des outils est celui de la 0.9.0.
- La pièce jointe est vérifiée par rapport au type du fichier existant, et non au type qu'elle
  déclare. Un fichier docx, xlsx, pptx ou OpenDocument est ouvert et sa structure vérifiée. Le
  fichier ZIP ne doit pas avoir plus de 10 000 entrées ni un répertoire central de plus de 16
  Mio, comptés sur le répertoire lui-même avant l'ouverture, et pas d'enregistrements ZIP64.
  Un fichier Office doit avoir un `[Content_Types].xml` qui déclare sa partie principale
  (`word/document.xml`, `xl/workbook.xml`, `ppt/presentation.xml`) comme document, classeur ou
  présentation (un modèle ou un type avec macros est un autre type), et le premier élément de
  cette partie principale, cherché dans ses 64 premiers Kio, doit être l'élément racine de ce
  type ; la partie n'est pas analysée en entier. Un fichier OpenDocument doit avoir `mimetype`
  physiquement en premier, stocké, sans champ extra et avec exactement ce type, un
  `META-INF/manifest.xml` dont l'élément racine est `manifest` et dont l'entrée racine nomme
  le même type, et un `content.xml` ou `styles.xml`. `[Content_Types].xml` et `manifest.xml`
  sont lus jusqu'à 4 Mio. Le XML est lu avec un analyseur qui refuse toute DTD et toute
  déclaration d'entité. Un PDF ou une image n'est comparé que sur ses premiers octets
  (`%PDF-`, PNG, JPEG, GIF, WebP) et n'est pas analysé en entier : un fichier tronqué passe
  donc. Un fichier texte doit être en UTF-8 sans octet NUL et ne pas commencer comme un format
  binaire. Les anciens fichiers doc, xls et ppt partagent une signature et ne se distinguent
  pas par leurs premiers octets : ils ne sont pas remplaçables. Un fichier existant d'un type
  sans signature connue est refusé avant le téléchargement, avec la liste des types
  remplaçables.
- `files_download` renvoie l'ETag du fichier dans le premier tronçon, de sorte qu'un fichier
  binaire dispose d'une référence pour `files_update`. Les tronçons suivants ne le portent pas.

## [0.9.0] - 2026-11-20

### Ajouté

- `profile_fields_browse` : un outil facultatif en lecture seule pour l'application
  Nextcloud Profile Fields, désactivé par défaut. 27 outils par défaut, 28 avec le
  commutateur activé. Merci à Vitor Mattos (@vitormattos) pour #49.
- Le commutateur « Allow reading Profile Fields » (`NC_MCP_PROFILE_FIELDS_READ`) figure
  dans Paramètres d'administration, Sécurité, MCP Connector et est déclaré comme variable
  d'environnement, pour qu'une installation depuis l'App Store puisse activer l'outil. Un
  changement prend effet une fois l'application désactivée puis réactivée.
- Niveaux : `me` pour les champs visibles du compte lui-même ; `definitions`, `values` et `search`
  utilisent des routes que l'application réserve aux administrateurs. Uniquement des
  requêtes OCS GET avec les permissions du compte connecté ; rien n'est créé, modifié ni
  supprimé. L'UID `.` ou `..` est refusé avant l'envoi de toute requête.
- Le commutateur ne pilote que cet outil. La recherche (`unified_search`, `search`,
  `prepare_context`) atteint le fournisseur de recherche de l'application avec ou sans lui
  et suit les permissions de l'application : un administrateur trouve les valeurs privées,
  tout autre compte seulement les valeurs que l'application lui montre.
- La CI installe Profile Fields depuis l'App Store et prouve l'outil en conditions réelles
  par un vrai client MCP dans le job `integration` : 27 outils sans le commutateur, 28 avec,
  aucune valeur d'autrui pour un compte sans droits d'administrateur.
- Si l'application Profile Fields est absente ou désactivée, ou si elle n'est activée
  pour aucun des groupes du compte, l'outil le signale et indique comment y remédier.
- Mesuré sur Nextcloud 34 avec Profile Fields 4.0.0. Sur Nextcloud 35, Profile Fields
  n'est disponible qu'en version nightly ; l'outil y signale que l'application est
  absente.

### Modifié

- Les descriptions des outils et les indications d'erreur énoncent des conditions
  préalables et des erreurs au lieu d'assurances, afin qu'un contrôle d'approbation comme
  celui de ChatGPT Business ne les lise pas comme une tentative d'abaisser le niveau de
  risque (ticket #53, signalé par Excauboi). Le comportement est inchangé ; les garanties
  restent dans le README et la documentation.
- La description dans l'App Store est désormais courte et renvoie au README de sa langue
  pour les détails.

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

[Unreleased]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/street1983nk/nextcloud-mcp-connector/compare/v0.7.3...v0.8.0

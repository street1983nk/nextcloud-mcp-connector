[English](README.md) | [Deutsch](README.de.md) | **Français**

> Le README anglais (README.md) fait foi ; cette traduction est mise à jour ensuite.

# MCP Connector pour Nextcloud

[![CI](https://github.com/street1983nk/nextcloud-mcp-connector/actions/workflows/ci.yml/badge.svg)](https://github.com/street1983nk/nextcloud-mcp-connector/actions/workflows/ci.yml)
[![Security scans](https://github.com/street1983nk/nextcloud-mcp-connector/actions/workflows/security.yml/badge.svg)](https://github.com/street1983nk/nextcloud-mcp-connector/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/street1983nk/nextcloud-mcp-connector/badge)](https://scorecard.dev/viewer/?uri=github.com/street1983nk/nextcloud-mcp-connector)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15326/badge)](https://www.bestpractices.dev/projects/15326)
[![Nextcloud App Store](https://img.shields.io/badge/App_Store-mcp__connector-0082c9)](https://apps.nextcloud.com/apps/mcp_connector)
[![Licence](https://img.shields.io/badge/Licence-AGPL--3.0--or--later-blue)](LICENSE)

Un serveur MCP soigneusement sélectionné qui relie votre Nextcloud (fichiers, agenda, notes,
Deck, contacts, Tables, Talk et Mail) à des assistants IA tels que Claude, Cursor, ChatGPT ou
vos propres agents. Installé comme ExApp Nextcloud, il est en même temps son propre serveur
d'autorisation OAuth 2.1.

**Findling + Nextcloud MCP Connector = la couche de récupération de votre propre RAG.**
[Findling](https://apps.nextcloud.com/apps/findling) rend le contenu de vos documents
interrogeable, scans compris. Le connecteur transmet ces résultats à tout client MCP, avec
exactement les droits de l'utilisateur qui demande ; mesuré dans
[tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py).
Le modèle, c'est vous qui l'apportez, et aucun contenu ne quitte votre serveur.

## Ce qu'il sait faire

- 27 outils répartis sur dix familles d'applications : fichiers, agenda, tâches (Tasks),
  notes, Deck, contacts, Tables, Talk, Mail et la recherche à l'échelle du cloud
- OAuth 2.1 conforme à la spécification d'autorisation MCP : enregistrement dynamique des
  clients, PKCE S256, jetons liés à leur audience, rotation des jetons de rafraîchissement
  avec détection de réutilisation et révocation immédiate. Claude.ai et ChatGPT reçoivent une
  URL et ne voient jamais de mot de passe
- Chaque requête s'exécute avec les droits de l'utilisateur connecté : les permissions
  Nextcloud s'appliquent sans changement, et l'assistant ne voit jamais plus que vous
- Gestion par utilisateur : chaque compte suspend ou réactive son propre accès et déconnecte
  un assistant en particulier, sur la page des connexions sous Paramètres, Sécurité,
  MCP Connector
- `prepare_context` regroupe une recherche, la semaine d'événements à venir, les conversations
  Talk en attente et les compteurs de courriels non lus en un seul appel, chaque source avec
  son propre budget de temps
- Un ensemble d'outils délibérément restreint, pour que ce serveur cohabite avec vos autres
  serveurs MCP, même dans des clients avec une limite stricte du nombre d'outils
- Aucune tâche planifiée, aucune indexation, aucune télémétrie, aucune copie de vos données,
  et aucun identifiant n'est jamais journalisé

## Ce que ce serveur ne peut pas faire

- Aucune suppression : aucun outil ne supprime de fichiers, d'événements, de tâches, de notes,
  de cartes ou de contacts ; la suppression d'une tâche n'est volontairement pas proposée
- Pas d'écrasement inconditionnel : `files_upload` refuse un chemin existant. Si
  l'administrateur active `NC_MCP_FILES_UPDATE`, `files_update` ne remplace un fichier texte
  UTF-8 existant que si son ETag correspond à la valeur lue auparavant ; les fichiers modifiés
  ou supprimés sont refusés. L'historique des versions dépend du backend de stockage de
  Nextcloud.
- Les tâches existantes restent inchangées tant que l'administrateur n'active pas
  l'interrupteur « Autoriser la modification des tâches existantes » (`NC_MCP_TASKS_UPDATE`) :
  Désactivé par défaut. Activé, les assistants peuvent modifier une tâche à la fois, et
  uniquement avec l'ETag renvoyé par `tasks_read` : `tasks_complete` la coche (d'abord ses
  sous-tâches) ou la rouvre, `tasks_update` modifie son titre, sa description, son échéance,
  sa date de début, sa priorité, ses étiquettes ou sa tâche parente, et `tasks_move` la
  déplace avec ses sous-tâches dans une autre liste de tâches propre ou partagée en écriture.
  Les tâches récurrentes et les tableaux Deck sont refusés. Un changement de l'interrupteur
  prend effet après avoir désactivé puis réactivé l'application.
- Aucun déplacement ni renommage de fichiers, de dossiers ou d'autres objets ; la seule
  exception est `tasks_move` pour une seule tâche lorsque `NC_MCP_TASKS_UPDATE` est activé.
  Aucune modification de partage ni de permission ; les fichiers binaires passent par
  l'assemblage privé de blocs de Nextcloud et refusent tout de même une destination existante
- Mail est strictement en lecture seule : aucun envoi, aucun brouillon, aucun déplacement,
  aucun marquage, aucune suppression, aucun téléchargement de pièce jointe
- Aucun accès administrateur : le serveur agit comme un utilisateur et hérite exactement de
  ses droits
- Aucune recherche plein texte dans le contenu des fichiers tant qu'une application de
  recherche comme Findling n'est pas installée

C'est une contrainte de conception et non une promesse de bon comportement : un test de
contrat lit les modules, autorise exactement les exceptions nommées (`files_update` et les
trois outils de tâches, chacun uniquement avec un ETag, le MOVE de l'assemblage privé de blocs
et un MOVE dans `move_todo`) et échoue à tout autre appel destructeur,
[tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py).

## Outils

**read** signifie que l'outil ne fait que lire, **create-only** signifie qu'il peut créer de
nouveaux objets mais ne modifie ni ne supprime jamais ceux qui existent, **conditional-update**
signifie qu'il ne remplace un objet existant que si son ETag correspond encore, et **modify**
signifie qu'il modifie une tâche existante, uniquement avec l'ETag de `tasks_read` et
seulement si l'admin l'active. Le tableau n'est pas
maintenu à la main : un test de contrat lit le registre en cours d'exécution et échoue dès
qu'un nom ou un niveau diverge.

| Tool | Permission | Ce qu'il fait |
|------|------------|---------------|
| `files_search` | read | Fichiers et dossiers par nom via WebDAV search ; le contenu n'est pas indexé |
| `files_list` | read | Les enfants directs d'un dossier, avec taille et date de modification |
| `files_read` | read | Le contenu d'un fichier |
| `files_download` | read | Un fichier de toute taille en blocs de ressource intégrés et limités |
| `files_read_as_markdown` | read | Un fichier DOCX, XLSX, PPTX ou PDF converti en Markdown, par tranches |
| `files_upload` | create-only | Un fichier texte ou binaire en blocs Base64 ; un chemin existant est refusé, jamais écrasé |
| `files_create_folder` | create-only | Un nouveau dossier, au besoin avec ses dossiers parents manquants (au plus 10 par appel) ; un dossier existant répond created false, rien n'est écrasé |
| `files_update` | conditional-update | Remplace un fichier texte UTF-8 existant uniquement avec son ETag lu auparavant ; disponible seulement si l'admin active `NC_MCP_FILES_UPDATE` |
| `calendar_list_events` | read | Les événements d'une plage de temps explicite, avec un fuseau horaire explicite |
| `calendar_create_event` | create-only | Un nouvel événement ; les événements existants ne sont jamais modifiés |
| `tasks_search` | read | Par défaut les tâches ouvertes, des listes de tâches propres et partagées ; 25 par page |
| `tasks_read` | read | Une tâche avec sa description (tronquée) et ses sous-tâches directes |
| `tasks_create` | create-only | Une nouvelle tâche ; sans `list` seulement s'il existe exactement une liste propre et que personne d'autre ne la voit, jamais dans une liste que d'autres voient sauf si elle est nommée |
| `tasks_complete` | modify | Marque une tâche comme terminée ou la rouvre, uniquement avec l'ETag de `tasks_read` ; si elle est terminée, ses sous-tâches le sont d'abord, les tâches récurrentes sont refusées ; disponible seulement si l'admin active `NC_MCP_TASKS_UPDATE` |
| `tasks_update` | modify | Modifie ou efface les champs nommés d'une tâche (titre, description, échéance, début, priorité, étiquettes, tâche parente), uniquement avec l'ETag de `tasks_read` ; toutes les autres lignes de la tâche restent telles quelles, les tâches récurrentes sont refusées ; disponible seulement si l'admin active `NC_MCP_TASKS_UPDATE` |
| `tasks_move` | modify | Déplace une tâche avec ses sous-tâches dans une liste nommée accessible en écriture, uniquement avec l'ETag de `tasks_read` ; les sous-tâches sont déplacées d'abord, un nom ou un UID déjà pris dans la liste cible n'est jamais écrasé, les tableaux Deck ne sont jamais une cible, les tâches récurrentes sont refusées ; disponible seulement si l'admin active `NC_MCP_TASKS_UPDATE` |
| `notes_search` | read | Des notes par titre et contenu, via le fournisseur de recherche de notes Nextcloud |
| `notes_read` | read | Une note |
| `notes_create` | create-only | Une nouvelle note ; les notes existantes ne sont jamais modifiées |
| `deck_browse` | read | Les tableaux, piles et cartes de Deck |
| `deck_create_card` | create-only | Une nouvelle carte dans une pile ; les cartes existantes ne sont jamais modifiées |
| `tables_browse` | read | Tables : les tables, les colonnes d'une table ou ses lignes |
| `tables_create_row` | create-only | Une ligne désignée par les titres de colonnes ; les lignes existantes ne sont jamais modifiées |
| `talk_browse` | read | Les conversations Talk et l'historique de l'une d'elles ; la lecture ne laisse aucune trace |
| `talk_send` | create-only | Un message dans une conversation ; jamais modifié ni supprimé, désactivable pour toute l'instance |
| `mail_browse` | read | Les comptes Mail, leurs boîtes aux lettres et les en-têtes de messages ; strictement en lecture seule |
| `contacts_search` | read | Des contacts dans les carnets d'adresses |
| `unified_search` | read | La recherche unifiée de Nextcloud à travers les fournisseurs, en respectant les permissions |
| `prepare_context` | read | Fichiers, notes, cartes, la semaine d'événements à venir, les conversations Talk en attente et les courriels non lus en un appel |
| `search` | read | Point d'entrée de recherche compatible OpenAI, délègue à la recherche unifiée |
| `fetch` | read | Récupération compatible OpenAI, résout un id vers un fichier, une note, une carte, un événement, un courriel, un message Talk, un tableau ou une tâche |

`search` et `fetch` existent parce que le profil de connecteur ChatGPT exige exactement ces
deux noms et schémas. Ce sont de fines enveloppes autour des outils ci-dessus, pas une seconde
implémentation.

Une réponse de `unified_search`, avec ses deux cas honnêtes : un résultat dont l'id est résolu
par les outils de lecture, et un fournisseur dont les entrées restent une URL au lieu d'un id
inventé. Un fournisseur qui échoue ou qui traîne est nommé sous `degraded`, si bien qu'une
réponse partielle est visiblement partielle. Notes, Deck, Tables, Talk et Mail sont des
applications optionnelles ; la liste des outils reste partout la même, et une application
manquante reçoit une réponse en une phrase, jamais un résultat vide.

```json
{"query":"budget","count":2,"results":[{"id":"file:4711","title":"Budget 2026.md","url":"https://cloud.example.org/index.php/f/4711","provider":"files","kind":"file"},{"id":"url:https://cloud.example.org/index.php/call/abc123","title":"Khaled","url":"https://cloud.example.org/index.php/call/abc123","provider":"talk-conversations","kind":"url","resolvable":false}]}
```

## Désactiver des bundles d'outils

- Variable : `NC_MCP_DISABLED_TOOLS`, noms de bundles séparés par des virgules, lue au
  démarrage.
- Où la définir : comme variable d'environnement de déploiement de l'ExApp, soit dans les
  options de déploiement de la boîte de dialogue d'installation ou de mise à jour, soit en
  ligne de commande :
  `occ app_api:app:register mcp_connector --env "NC_MCP_DISABLED_TOOLS=mail,calendar"`
  (désenregistrer d'abord sur une installation existante ; les connexions des utilisateurs
  sont conservées, le conteneur est recréé). Le journal de démarrage nomme les bundles
  désactivés.
- Par défaut : non définie, tous les bundles sont actifs.
- Exemple : `export NC_MCP_DISABLED_TOOLS=mail,calendar`, utile lorsqu'un second serveur MCP
  propose déjà le courrier et l'agenda et qu'un modèle plus petit confond les deux.
- Bundles et leurs outils :
  - `calendar` : `calendar_list_events`, `calendar_create_event`
  - `chatgpt` : `search`, `fetch`
  - `contacts` : `contacts_search`
  - `context` : `prepare_context`
  - `deck` : `deck_browse`, `deck_create_card`
  - `files` : `files_search`, `files_list`, `files_read`, `files_download`,
    `files_read_as_markdown`, `files_upload`, `files_create_folder` et `files_update`
    (seulement si activé)
  - `mail` : `mail_browse`
  - `notes` : `notes_search`, `notes_read`, `notes_create`
  - `search` : `unified_search`
  - `tables` : `tables_browse`, `tables_create_row`
  - `talk` : `talk_browse`, `talk_send`
  - `tasks` : `tasks_search`, `tasks_read`, `tasks_create` et `tasks_complete`,
    `tasks_update`, `tasks_move` (seulement si activé)
- Un nom inconnu, ou tous les noms à la fois, arrête le serveur au démarrage avec un message
  qui énumère les noms valides.
- Ce n'est pas un contrôle d'accès : `search`, `fetch` et `prepare_context` atteignent toujours
  le contenu d'un bundle désactivé. Pour tenir un contenu à l'écart de l'assistant, utilisez
  les permissions Nextcloud, l'étiquette `kein-ki` ou `NC_MCP_FILES_ROOT`.
- Les connecteurs ChatGPT attendent le bundle `chatgpt` (`search`, `fetch`).
- L'ExApp déclare la variable et consigne au démarrage les bundles désactivés.

## Exclure des dossiers : l'étiquette kein-ki

Un dossier ou un fichier portant l'étiquette collaborative `kein-ki` devient invisible pour l'assistant, avec tout ce qu'il contient.
Vérifier avec `php occ mcp_connector:exclusion:check --admin=<uid>`.
Limite principale : une étiquette au-dessus de la racine d'un partage ne protège pas le dossier partagé chez le destinataire, étiquetez donc le dossier que vous partagez.
Mise en place, toutes les limites et leurs constats : [docs/exclusion.fr.md](docs/exclusion.fr.md).

## Architecture

Un conteneur, une application : le connecteur est une ExApp Nextcloud bâtie
sur FastAPI et le SDK MCP officiel, Streamable HTTP et stdio depuis le même
serveur, et il est son propre serveur d'autorisation OAuth 2.1 avec un pont
vers la connexion Nextcloud. Chaque appel d'outil est une requête HTTP vers
les APIs propres de Nextcloud (WebDAV, CalDAV, CardDAV, OCS et les APIs REST
des applications) au nom de l'utilisateur connecté ; les droits s'appliquent
inchangés, rien n'est indexé ni copié.

## Sécurité

Ce serveur détient des **données privées**, il absorbe du **contenu non fiable** (un courriel
ou un message Talk est écrit par un tiers, et pour un courriel ce tiers n'a même pas besoin
d'un compte sur votre instance), et il a une **sortie**, `talk_send`. Ces trois éléments
ensemble sont ce que Simon Willison appelle la
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), et un modèle de
langage ne sépare pas de façon fiable les données des instructions. C'est pourquoi `talk_send`
se trouve derrière l'interrupteur d'administration `NC_MCP_TALK_SEND`, qui ferme la sortie
pour toute l'instance tandis que la lecture reste intacte, et Mail ajoute de la portée sans
sortie propre, délibérément. Aucune des deux ne rend l'injection de prompt impossible. La
version longue, avec chaque contre-mesure et le reste honnête, se trouve dans
[docs/privacy.md](docs/privacy.md). Chaque limite de ce serveur sur une seule page, dans
l'ordre à appliquer sur des données confidentielles :
[docs/hardening.fr.md](docs/hardening.fr.md). La version systématique, actifs, attaquants et
chaque menace avec le test qui tient sa contre-mesure :
[docs/threat-model.md](docs/threat-model.md) (en anglais). Les interrupteurs se trouvent sous
Paramètres, Administration, Sécurité :

![Paramètres d'administration du MCP Connector](docs/screenshots/admin-settings.png)

## Installation

Référencée dans l'App Store de Nextcloud sous le nom
[MCP Connector](https://apps.nextcloud.com/apps/mcp_connector) et installée comme ExApp :
activer AppAPI, enregistrer un deploy daemon, puis déployer et activer l'application.
Nextcloud 32 à 35. Sur 34.0.3 l'interface de gestion des applications s'en charge, sur les
versions antérieures occ est le chemin fiable. Le déroulé complet avec les commandes exactes
et les pièges qui surviennent vraiment : [docs/exapp-install.md](docs/exapp-install.md).

Depuis la 0.2.0, le serveur fonctionne aussi sans AppAPI. `nc-mcp-oauth` sert le même point
de terminaison, le même serveur d'autorisation et le même écran de consentement pour une
Nextcloud qu'il atteint en HTTPS. Comme aucun en-tête AppAPI n'y nomme le compte derrière le
navigateur, la décision de consentement est confirmée par l'authentification unique OIDC à
laquelle Nextcloud fait déjà confiance. Installation, secrets et exploitation :
[docs/standalone-oauth.md](docs/standalone-oauth.md).

[![MCP Connector dans l'App Store de Nextcloud](docs/screenshots/app-store.png)](https://apps.nextcloud.com/apps/mcp_connector)

## Clients

Claude.ai et ChatGPT se connectent via OAuth avec une seule URL. Claude Desktop, Claude Code,
Cursor et les autres clients locaux lancent le même serveur en stdio, avec un mot de passe
d'application Nextcloud :

```bash
uv tool install nextcloud-mcp-connector

export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

Le même serveur parle Streamable HTTP pour les clients distants, sur `POST /mcp`, où
`NC_MCP_ALLOWED_HOSTS` est en pratique obligatoire. Installation pas à pas, chaque variable
d'environnement et les trois erreurs qui surviennent vraiment :
[docs/client-setup.md](docs/client-setup.md). OAuth pour l'administration :
[docs/oauth-setup.md](docs/oauth-setup.md). Les plateformes d'automatisation sont aussi des
clients, avec une connexion OAuth par personne : [docs/n8n-setup.md](docs/n8n-setup.md).

![Page des connexions avec deux assistants connectés](docs/screenshots/connections-page-v2.png)

## Confidentialité

Chaque appel part vers votre Nextcloud et revient : rien ne tourne en arrière-plan, aucun
résultat n'est mis en cache, aucun index n'est conservé. Dans les modes HTTP, les identifiants
voyagent par requête et ne sont jamais stockés. Les questions que posent les utilisateurs :
[docs/faq.md](docs/faq.md).

## Enterprise

Le journal d'audit fait partie de cette application et non d'un module complémentaire. Activé,
il consigne chaque appel d'outil : le compte pour lequel il s'est exécuté, l'outil, l'heure,
l'application appelante et le résultat, jamais une valeur de paramètre ni une partie d'un
résultat. Il est désactivé par défaut, un administrateur l'active dans les paramètres
d'administration de cette application, et il se lit avec `occ mcp_connector:audit:read`.
Chaque entrée est chaînée par empreinte à la précédente, et `occ mcp_connector:audit:verify`
parcourt les chaînes et indique le premier endroit où l'une d'elles est rompue.

L'authentification via le fournisseur d'identité que votre organisation exploite déjà est
arrivée avec la 0.2.0, dans le déploiement sans AppAPI : la décision de consentement est
confirmée par l'authentification unique OIDC à laquelle Nextcloud fait déjà confiance via
`user_oidc`. Les politiques de groupe restent prévues.

Demande de devis : admin@infranode.dev

## Développement

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest` ne démarre rien et n'a besoin de rien. `uv run pytest -m matrix` démarre le
serveur HTTP comme sous-processus, `uv run pytest -m integration` a besoin du Nextcloud de
test local de `compose.test.yml`.

L'app id, les noms de paquets et le nom du dépôt sont figés, voir
[docs/app-id-freeze.md](docs/app-id-freeze.md).

## Licence

AGPL-3.0-or-later, voir [LICENSE](LICENSE). Dons : [PayPal](https://www.paypal.com/paypalme/KhaledCherifDev)
et [Stripe](https://buy.stripe.com/3cI14n2ke6AbdTPfG22VG00).

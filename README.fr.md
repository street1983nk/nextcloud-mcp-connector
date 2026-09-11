[English](README.md) | [Deutsch](README.de.md) | **Français**

> Le README anglais (README.md) fait foi ; cette traduction est mise à jour ensuite.

# MCP Connector pour Nextcloud

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

- 21 outils répartis sur neuf familles d'applications : fichiers, agenda, notes, Deck,
  contacts, Tables, Talk, Mail et la recherche à l'échelle du cloud
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

- Rien supprimer : aucun outil n'émet de DELETE sur des fichiers, événements, notes, cartes
  ou contacts
- Rien écraser : les écritures sont en création seule, et `files_upload` refuse un chemin
  existant par une erreur claire au lieu de le remplacer
- Aucun déplacement, aucun renommage, aucune modification de partage ni de permission
- Mail est strictement en lecture seule : aucun envoi, aucun brouillon, aucun déplacement,
  aucun marquage, aucune suppression, aucun téléchargement de pièce jointe
- Aucun accès administrateur : le serveur agit comme un utilisateur et hérite exactement de
  ses droits
- Aucune recherche plein texte dans le contenu des fichiers tant qu'une application de
  recherche comme Findling n'est pas installée

C'est une contrainte de conception et non une promesse de bon comportement : un test de
contrat lit les modules et échoue au premier appel destructeur,
[tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py).

## Outils

**read** signifie que l'outil ne fait que lire, **create-only** signifie qu'il peut créer de
nouveaux objets mais ne modifie ni ne supprime jamais ceux qui existent. Le tableau n'est pas
maintenu à la main : un test de contrat lit le registre en cours d'exécution et échoue dès
qu'un nom ou un niveau diverge.

| Tool | Permission | Ce qu'il fait |
|------|------------|---------------|
| `files_search` | read | Fichiers et dossiers par nom via WebDAV search ; le contenu n'est pas indexé |
| `files_list` | read | Les enfants directs d'un dossier, avec taille et date de modification |
| `files_read` | read | Le contenu d'un fichier |
| `files_upload` | create-only | Un nouveau fichier ; un chemin existant est refusé, jamais écrasé |
| `calendar_list_events` | read | Les événements d'une plage de temps explicite, avec un fuseau horaire explicite |
| `calendar_create_event` | create-only | Un nouvel événement ; les événements existants ne sont jamais modifiés |
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
| `fetch` | read | Récupération compatible OpenAI, résout un id vers un fichier, une note, une carte, un événement, un courriel, un message Talk ou un tableau |

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
[docs/privacy.md](docs/privacy.md). Les interrupteurs se trouvent sous Paramètres,
Administration, Sécurité :

![Paramètres d'administration du MCP Connector](docs/screenshots/admin-settings.png)

## Installation

Référencée dans l'App Store de Nextcloud sous le nom
[MCP Connector](https://apps.nextcloud.com/apps/mcp_connector) et installée comme ExApp :
activer AppAPI, enregistrer un deploy daemon, puis déployer et activer l'application.
Nextcloud 32 à 34. Sur 34.0.3 l'interface de gestion des applications s'en charge, sur les
versions antérieures occ est le chemin fiable. Le déroulé complet avec les commandes exactes
et les pièges qui surviennent vraiment : [docs/exapp-install.md](docs/exapp-install.md).

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

![Page des connexions avec deux assistants connectés](docs/screenshots/connections-page.png)

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

Prévus, mais pas encore disponibles : les politiques de groupe et l'authentification via le
fournisseur d'identité que votre organisation exploite déjà.

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

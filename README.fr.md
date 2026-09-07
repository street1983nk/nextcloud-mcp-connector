[English](README.md) | [Deutsch](README.de.md) | **Français**

> Le README anglais (README.md) fait foi ; cette traduction est mise à jour ensuite.

# MCP Connector pour Nextcloud

Un serveur MCP soigneusement sélectionné qui relie votre Nextcloud (fichiers, agenda, notes, deck,
contacts, Tables, Talk et Mail) à des assistants IA tels que Claude, Cursor, ChatGPT ou vos propres
agents.

**Findling + Nextcloud MCP Connector = la couche de récupération de votre propre RAG.**
[Findling](https://apps.nextcloud.com/apps/findling) rend le contenu de vos documents
interrogeable, scans compris, et la 1.0.0 apporte la recherche sémantique. Le connecteur
transmet ces résultats à tout client MCP, avec exactement les droits de l'utilisateur qui
demande. Le modèle, c'est vous qui l'apportez, et aucun contenu ne quitte votre serveur.
Mesuré, pas promis :
[tests/integration/test_content_hit_fidelity.py](tests/integration/test_content_hit_fidelity.py)
prouve qu'un résultat de contenu n'atteint jamais un autre compte.


**Ce serveur ne peut jamais supprimer, écraser ou repartager quoi que ce soit.**

Cette phrase est la contrainte de conception, pas une promesse de bon comportement. Le serveur
n'implémente aucun appel destructeur : pas de DELETE, pas de MOVE, pas d'écrasement, pas de
modification de partage. Les outils d'écriture sont en création seule, et une collision de nom est
traitée par un refus clair plutôt que par un écrasement silencieux.

Deux autres propriétés découlent de la même idée :

- **L'assistant ne voit jamais plus que vous.** Chaque requête s'exécute avec vos propres
  identifiants Nextcloud, si bien que les permissions Nextcloud s'appliquent sans changement.
- **Un ensemble d'outils délibérément restreint.** Les 21 outils sont sélectionnés de façon que ce
  serveur cohabite avec vos autres serveurs MCP, même dans des clients avec une limite stricte du
  nombre d'outils.

Licence : AGPL-3.0-or-later. L'app id, les noms de paquets et le nom du dépôt sont figés, voir
[docs/app-id-freeze.md](docs/app-id-freeze.md).

## Statut

Version 0.1.11. L'application est référencée dans l'App Store de Nextcloud et installable comme
ExApp Nextcloud via AppAPI. Ce qui est en place aujourd'hui, et où chacune de ces affirmations est
consignée :

- Les 21 outils de l'ensemble v1 sont implémentés, et le tableau des outils ci-dessous n'est plus
  maintenu à la main : un test de contrat lit le registre d'outils en direct et échoue si un nom
  ou un niveau de permission du tableau est en désaccord avec lui.
- La connexion OAuth 2.1 est vérifiée de bout en bout face aux deux connecteurs hébergés pour
  lesquels elle a été construite, Claude.ai et ChatGPT, avec l'enregistrement dynamique de client
  et la rotation des refresh tokens. Le parcours et les mesures figurent dans
  [docs/oauth-setup.md](docs/oauth-setup.md).
- Gestion par compte : chaque compte met en pause ou reprend son propre accès MCP et déconnecte
  individuellement chaque assistant connecté sur la page des connexions de cette application, que
  Nextcloud référence sous Paramètres, Sécurité, MCP Connector.
- `prepare_context` regroupe une recherche, la semaine à venir, les conversations Talk en attente
  et les compteurs de courriels non lus en un seul appel, de sorte qu'une question coûte un
  aller-retour au lieu de plusieurs. Chaque source a son propre budget de temps et sa propre
  entrée `degraded` : une source lente raccourcit le paquet et jamais la réponse. Trois plafonds
  gardent la taille prévisible : au plus trois conversations, un aperçu de chat coupé à 200 octets,
  et au plus trois comptes de courriel. Le courriel arrive sous forme de compteur, et c'est tout
  l'intérêt : le paquet standard ne contient ni objet ni contenu de courriel.

Depuis la 0.1.4 : Tables et Talk. Un assistant parcourt les tableaux du compte et ajoute
une ligne à l'un d'eux en nommant les titres de colonnes, il lit les conversations du compte et
l'historique de l'une d'elles, et il envoie un message dans une conversation. La lecture d'une
conversation ne laisse aucune trace : aucun marqueur de lecture n'est déplacé, aucune
notification n'est acquittée et le statut en ligne reste tel quel. Talk est la seule famille où
un assistant peut présenter quelque chose à d'autres personnes : un administrateur peut donc
désactiver cet envoi pour toute l'instance, et un message qui mentionne tout le monde, un groupe
entier ou une équipe entière d'un coup n'est jamais envoyé.

Installation pas à pas pour Claude Desktop, Claude Code et les clients HTTP distants, y compris les
trois erreurs qui surviennent réellement : **[docs/client-setup.md](docs/client-setup.md)**.

### OAuth 2.1

Installé comme ExApp Nextcloud, ce serveur est aussi son propre serveur d'autorisation OAuth 2.1,
conforme à la spécification d'autorisation MCP : enregistrement dynamique de client, PKCE S256,
jetons liés à une audience, rotation des refresh tokens avec détection de réutilisation et
révocation immédiate. Un client tel que Claude.ai ou ChatGPT reçoit une seule URL, connecte
l'utilisateur sur les propres pages de Nextcloud et ne voit jamais de mot de passe ni d'App
password. La connexion apparaît sous Paramètres, Sécurité, Appareils et sessions et peut y être
close.

Depuis la 0.1.3 : une application d'assistant peut
aussi s'identifier par l'adresse d'un document de métadonnées qu'elle publie elle-même, au lieu
de s'enregistrer ici d'abord. C'est la voie que la spécification MCP actuelle préfère, et celle
par laquelle Claude Code se connecte. Les deux voies fonctionnent côte à côte, et un
administrateur peut désactiver l'une ou l'autre.

Ce qu'un administrateur doit régler, ce qu'un utilisateur saisit, et les mesures qui étayent les
deux : **[docs/oauth-setup.md](docs/oauth-setup.md)**.

## Dans l'App Store de Nextcloud

L'application est référencée sous le nom **MCP Connector** :
**[apps.nextcloud.com/apps/mcp_connector](https://apps.nextcloud.com/apps/mcp_connector)**

[![MCP Connector dans l'App Store de Nextcloud](docs/screenshots/app-store.png)](https://apps.nextcloud.com/apps/mcp_connector)

Elle s'installe comme ExApp Nextcloud : activer AppAPI, enregistrer un démon de déploiement,
puis déployer et activer l'application. Sous **Nextcloud 34.0.3**, la gestion des applications
s'en charge : la liste des applications affiche l'ExApp avec son démon de déploiement, le
bouton d'installation d'une ExApp s'appelle « Deploy and enable », et « Remove » se trouve dans
le menu d'actions d'une ExApp désactivée (mesuré sur 34.0.3.2 le 2026-08-20). Sous 34.0.2 et
antérieur, la gestion n'affiche aucune ExApp, et occ reste la voie fiable sur toutes les
versions. Le parcours complet, avec les commandes occ exactes et les pièges réellement
rencontrés, se trouve dans **[docs/exapp-install.md](docs/exapp-install.md)** (en anglais).

Après l'installation, l'application enregistre ses réglages sous Paramètres, Administration,
Sécurité :

![Réglages d'administration du MCP Connector](docs/screenshots/admin-settings.png)

Chaque compte gère ses propres connexions sur la page des connexions de l'application, que
Nextcloud référence sous Paramètres, Sécurité, MCP Connector :

![Page des connexions avec deux assistants connectés](docs/screenshots/connections-page.png)

## FAQ

**Mon administrateur a installé cette application. Puis-je la désactiver pour moi ?**

Oui, et vous n'avez pas besoin de votre administrateur pour cela. Rien ne tourne en arrière-plan :
le connecteur n'agit qu'à la demande d'un assistant que vous avez connecté vous-même, il n'y a ni
tâche planifiée, ni indexation, ni télémétrie. Votre propre compte dispose d'un interrupteur sur
la page des connexions de cette application, que Nextcloud référence sous Paramètres, Sécurité,
MCP Connector, et chaque assistant connecté peut être déconnecté séparément, ce qui rend son mot
de passe d'application Nextcloud à Nextcloud.

La réponse complète, avec la frontière entre ce que cette application contrôle et ce que décide le
fournisseur de votre assistant : **[docs/faq.md](docs/faq.md)** (en anglais).

## Démarrage rapide (stdio)

Vous avez besoin d'un App password Nextcloud, pas de votre mot de passe de connexion. Créez-en un
dans Nextcloud sous Paramètres, Sécurité, Appareils et sessions.

```bash
uv tool install nextcloud-mcp-connector   # or: uv run nc-mcp inside a checkout

export NC_MCP_URL=https://cloud.example.com
export NC_MCP_USER=alice
export NC_MCP_APP_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx

nc-mcp
```

Configuration du client, par exemple pour Claude Desktop ou Cursor :

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

## Mode HTTP

Le même serveur parle également Streamable HTTP pour les clients distants :

```bash
export NC_MCP_URL=https://cloud.example.com
export NC_MCP_ALLOWED_HOSTS=mcp.example.com
uv run uvicorn mcp_connector.entry_http:app --host 127.0.0.1 --port 8765
```

Le point de terminaison MCP est `POST /mcp`, et `GET /health` répond
`{"status":"ok","version":"..."}` sans authentification. Un seul point de terminaison sert les deux
générations du protocole : les clients sur la spécification actuelle et les clients bâtis sur le MCP
SDK 1.x sont routés selon la version de protocole de leur requête, et un redémarrage ne peut pas
interrompre une conversation car le serveur ne conserve aucun état de session.

Les identifiants ne sont pas lus depuis l'environnement dans ce mode. Ils voyagent par requête dans
l'en-tête `Authorization` (Basic, utilisateur et App password) et sont transmis sans changement à
Nextcloud, qui les authentifie. Le serveur ne traite jamais l'en-tête comme une revendication
d'identité qui lui serait propre, et il ne stocke rien, si bien qu'un seul déploiement peut servir
plusieurs utilisateurs sans stockage d'identifiants.

Pour les déploiements mono-utilisateur, un Bearer token statique est disponible à la place :
définissez `NC_MCP_STATIC_BEARER`, et le compte Nextcloud est pris depuis l'environnement comme en
mode stdio. Les deux modes HTTP sont mutuellement exclusifs.

`NC_MCP_ALLOWED_HOSTS` n'est pas optionnel en pratique. Sans lui, la couche de transport n'accepte
que `Host: localhost` et `Host: 127.0.0.1` et répond à toute autre requête par `421 Misdirected
Request` avant qu'aucun code MCP ne s'exécute. Notez qu'il s'agit de l'en-tête `Host` des requêtes
entrantes, pas de l'adresse d'écoute : `--host 0.0.0.0` n'ouvre à personne.

## Variables d'environnement

| Variable | Mode | Requis | Rôle |
|----------|------|----------|---------|
| `NC_MCP_URL` | all | oui | URL de base de votre Nextcloud, y compris un sous-chemin si vous en utilisez un |
| `NC_MCP_USER` | stdio, static bearer | oui | Identifiant utilisateur Nextcloud |
| `NC_MCP_APP_PASSWORD` | stdio, static bearer | oui | App password depuis Paramètres, Sécurité, Appareils et sessions |
| `NC_MCP_ALLOWED_HOSTS` | HTTP | oui en pratique | Liste d'autorisation d'en-têtes `Host` de ce serveur, séparés par des virgules ; un joker de port est ajouté par nom |
| `NC_MCP_STATIC_BEARER` | HTTP | non | Bearer token statique pour les déploiements mono-utilisateur ; sans lui, les clients s'authentifient par requête |
| `NC_MCP_DISABLE_DNS_REBINDING_PROTECTION` | HTTP | non | À mettre à `true` uniquement derrière un proxy qui contrôle l'en-tête `Host` |
| `NC_MCP_PUBLIC_URL` | static bearer, ExApp | oui pour OAuth | URL publique de ce serveur. En mode ExApp, c'est l'émetteur (issuer) du serveur d'autorisation et la ressource du document de ressource protégée, si bien qu'OAuth ne fonctionne pas sans elle |
| `NC_MCP_OAUTH_DCR` | ExApp | non | Enregistrement dynamique de client, activé sauf s'il est désactivé |
| `NC_MCP_OAUTH_CIMD` | ExApp | non | Un client peut s'identifier par l'adresse d'un document de métadonnées qu'il publie lui-même, activé sauf s'il est désactivé ; désactiver l'enregistrement automatique ferme cette voie avec lui |
| `NC_MCP_OAUTH_ALLOWLIST_ONLY` | ExApp | non | Seuls les clients listés peuvent s'autoriser ; une liste vide ferme alors la porte à tout le monde |
| `NC_MCP_OAUTH_ALLOWED_CLIENTS` | ExApp | non | Ids de client ou redirect URIs séparés par des virgules, lus uniquement quand l'allowlist est active |
| `NC_MCP_TALK_SEND` | all | non | Le canal Talk sortant de cette application, activé sauf s'il est mis à off. Avec off, aucun assistant ne peut envoyer de message Talk via ce connecteur, quels que soient les droits du compte dans Talk lui-même ; la lecture des conversations et de leur historique n'est pas affectée. En mode ExApp, le formulaire d'administration écrit cette valeur |

Aucun identifiant n'est jamais journalisé, dans aucun mode.

## Outils

Niveaux de permission : **read** signifie que l'outil ne fait que lire, **create-only** signifie que
l'outil peut créer de nouveaux objets mais ne peut jamais modifier ni supprimer ceux qui existent.

| Tool | Permission | Ce qu'il fait |
|------|------------|--------------|
| `files_search` | read | Recherche fichiers et dossiers par nom via WebDAV search ; le contenu n'est pas indexé |
| `files_list` | read | Liste les enfants directs d'un dossier, avec tailles et dates de modification |
| `files_read` | read | Lit le contenu d'un seul fichier |
| `files_upload` | create-only | Téléverse un nouveau fichier ; un chemin existant est refusé, jamais écrasé |
| `calendar_list_events` | read | Liste les événements dans une plage de temps explicite, avec un fuseau horaire explicite |
| `calendar_create_event` | create-only | Crée un nouvel événement ; les événements existants ne sont jamais modifiés |
| `notes_search` | read | Trouve des notes par titre et contenu via le fournisseur de recherche de notes Nextcloud |
| `notes_read` | read | Lit une seule note |
| `notes_create` | create-only | Crée une nouvelle note ; les notes existantes ne sont jamais modifiées |
| `deck_browse` | read | Parcourt les tableaux, piles et cartes de Deck |
| `deck_create_card` | create-only | Crée une nouvelle carte dans une pile ; les cartes existantes ne sont jamais modifiées |
| `tables_browse` | read | Parcourt Tables : les tables, les colonnes d'une table ou ses lignes |
| `tables_create_row` | create-only | Ajoute une ligne désignée par les titres de colonnes ; les lignes existantes ne sont jamais modifiées |
| `talk_browse` | read | Parcourt Talk : les conversations de ce compte, ou l'historique de l'une d'elles |
| `talk_send` | create-only | Envoie un message dans une conversation ; un message n'est jamais modifié ni supprimé, et une administratrice peut désactiver l'envoi pour toute l'instance |
| `mail_browse` | read | Parcourt Mail : les comptes de cet utilisateur, les boîtes aux lettres de l'un d'eux, ou les en-têtes de messages de l'une d'elles ; strictement en lecture seule, aucun moyen d'envoyer, de rédiger un brouillon, de déplacer, de marquer ou de supprimer un courriel |
| `contacts_search` | read | Recherche des contacts dans les carnets d'adresses |
| `unified_search` | read | Interroge la recherche unifiée de Nextcloud à travers les fournisseurs, en respectant les permissions |
| `prepare_context` | read | Regroupe fichiers, notes et cartes correspondants avec la semaine d'événements à venir, les conversations Talk en attente et les compteurs de courriels non lus pour une même question |
| `search` | read | Point d'entrée de recherche compatible OpenAI, délègue à la recherche unifiée |
| `fetch` | read | Point d'entrée de récupération compatible OpenAI, résout un id vers un fichier, une note, une carte, un événement, un courriel, un message Talk ou un tableau |

`search` et `fetch` existent parce que le profil de connecteur ChatGPT exige exactement ces deux noms
et schémas. Ce sont de fines enveloppes autour des outils ci-dessus, pas une seconde implémentation.

### Fichiers : ce que la recherche met réellement en correspondance

`files_search` utilise WebDAV search, qui met en correspondance des **noms**, pas le contenu des
fichiers. Un mot qui n'apparaît qu'à l'intérieur d'un document ne produit aucun résultat, et c'est
le comportement du protocole, pas un défaut de ce serveur. Chaque réponse de recherche porte donc la
même note :

```json
{"query":"budget","folder":"/","count":1,"items":[{"path":"/Docs/budget-2026.md","name":"budget-2026.md","kind":"file","size":2048,"content_type":"text/markdown","modified":"Thu, 14 Aug 2026 10:00:00 GMT","id":"file:4711"}],"note":"matched on names only; contents are not indexed"}
```

La recherche en texte intégral nécessiterait une application Nextcloud installée séparément, si bien
que la réponse honnête est la note ci-dessus plutôt qu'un résultat vide silencieux.

`files_list` renvoie les enfants directs d'un dossier, les dossiers d'abord puis les noms. Le dossier
lui-même ne fait jamais partie de sa propre liste, et un chemin qui pointe vers un fichier reçoit une
explication au lieu d'une liste vide.

### Listes longues : des handles de curseur plutôt que des sessions

Une liste qui a dû s'arrêter prématurément le signale et remet un handle :

```json
{"items": ["..."], "truncated": true, "next": "eyJmIjoiLyIsIm8iOjI1LCJxIjoiYnVkZ2V0In0"}
```

Renvoyez cette valeur comme paramètre `cursor` pour continuer. Le handle est du base64url de JSON
compact et contient toute la position, si bien que le serveur ne conserve aucune session : un handle
fonctionne encore après un redémarrage du serveur, et il fonctionne face à un autre processus du même
serveur. Il n'est délibérément pas signé, car il ne porte ni secret ni permission. Les identifiants
proviennent du canal d'authentification à chaque appel, si bien qu'un handle modifié ne peut que
paginer différemment à travers les propres données de l'appelant. Un handle issu d'une autre requête
est refusé plutôt que de renvoyer discrètement la mauvaise page.

### Heures de l'agenda

CalDAV est le seul endroit où une petite erreur de temps produit une réponse fausse mais assurée, si
bien que les outils d'agenda sont explicites à ce sujet :

- `start` et `end` sont requis et doivent porter un fuseau, par exemple `2026-09-01T00:00:00+02:00`
  ou `2026-09-01T00:00:00Z`. Une valeur sans fuseau est refusée au lieu d'être devinée.
- Les événements récurrents sont dépliés par Nextcloud lui-même, si bien que chaque occurrence
  revient sous forme de temps absolu. Le paramètre optionnel `timezone` (un nom IANA tel que
  `Europe/Berlin`) change seulement la façon dont la réponse est écrite, jamais quels événements elle
  contient.
- Les événements sur la journée entière sont des dates sans heure et sont marqués par `all_day`. Leur
  date de fin est exclusive, telle que la définit la RFC 5545 : un événement le 24 octobre se termine
  le 25 octobre.
- `calendar_create_event` relit une fois l'événement créé et rapporte les heures que le serveur a
  stockées, pas celles qui lui ont été demandées.

### Contacts

`contacts_search` est en lecture seule, et le reste dans cette version : il n'y a aucun chemin
d'écriture CardDAV du tout.

- Le terme de recherche est mis en correspondance par Nextcloud lui-même avec le nom complet et les
  adresses mail d'une fiche, insensible à la casse et aux accents. Un numéro de téléphone est renvoyé
  mais pas recherché.
- Chaque carnet d'adresses du compte est interrogé en même temps. Celui qui échoue est nommé sous
  `degraded`, si bien qu'une réponse partielle est visiblement partielle.
- Les deux collections que Nextcloud génère pour chaque compte sont écartées : l'annuaire des comptes
  de l'instance (`z-server-generated--system`, affiché comme "Accounts") et la liste des "contacts
  récents". Aucune n'est un carnet d'adresses que l'utilisateur tient, et une recherche par nom ne
  devrait pas distribuer l'annuaire de toute une organisation comme effet de bord.
- Un compte sans carnet d'adresses propre reçoit une erreur qui nomme
  `occ dav:create-addressbook <user> contacts`, jamais un résultat vide : "aucun carnet d'adresses"
  et "aucun contact correspondant" sont des réponses différentes.

### Deck

Deck est un seul outil de navigation avec un niveau, pas un outil par niveau :

```json
{"level":"cards","count":2,"results":[{"id":"card:2:11:101","title":"Deck-Client bauen","stack":"To Do","url":"https://cloud.example.org/index.php/apps/deck/card/101"}]}
```

- `deck_browse(level="boards")` liste les tableaux avec `can_edit`, `level="stacks"` a besoin d'un
  `board_id` et rapporte combien de cartes contient une pile, `level="cards"` renvoie les cartes
  elles-mêmes. Un niveau invalide est rejeté par le schéma, et un `board_id` manquant nomme le
  paramètre au lieu d'en deviner un.
- `level="cards"` coûte exactement **une** requête HTTP par tableau, car Nextcloud envoie déjà les
  cartes à l'intérieur de la réponse des piles. Un test compte les requêtes, face au mock et face à
  une instance réelle.
- Un id de carte est la forme longue canonique `card:<board>:<stack>:<card>`, qui adresse la carte à
  travers l'API publique de Deck sans recherche préalable.
- `deck_create_card` ne fait que créer. Il n'y a aucune mise à jour, aucune suppression et aucune
  création de tableau ou de pile nulle part dans le chemin de code de Deck. Un titre de plus de 255
  caractères ou une date d'échéance qui n'est pas ISO-8601 est refusé avant la requête, et un compte
  dont le Nextcloud interdit la création de tableau est vérifié au regard des propres permissions du
  tableau, si bien qu'un tableau en lecture seule est expliqué au lieu de recevoir une réponse 403.

### Mail

Mail est un seul outil de parcours à trois niveaux, avec une propriété stricte : il lit, et il ne
sait rien faire d'autre.

- `mail_browse(level="accounts")` liste les comptes de messagerie de l'utilisateur connecté avec leur
  adresse, `level="mailboxes"` exige un `account_id` et liste les boîtes aux lettres de ce compte
  avec leur nombre de messages non lus et leur rôle IMAP, et `level="messages"` exige un `mailbox_id`
  et renvoie les en-têtes de messages, les plus récents d'abord. Aucun des deux identifiants n'est
  deviné : il n'y a ni compte par défaut ni "première boîte", parce qu'une réponse qui a l'air juste
  au sujet du courrier de quelqu'un d'autre serait l'erreur la plus coûteuse de cette famille. Une
  fenêtre compte 20 en-têtes si aucune plus grande n'est demandée, 50 au maximum, et une liste qui a
  dû s'arrêter remet un handle `next` comme toute autre liste longue de ce serveur.
- **Le texte complet d'un seul message** passe par le `fetch` existant, avec l'identifiant
  `mail:<databaseId>` que porte chaque en-tête, et non par un second outil. Le corps est toujours
  converti en texte, que le message ait été écrit en HTML ou non, et il est coupé à 32 Kio avec un
  marqueur qui ne promet aucune suite : un courriel n'a pas de décalage à partir duquel continuer. À
  côté du texte, et délibérément jamais dedans, `metadata` porte ce que Nextcloud sait lui-même de
  l'expéditeur : `sender_trusted`, `dkim`, `signature`, `encrypted`, `phishing_warning` et
  `phishing_checks`. Un `dkim` égal à `unchecked` signifie "aucune vérification n'a été faite" et non
  "la signature est invalide", et le même mot couvre un courriel sans aucune signature : ni l'un ni
  l'autre n'est un expéditeur vérifié, et tous deux mènent à la même étape suivante.
- **La grammaire de filtre**, exactement telle qu'elle est testée. Les conditions s'écrivent
  `type:value` et se séparent par des espaces :

  | Type | Prend | Exemple |
  |------|-------|---------|
  | `is:` | `unread`, `read`, `starred`, `answered`, `important` | `is:unread` |
  | `not:` | les mêmes cinq valeurs | `not:answered` |
  | `from:` | une adresse ou une partie d'adresse | `from:facture@example.org` |
  | `subject:` | un mot de l'objet | `subject:facture` |
  | `tags:` | l'identifiant **numérique** de l'étiquette, jamais le libellé IMAP | `tags:1` |
  | `start:` | des **secondes Unix** | `start:1756000000` |
  | `end:` | des **secondes Unix** | `end:1756600000` |

  Deux propriétés de l'analyseur de l'application Mail font partie de la grammaire, parce qu'un
  appelant ne peut pas les deviner. Le filtre est découpé sur les **espaces**, donc une valeur qui en
  contient un doit être encodée en pourcentage : `subject:facture%20mai` est la seule écriture qui
  filtre sur les deux mots, et `subject:facture mai` filtre sur `facture` et laisse tomber `mai` sans
  le dire. Et chaque jeton est découpé à son **premier** deux-points, le reste disparaissant, donc un
  deux-points dans une valeur doit s'écrire `%3A`. `start:` et `end:` sont comparés à une colonne
  entière, ils prennent donc des secondes Unix et rien d'autre : `start:2026-08-01` élimine tous les
  messages au lieu d'échouer, et `start:2026-08-01T10:00:00Z` serait en plus coupé à son premier
  deux-points, raison pour laquelle un horodatage ISO est refusé ici.

  Un type que ce connecteur ne connaît pas est **refusé**, et non écarté. L'application Mail l'écarte
  en silence et répond avec la liste non filtrée, si bien que `is:ungelesen` ressemblerait à un
  résultat de filtre correct et qu'un modèle ne peut pas voir la différence. Une erreur coûte un
  aller-retour, une réponse fausse qui a l'air juste coûte la conversation.
- **Ce qui manque délibérément.** Il n'y a pas de filtre `body:` : c'est la seule condition qui quitte
  la base de données et cherche via IMAP, elle coûte donc un aller-retour vers le serveur de
  messagerie de l'utilisateur à chaque appel. Les pièces jointes ne sont jamais téléchargées. Et il
  n'existe aucun chemin d'écriture, voir la section correspondante plus bas.

### Recherche à l'échelle du cloud

`unified_search` interroge chaque fournisseur de recherche que l'instance offre, en même temps :

```json
{"query":"budget","count":2,"results":[{"id":"file:4711","title":"Budget 2026.md","subline":"in Dokumente","url":"https://cloud.example.org/index.php/f/4711","provider":"files","kind":"file"},{"id":"url:https://cloud.example.org/index.php/call/abc123","title":"Khaled","url":"https://cloud.example.org/index.php/call/abc123","provider":"talk-conversations","kind":"url","resolvable":false}],"note":"matched on names and metadata; file contents are not indexed","degraded":[{"provider":"search-deck-card-board","reason":"The provider did not answer within 15 seconds."}]}
```

- La liste des fournisseurs provient de Nextcloud à chaque appel et n'est jamais codée en dur, car
  elle suit les applications installées. Une application activée il y a une minute est interrogeable
  sans redémarrage.
- Chaque fournisseur reçoit son propre délai d'expiration. Celui qui échoue ou se bloque est nommé
  sous `degraded` avec un motif, si bien qu'une réponse partielle est toujours visiblement partielle,
  jamais une liste discrètement plus courte.
- Les permissions sont l'affaire de Nextcloud : chaque fournisseur s'exécute en tant qu'utilisateur
  authentifié, et ce serveur ne tient aucun index et ne met aucun résultat en cache.
- Les résultats de Files, Notes et Deck portent un id que les outils de lecture comprennent. Tout le
  reste reçoit un id `url:` et `resolvable: false`, car un id inventé résoudrait vers le mauvais
  objet. Le fournisseur de Deck ne rapporte qu'un id de carte, si bien que sa forme courte
  `card:<cardId>` est marquée de la même façon.
- `providers` restreint la diffusion à un sous-ensemble séparé par des virgules, par exemple
  `files,notes`. Un nom que l'instance ne connaît pas est rapporté sous `degraded` au lieu d'être
  silencieusement ignoré.
- `limit` s'applique par fournisseur et est de nouveau plafonné par Nextcloud lui-même. Si un
  fournisseur pagine, son curseur revient sous `cursors`.

### Profil de connecteur ChatGPT

`search` et `fetch` sont les deux noms que le connecteur OpenAI recherche. Leurs paramètres sont
`query` et `id`, leurs noms de champs sont fixes, et ce sont les deux seuls outils de ce serveur à
livrer un output schema, car ChatGPT lit la charge utile comme contenu structuré :

```json
{"results":[{"id":"file:4711","title":"Budget 2026.md","url":"https://cloud.example.org/index.php/f/4711","text":"in Dokumente"}]}
```

```json
{"id":"file:4711","title":"Budget 2026.md","text":"# Budget 2026 ...","url":"https://cloud.example.org/index.php/f/4711","metadata":{"kind":"file","path":"/Dokumente/Budget 2026.md","content_type":"text/markdown"}}
```

- `search` n'ajoute aucune seconde recherche. Il appelle `unified_search` et renomme les champs, si
  bien que les deux outils répondent à la même question de la même façon.
- Chaque résultat porte une URL absolue et non vide sur l'instance configurée. ChatGPT ne crée des
  métadonnées de citation que tant que `url` est une chaîne non vide, si bien qu'une URL vide ferait
  discrètement disparaître la source.
- `fetch` résout les sept types d'id que les outils de lecture comprennent : `file:<fileid>`
  (recherché par une seule WebDAV search sur `oc:fileid`), `note:<id>`,
  `card:<board>:<stack>:<card>` y compris la forme courte `card:<cardId>` du fournisseur de recherche
  Deck, `event:<calendar>:<object>`, `mail:<databaseId>` (le texte complet d'un seul message,
  coupé à 32 Kio, la coupe étant marquée), `message:<token>:<messageId>` (un seul message Talk, lu
  par la même route de contexte qui ne laisse aucune trace ; le message doit être lisible dans cette
  conversation, sinon la réponse est un refus et jamais un message voisin) et `table:<tableId>` (le
  titre, le nombre de lignes et les premières lignes d'un tableau ; une vue n'est pas un tableau et
  reste une URL).
- Un résultat de recherche venant de Mail reste un id `url:` bien que la route du texte complet
  existe, et c'est une mesure et non un oubli : une entrée de recherche de l'application Mail porte
  un lien profond avec un identifiant de message RFC, et sa résolution vers le `databaseId` dont
  cette route a besoin n'est pas mesurée. Un id juste la plupart du temps est, le reste du temps,
  une réponse sur le courrier de quelqu'un d'autre.
- Un id `url:` reçoit une réponse honnête : ce serveur ne requête jamais une URL issue d'un résultat
  de recherche, et il le dit au lieu d'inventer du contenu. Un préfixe inconnu est refusé avec la
  liste de ceux qui sont valides, car résoudre un message de chat comme une note est pire qu'une
  erreur.
- Un fichier long est coupé à la même limite que `files_read`. La coupe est marquée à l'intérieur de
  `text` et de nouveau dans `metadata`, avec le décalage à partir duquel continuer.

### Applications optionnelles

Notes, Deck, Tables, Talk et Mail sont des applications Nextcloud optionnelles, dix outils en tout. La
liste des outils est la même partout : elle ne dépend jamais des applications qu'une instance possède,
si bien qu'elle reste mise en cache et prévisible pour chaque client. Si une application manque,
l'outil le dit en une phrase et nomme une alternative, par exemple "The Notes app is not installed on
this Nextcloud.", "The Tables app is not enabled on this Nextcloud.", "The Talk app is not available on
this Nextcloud." ou "The Mail app is not available on this Nextcloud." Les agendas et les contacts
n'ont besoin d'aucune application : CalDAV et CardDAV font partie du cœur de Nextcloud.

Mail est détectée autrement que les quatre autres, et la raison ne vient pas de nous : l'application
Mail ne publie aucune entrée de capacités, il n'y a donc rien à chercher dans le document de capacités.
Ce serveur interroge alors la navigation de l'utilisateur connecté, qui liste les applications que ce
compte peut réellement ouvrir. Cela coûte une requête supplémentaire par fenêtre de cache, et
uniquement lors d'un appel à Mail.

## Ce que ce serveur ne peut pas faire

- **Aucune suppression.** Aucun outil n'émet de DELETE contre des fichiers, événements, notes, cartes
  ou contacts.
- **Aucun écrasement.** Les écritures sont en création seule. `files_upload` refuse un chemin cible
  existant avec une erreur claire au lieu de le remplacer, et les outils de création ne touchent
  jamais un objet existant.
- **Aucun déplacement ni renommage.** MOVE et COPY ne sont pas implémentés.
- **Aucune modification de partage.** Le serveur ne crée, ne modifie ni ne supprime de partages, et
  il ne change jamais les permissions.
- **Aucun accès administrateur.** Le serveur agit comme un utilisateur avec un App password et hérite
  exactement des permissions de cet utilisateur.
- **Aucune recherche en texte intégral dans le contenu des fichiers** à moins que l'application
  Nextcloud Full text search ne soit installée et configurée. Sans elle, la recherche de fichiers met
  en correspondance les noms et les métadonnées.
- **Aucune tâche d'arrière-plan, aucune synchronisation, aucune copie locale de vos données.** Chaque
  appel va vers votre Nextcloud et revient.
- **Aucun envoi de courriel.** Aucun outil n'envoie de courriel, ne crée de brouillon, ne déplace de
  message, ne pose ni ne retire de marqueur et ne supprime quoi que ce soit, et la route des pièces
  jointes de l'application Mail n'est jamais appelée. Ce qui tient cette phrase est un test de
  contrat : il lit les deux modules Mail de ce serveur et affirme qu'aucun appel d'écriture ne s'y
  trouve, face à la liste des routes que l'application Mail offre pour exactement ces actions.

### La chaîne que ce serveur possède, et l'interrupteur qui la brise

Lire le courrier complète une combinaison qu'il vaut mieux nommer que décrire. Ce serveur a accès à des
**données privées** (fichiers, agenda, notes, contacts, Tables et désormais le courrier), il absorbe du
**contenu non fiable** (un courriel et un message Talk sont écrits par un tiers, et pour un courriel ce
tiers n'a même pas besoin d'un compte sur votre instance), et il a une **sortie** : `talk_send`, le
seul outil qui place un message directement devant d'autres personnes, et derrière lui les écritures
en création seule, qui peuvent laisser un fichier, une carte ou une ligne dans un conteneur partagé
avec d'autres. Ces trois éléments ensemble sont ce que Simon Willison appelle la
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), et un modèle de langage
ne sépare pas de façon fiable les données des instructions : un courriel peut donc porter une phrase
destinée au modèle, et la réponse peut prendre le chemin de la sortie.

Deux choses s'y opposent ici. `talk_send` se trouve derrière l'interrupteur d'administration
`NC_MCP_TALK_SEND`, qui ferme le canal de message direct pour toute l'instance tandis que la lecture
reste intacte ; les écritures en création seule restent ouvertes, si bien qu'un opérateur qui veut
fermer chaque chemin vérifie aussi quels dossiers, tableaux et tables les comptes connectés
partagent. Et **Mail est en lecture seule** : cette famille ajoute de la portée et, délibérément,
aucune sortie propre. Aucune des deux ne rend l'injection de prompt impossible. La version longue,
avec chaque contre-mesure et le reste honnête, se trouve dans [docs/privacy.md](docs/privacy.md),
section "The chain that mail closes".

## Limitations connues

Des choses qui ne sont pas des défauts mais qui vous surprendront une fois. Chacune est un compromis
délibéré, et chacune est visible dans la réponse que donne l'outil plutôt que cachée derrière un
résultat vide.

| Limitation | Ce que vous voyez | Que faire |
|------------|--------------|------------|
| **La recherche met en correspondance les noms, pas le contenu** | Chaque réponse de recherche porte `"note":"matched on names only; contents are not indexed"` | Installer et configurer l'application Nextcloud Full text search, ou rechercher par nom de fichier |
| **Un compte créé avec `occ user:add` n'a pas d'agenda** | `calendar_list_events` renvoie une erreur qui nomme l'agenda manquant | `occ dav:create-calendar <user> personal`, ou se connecter une fois à Nextcloud par l'interface web, ce qui le crée |
| **Il en va de même pour le carnet d'adresses** | `contacts_search` nomme la solution au lieu de ne rien renvoyer | `occ dav:create-addressbook <user> contacts` |
| **Notes, Deck, Tables, Talk et Mail sont des applications optionnelles** | Les outils restent dans `tools/list` partout et répondent "The Notes app is not installed on this Nextcloud.", "The Tables app is not enabled on this Nextcloud.", "The Talk app is not available on this Nextcloud." ou "The Mail app is not available on this Nextcloud." | Installer l'application, ou ignorer ces dix outils |
| **Deux courriels de la même seconde d'envoi peuvent tomber de part et d'autre d'une limite de page** | La pagination de l'application Mail compare l'heure d'envoi de façon stricte : de deux messages portant la même seconde, le second manque sur la page suivante, définitivement | Demander un `limit` plus grand, ce qui rend la limite plus rare. Cette limite appartient à l'application, et ce serveur ne la corrige pas en silence : une correction de notre part serait une seconde vérité sur l'ordre, et deux appelants avec la même fenêtre verraient des listes différentes |
| **Aucune recherche en texte intégral dans le corps des courriels** | Il n'y a pas de filtre `body:`, et la grammaire le refuse comme tout autre type inconnu | Utiliser la recherche de l'application Mail elle-même. `body:` y existe, mais il quitte la base de données et cherche via IMAP, ce qui coûte un aller-retour vers le serveur de messagerie de l'utilisateur à chaque appel |
| **Une boîte aux lettres jamais synchronisée et un serveur de messagerie injoignable** | Les deux répondent par une erreur dont la phrase désigne le compte dans l'application Mail, pas Nextcloud | Ouvrir une fois le compte dans l'application Mail et le laisser se synchroniser, ou réparer le compte là-bas. Aucun des deux cas n'est un problème Nextcloud, et aucun n'est traité par une liste vide |
| **Rien ne peut être supprimé ni écrasé** | `files_upload` refuse un chemin existant avec un conflit, et il n'y a aucun outil de mise à jour ou de suppression du tout | Choisir un autre nom. C'est la contrainte de conception, pas une fonctionnalité manquante |
| **Aucune session, donc aucun état de pagination côté serveur** | Une liste longue remet un handle `next` que vous passez de nouveau | Rien. Le handle survit à un redémarrage, ce qui est le but |
| **Les agendas ont besoin d'une fenêtre de temps explicite avec un fuseau** | Un `start` ou `end` sans fuseau est refusé | Envoyer `2026-09-01T00:00:00+02:00` ou `...Z`. Un fuseau deviné est une réponse fausse mais assurée |
| **Une seule IP pour de nombreux utilisateurs déclenche la protection anti-force brute** | `429` après un mauvais App password, pour tout le monde derrière le même déploiement | Attendre et utiliser un App password correct ; voir la section dépannage dans l'installation du client |
| **Toutes les applications d'assistant ne peuvent pas terminer une connexion OAuth** | Une application qui demande à être renvoyée vers une adresse de son propre schéma, Cursor par exemple, est refusée à la connexion, et la page nomme la voie qui fonctionne | Utiliser un App password sur le même point de terminaison `/exapps/mcp_connector/mcp` ; le mode ExApp accepte les deux, voir [docs/client-setup.md](docs/client-setup.md) |

La phase 2 a rendu le serveur installable comme ExApp Nextcloud via AppAPI, chaque requête
s'exécutant sous la propre identité de l'utilisateur appelant. Trois documents en rendent compte,
ainsi que des deux spikes dont elle dépendait :

- [docs/exapp-install.md](docs/exapp-install.md) : installation de l'application comme ExApp sur la
  topologie HaRP, les preuves, les pièges connus, et le passage de relais vers la phase 5 avec
  Nextcloud AIO.
- [docs/spike-discovery.md](docs/spike-discovery.md) : la décision de découverte pour la topologie
  OAuth de la phase 3, avec la matrice mesurée et le repli sur le reverse proxy.
- [docs/spike-dav.md](docs/spike-dav.md) : le résultat de l'impersonation DAV, à savoir que les six
  familles d'API s'exécutent sous un seul mode d'impersonation, si bien qu'il n'y a pas de séparation
  de fournisseur par famille.

## Enterprise

Le journal d'audit fait partie de cette application et non d'un module complémentaire. Activé, il
consigne chaque appel d'outil : le compte pour lequel il s'est exécuté, l'outil, l'heure,
l'application appelante et le résultat, jamais une valeur de paramètre ni une partie d'un
résultat. Il est désactivé par défaut, un administrateur l'active dans les paramètres
d'administration de cette application, et il se lit avec `occ mcp_connector:audit:read`. Chaque
entrée est chaînée par empreinte à la précédente, et `occ mcp_connector:audit:verify` parcourt
les chaînes et indique le premier endroit où l'une d'elles est rompue.

Deux choses sont prévues comme module commercial : les politiques de groupe et l'authentification
via le fournisseur d'identité que votre organisation exploite déjà. Nous nous tenons à la
disposition de votre organisation pour l'évaluation et le déploiement : admin@infranode.dev

## Développement

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest` ne démarre rien et n'a besoin de rien. Les deux couches plus lourdes sont
optionnelles (opt-in) :

- `uv run pytest -m matrix` démarre le serveur HTTP comme sous-processus et vérifie qu'un client
  actuel et un client sur MCP SDK 1.29 sont tous deux servis depuis le même point de terminaison, et
  que la conversation survit à un redémarrage. Il n'a besoin d'aucun Nextcloud.
- `uv run pytest -m integration` a besoin du Nextcloud de test local de `compose.test.yml`.

## Licence

AGPL-3.0-or-later, voir [LICENSE](LICENSE).

# Tenir des dossiers à l'écart de l'assistant : l'étiquette kein-ki

**Langues :** [English](exclusion.md) | [Deutsch](exclusion.de.md) | Français

Un dossier ou un fichier qui porte l'étiquette collaborative `kein-ki` est invisible pour
l'assistant, tout comme tout ce qui se trouve en dessous. La comparaison ignore la casse et les
espaces autour, `Kein-KI` compte donc aussi, mais une autre graphie comme `Kein KI` ou `keinki`
ne compte pas. L'étiquette est la liste : il n'y a pas de seconde liste de dossiers dans les
paramètres ni d'interrupteur d'administration qui désactive le filtre ; s'il n'existe aucune
étiquette `kein-ki`, rien n'est filtré
([26-CONTEXT.md, D-26-01 et D-26-02](../.planning/phases/26-guard-kern/26-CONTEXT.md)).

Cette page décrit les deux modes de fonctionnement de l'étiquette, la mise en place avec occ, la
commande de vérification et chaque limite mesurée ou décidée. Chaque commande ci-dessous a été
exécutée contre Nextcloud 35.0.0 le 2026-10-01 et figure avec sa sortie dans les preuves brutes
([raw/29-01-messungen.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt),
[raw/29-06-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt),
[raw/29-REVIEW-FIX-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live-beweis.txt), reprise avec le code actuel).

<a id="operating-modes"></a>
## Modes de fonctionnement

| | Libre-service (collaboratif) | Mode organisation (étiquette restreinte avec délégation à des groupes) |
|---|---|---|
| Niveau d'accès de l'étiquette | `public` | `restricted` |
| Qui peut poser et retirer `kein-ki` | tout utilisateur qui voit le fichier | les administrateurs et les membres des groupes délégués |
| Mesuré sur Nextcloud 35 | un compte normal voit l'étiquette et peut l'attribuer (M1b) | un membre de `ki-verantwortung` l'attribue (201), un non-membre reçoit 403 (M8) |

Renommer ou supprimer une étiquette via WebDAV est réservé aux administrateurs dans les deux
modes (code source de Nextcloud, `SystemTagNode`,
[29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).

**Le libre-service** convient aux équipes où chacun décide de ses propres dossiers. Quiconque
voit un fichier peut aussi retirer l'étiquette ; cela découle du code source de Nextcloud
(`canUserAssignTag`, [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md))
et n'a pas été mesuré séparément.

**Le mode organisation** convient à une organisation où un groupe désigné décide de ce qui reste
à l'écart de l'assistant. Dans ce mode, activez aussi `restrict_creation_to_admin` : sans ce
réglage, chaque compte peut créer de nouvelles étiquettes, donc aussi des sosies comme `Kein KI`
que le connecteur ne respecte pas. Mesuré : sans le réglage, un compte normal a créé une
étiquette (201), avec le réglage le même compte a reçu 403 (M8).

Nextcloud refuse une nouvelle étiquette qui ne diffère d'une étiquette existante que par la
casse (`Tag KEIN-KI-M6 already exists`, code de sortie 2, M6). Les autres graphies sont acceptées :
`Kein KI`, `keinki` et `kein` plus un tiret demi-cadratin plus `ki` ont été créées à côté de
`kein-ki` comme étiquettes à part entière et enregistrées sans modification (M6). La commande de
vérification ci-dessous les trouve.

<a id="setup-self-service"></a>
## Mise en place : libre-service

1. Créer l'étiquette en `public` :

   ```
   php occ tag:add kein-ki public --output=json
   ```

   Sortie mesurée (M7) : `{"id":"200","name":"kein-ki","access":"public"}`

2. Étiqueter un dossier. Les utilisateurs le font dans l'interface web (détails du fichier,
   étiquettes). Un administrateur peut le faire avec occ ; le chemin est
   `<utilisateur>/files/<dossier>` sans barre oblique initiale, mesuré avec le dossier
   `KI-frei` du compte `alice` :

   ```
   php occ tag:files:add alice/files/KI-frei kein-ki public
   ```

   Sortie mesurée (M7) : `public tag named kein-ki added.`

   Le niveau d'accès dans cette commande doit correspondre à celui de l'étiquette existante ;
   avec un autre niveau, Nextcloud ne trouve pas l'étiquette et la commande échoue (piège P7 dans
   [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).

3. Contrôler le résultat avec la commande de vérification (voir [plus bas](#check-command)).

<a id="setup-organisation"></a>
## Mise en place : mode organisation

1. Créer le groupe qui décide et y ajouter ses membres :

   ```
   php occ group:add ki-verantwortung
   php occ group:adduser ki-verantwortung alice
   ```

   Sortie mesurée (M8) : `Created group "ki-verantwortung"` et `user alice added`

2. Créer l'étiquette en `restricted` :

   ```
   php occ tag:add kein-ki restricted --output=json
   ```

   Sortie mesurée (M8) : `{"id":"201","name":"kein-ki","access":"restricted"}`. L'`id` est le
   `<tag-id>` de l'étape suivante.

3. Déléguer l'étiquette au groupe. Nextcloud n'a pas de commande occ pour la délégation
   d'étiquettes à des groupes (vérifié sur Nextcloud 35). Il existe deux voies :

   - **Interface web :** le formulaire de l'application systemtags se trouve sous
     *Paramètres d'administration > Paramètres de base > Étiquettes collaboratives* (chemin de
     menu tiré des fichiers de traduction de Nextcloud 35, M9).
   - **WebDAV en tant qu'administrateur**, la propriété `oc:groups` définie par PROPPATCH
     (mesuré 207, M8) :

     ```
     curl -u admin:<app-password> -X PROPPATCH "https://cloud.example.com/remote.php/dav/systemtags/<tag-id>" -H "Content-Type: application/xml" --data '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:set><d:prop><oc:groups>ki-verantwortung</oc:groups></d:prop></d:set></d:propertyupdate>'
     ```

     Plusieurs groupes se séparent par `|` (code source de Nextcloud, `SystemTagPlugin`,
     [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).
     Autre possibilité, les étapes 2 et 3 en une seule requête POST (mesuré 201, M8) :

     ```
     curl -u admin:<app-password> -X POST "https://cloud.example.com/remote.php/dav/systemtags/" -H "Content-Type: application/json" -d '{"name":"kein-ki","userVisible":true,"userAssignable":false,"groups":"ki-verantwortung"}'
     ```

4. Réserver la création d'étiquettes aux administrateurs :

   ```
   php occ config:app:set systemtags restrict_creation_to_admin --value=true --type=boolean
   php occ config:app:get systemtags restrict_creation_to_admin
   ```

   Sortie mesurée (M8) : `Config value 'restrict_creation_to_admin' for app 'systemtags' is now
   set to '1', stored as boolean in fast cache`, puis `1`.

5. Contrôler le résultat avec la commande de vérification.

<a id="check-command"></a>
## La commande de vérification

```
php occ mcp_connector:exclusion:check --admin=<uid>
php occ mcp_connector:exclusion:check --admin=<uid> --json
```

La commande s'exécute sans session utilisateur, ne fait que lire et ne modifie rien : lors de la
preuve en conditions réelles, les tables `systemtag`, `systemtag_object_mapping`,
`systemtag_group` et la configuration de l'application `systemtags` étaient identiques avant et
après chacun des 20 appels
([raw/29-06-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt)).
Sans `--admin`, elle lit en tant que comptes réels de l'instance ; la reprise du 2026-10-01 a donc
aussi comparé les tables de compte `preferences`, `storages`, `mounts` et `filecache` :
identiques avant et après chacun des 20 appels, et identiques autour d'une exécution dont le
premier compte lecteur venait d'être créé et ne s'était jamais connecté
([raw/29-REVIEW-FIX-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live-beweis.txt),
[raw/29-REVIEW-FIX-live.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live.txt), WR-04).
Sa sortie indique des nombres, des noms d'étiquettes et des groupes de délégation, jamais un
fichier, un chemin ou un compte.

Elle vérifie sept étapes dans cet ordre :

1. `admin_identity` : le compte nommé avec `--admin` est administrateur (`not_checked` avec
   `admin_unconfirmed` s'il n'a pas pu être confirmé, par exemple un uid mal saisi).
2. `tag_listing_readable` : la liste des étiquettes de l'instance est lisible.
3. `tag_exists` : une étiquette nommée exactement `kein-ki` existe (casse ignorée, comme le
   filtre du connecteur).
4. `tag_visible` : cette étiquette est visible pour les utilisateurs.
5. `no_variants` : aucune autre graphie (`Kein KI`, `keinki`, tirets, tirets bas) n'est
   utilisée.
6. `operating_mode` : libre-service ou mode organisation, avec les groupes délégués.
7. `assignment_count` : combien d'éléments portent l'étiquette.

**Verdict.** L'absence totale d'étiquette `kein-ki` est une indication, pas un échec : `passed`
reste true et la sortie explique comment la créer. Une étiquette `kein-ki` invisible, ou
seulement une autre graphie sans l'étiquette exacte, échoue (`passed` false). L'étiquette exacte
à côté d'une autre graphie réussit avec un avertissement qui désigne les éléments portant l'autre
graphie comme non exclus.

**Code de sortie.** Via AppAPI, le code de sortie de la commande vaut toujours 0, quel que soit
le verdict. Un script ou une supervision lit la clé `passed` de la réponse `--json`, jamais le
code de sortie.

**Sans `--admin`.** La commande lit alors en tant que premier compte de la liste des utilisateurs
de l'instance (triée), sur beaucoup d'instances un administrateur, et n'évalue que les étiquettes
visibles. Elle ne peut pas vérifier ainsi les étiquettes invisibles ni les groupes de délégation,
et la sortie le dit. Pour la vérification complète, la lancer avec `--admin=<uid>`.

**Nombres.** Le nombre compte les attributions sur toute l'instance, y compris les fichiers de la
corbeille ; sur Nextcloud 35, il est même resté après `occ trashbin:cleanup` (mesuré 2 avant,
2 dans la corbeille, 2 après, M4 dans
[raw/29-01-messungen.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt)).
Ce n'est donc pas le nombre de fichiers qu'un utilisateur peut atteindre.

La commande répond en anglais ; la ligne "See docs/exclusion.md" renvoie à la page anglaise.

Sortie mesurée, libre-service (preuve en conditions réelles, cas B) :

```
$ php occ mcp_connector:exclusion:check --admin=<uid>
  checked the kein-ki exclusion tag of this instance, read only
  passed       the named account is an administrator
  passed       the tag listing of this instance can be read
  passed       a tag named exactly kein-ki exists
  passed       the kein-ki tag is visible to users
  passed       no other spelling of kein-ki is in use
  passed       the operating mode of the kein-ki tag
  passed       the items carrying kein-ki can be counted
  Self service: every user who can see a file can set and remove kein-ki on it.
  Items carrying kein-ki (assignments across the instance, trash bin included): 1
  A green result does not cover shares: a tag above the root of a share does not protect it for the recipient. See docs/exclusion.md.
```

Sortie mesurée, étiquette exacte à côté d'une autre graphie (preuve en conditions réelles,
cas F) :

```
$ php occ mcp_connector:exclusion:check --admin=<uid>
  checked the kein-ki exclusion tag of this instance, read only
  passed       the named account is an administrator
  passed       the tag listing of this instance can be read
  passed       a tag named exactly kein-ki exists
  passed       the kein-ki tag is visible to users
  note         no other spelling of kein-ki is in use (variant_beside_exact)
  passed       the operating mode of the kein-ki tag
  passed       the items carrying kein-ki can be counted
  Self service: every user who can see a file can set and remove kein-ki on it.
  Items carrying kein-ki (assignments across the instance, trash bin included): 1
  Items tagged 'keinki' are NOT excluded: 1
  A green result does not cover shares: a tag above the root of a share does not protect it for the recipient. See docs/exclusion.md.
```

La même preuve couvre l'absence d'étiquette, le mode organisation, une étiquette invisible,
seulement une autre graphie et un non-administrateur nommé avec `--admin` ; la forme JSON du
cas B est
`{"checked":true,"passed":true,"mode":"self_service","assigned":1,"unprotected":0,...}`.

## Limites

Une vérification verte signifie que l'étiquette est correctement configurée. Elle ne signifie
pas que rien d'étiqueté ne peut jamais transparaître. Voici les limites, une phrase chacune, avec
le constat sur lequel elles reposent.

<a id="limit-share-boundary"></a>
### Limite du partage

Une étiquette sur un dossier au-dessus de la racine d'un partage est invisible pour le
destinataire, le dossier partagé apparaît donc non protégé dans les sessions du destinataire ;
une étiquette sur le dossier partagé lui-même fonctionne, étiquetez donc le nœud que vous
partagez.
Source : [25-MESSBERICHT.md, K5, Freigabe-Grenze](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="limit-invisible-tag"></a>
### Une étiquette invisible ne fonctionne pas

Pour un compte qui n'est pas administrateur, une étiquette invisible n'existe pas (la requête
d'étiquette répond 412 et la liste l'omet), elle ne filtre donc que dans les sessions
d'administrateurs ; la commande de vérification la signale comme échouée.
Source : [25-MESSBERICHT.md, K5, unsichtbares Tag](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md) ;
l'administrateur la voit : [raw/29-01-messungen.txt, M2](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt).

<a id="limit-app-disabled"></a>
### Application systemtags désactivée

Après `occ app:disable systemtags`, la requête d'étiquette continue de répondre avec des
résultats sur Nextcloud 32 à 35, le connecteur continue donc de filtrer ; disparaissent le
fournisseur de recherche de systemtags, la capability (sur 32 à 34 avec APCu seulement après un
redémarrage du serveur web) et les commandes occ `tag:files:*`.
Source : [25-MESSBERICHT.md, K1](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="limit-timing"></a>
### Temps de réponse

Un élément étiqueté coûte une requête d'étiquette de plus qu'un élément absent, le temps de
réponse peut donc les distinguer ; le connecteur n'ajoute aucun délai artificiel (une
limite connue, assumée délibérément).
Source : [28-CONTEXT.md, D-28-12](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-06](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-search-outage"></a>
### search pendant une panne

Quand la vérification d'exclusion ne peut pas obtenir de réponse, l'outil ChatGPT `search`
renvoie moins de résultats sans le signaler ; rien d'étiqueté ne passe.
Source : [28-CONTEXT.md, D-28-13](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-08](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-notes-create"></a>
### notes_create

`notes_create` crée une catégorie qui n'existe pas et en refuse une qui est étiquetée, le refus
montre donc qu'un dossier étiqueté de ce nom existe (assumé délibérément, fixé par un test).
Source : [28-CONTEXT.md, D-28-16](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-07](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-third-party-providers"></a>
### Fournisseurs de recherche d'applications tierces

Un fournisseur de recherche qui nomme des fichiers sans identifiant de fichier, sans chemin ni
lien `/f/<id>` n'est pas contrôlé et passe par la recherche unifiée (à l'exécution, le connecteur le laisse
passer en cas de doute, choix délibéré) ; le contrôle en CI ne voit que les fournisseurs de l'instance de CI.
Source : [28-REVIEW.md, WR-02 et décisions du propriétaire](../.planning/phases/28-gates-und-beweise/28-REVIEW.md).

<a id="limit-tables-free-text"></a>
### Texte libre de Tables avec `/f/<id>`

Les cellules Tables en texte libre qui contiennent une adresse `/f/<id>` restent intactes ; seuls
les objets lien sont contrôlés.
Source : [28-REVIEW.md, WR-03](../.planning/phases/28-gates-und-beweise/28-REVIEW.md),
[28-CONTEXT.md, D-28-18](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-03](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-talk-file-room"></a>
### Conversations de fichier Talk pendant un échec de la recherche de chemin

Si la recherche de chemin échoue alors qu'un dossier est étiqueté, Talk répond différemment pour
une conversation de fichier que pour un jeton inventé, un appelant peut donc savoir qu'un jeton
appartient à une conversation de fichier, même pour un fichier étiqueté.
Source : [28-REVIEW.md, IN-02](../.planning/phases/28-gates-und-beweise/28-REVIEW.md).

## Autres limites techniques

<a id="tech-sqlite"></a>
### SQLite avec de nombreuses attributions d'étiquettes

Mesuré : sur SQLite, une requête d'étiquette avec un seul résultat a pris environ 240 s pour
140 005 attributions (240 298 ms, Nextcloud 35.0.0, mesuré le 2026-09-26 ; PostgreSQL : médiane
de 62 ms pour 110 005). Le connecteur attend au plus 15 s une requête d'étiquette (`TAG_BUDGET`
dans [exclusion.py](../src/mcp_connector/nextcloud/exclusion.py)), la vérification s'y termine donc sans
réponse, et les entrées porteuses de fichiers sont retenues (fail-closed).
Source : [25-MESSBERICHT.md, G2 et décision du propriétaire E3](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="tech-upload-oracle"></a>
### Envoi à côté d'un fichier étiqueté

Un envoi vers une destination étiquetée reçoit le refus d'un dossier parent manquant ; pour un
fichier étiqueté sous un dossier parent visible, ce refus montre quand même que quelque chose
est particulier à cet endroit, ce qui ne peut être évité sans écrire.
Source : [27-SECURITY.md, A-27-03](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-SECURITY.md).

<a id="tech-folder-oracle"></a>
### Dossier à côté d'un dossier étiqueté

La création d'un dossier dans un dossier étiqueté ou en dessous reçoit le refus d'un dossier
parent manquant ; à côté d'un dossier parent visible, ce refus montre quand même que quelque
chose est particulier à cet endroit, ce qui ne peut être évité sans écrire.
Source : [folder-evidence.md, Folder next to a tagged folder](folder-evidence.md#folder-next-to-a-tagged-folder).

<a id="tech-tables-talk-sandbox"></a>
### Tables et Talk sans bac à sable

Tables et Talk reçoivent seulement la vérification d'étiquette, pas le bac à sable de dossier
`NC_MCP_FILES_ROOT` des outils de fichiers.
Source : [28-SECURITY.md, A-28-04](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="tech-foreign-text"></a>
### Noms de fichiers dans un texte tiers

Un nom de fichier saisi dans un message, un texte enrichi ou une description Deck se trouve hors
d'une vérification fondée sur les identifiants de fichier et n'est pas contrôlé.
Source : [28-SECURITY.md, A-28-03](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="tech-upload-staging"></a>
### Dossier de transit d'un envoi par blocs

Un envoi par blocs qui s'arrête tôt laisse derrière lui son dossier de transit
`uploads/<user>/nc-mcp-<sha256>` ; il ne révèle rien et relève du nettoyage.
Source : [28-CONTEXT.md, D-28-20](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md).

<a id="tech-talk-conversations"></a>
### Résultats de talk-conversations

Les résultats du fournisseur de recherche `talk-conversations` suivent deux règles : un résultat
dont le jeton ne figure pas dans la liste des conversations est retenu dès que quoi que ce soit
est étiqueté, et si la liste ne peut pas être lue, tous sont retenus avec une seule entrée
degraded sous le nom du fournisseur.
Source : [28-CONTEXT.md, D-28-21](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md).

<a id="tech-one-wording"></a>
### Une seule formulation quand la vérification reste sans réponse

Chaque outil dit la même chose quand la vérification ne peut pas obtenir de réponse : "The
exclusion check (tag kein-ki) could not be answered, so entries that may carry file content are
withheld."
Source : [27-CONTEXT.md, D-27-05](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-CONTEXT.md).

<a id="tech-mariadb"></a>
### MySQL et MariaDB non mesurés

Les constats sur les graphies et toutes les durées valent pour SQLite et PostgreSQL ; MySQL et
MariaDB n'ont pas été mesurés.
Source : [25-MESSBERICHT.md, Grenzen der Messung](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

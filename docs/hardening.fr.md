[English](hardening.md) | [Deutsch](hardening.de.md) | Français

# Exploiter le connecteur sur des données confidentielles

Chaque limite offerte par ce serveur, sur une seule page, dans l'ordre dans
lequel un administrateur devrait les mettre en place. Chaque section nomme le
mécanisme, ce contre quoi il protège et, là où cela compte, ce contre quoi il
ne protège **pas**. Les documents détaillés sont liés à la fin des sections.

## 1. La limite qui compte : les permissions Nextcloud

Chaque requête s'exécute avec les droits de l'utilisateur connecté, contre
les API propres de Nextcloud ; l'assistant ne peut jamais voir plus que la
personne qui l'a connecté. Il n'existe dans ce serveur aucun second modèle de
droits qui pourrait dériver. C'est le mur porteur : tout ce qui suit réduit
la surface, rien de ce qui suit ne le remplace.

Conséquence pratique : pour une automatisation (n8n et similaires), connecter
un compte qui ne porte que les droits nécessaires à la tâche, jamais un
compte personnel ni un compte administrateur.

## 2. Exclure ce que l'assistant ne doit jamais voir : l'étiquette kein-ki

Un dossier ou un fichier portant l'étiquette collaborative `kein-ki`
disparaît pour l'assistant, avec tout ce qu'il contient, dans chaque outil,
chaque recherche et chaque bundle de contexte.

- Vérifier la configuration avant de s'y fier :
  `php occ mcp_connector:exclusion:check --admin=<uid>`
- La limite la plus importante : une étiquette **au-dessus de la racine d'un
  partage** ne protège pas le dossier partagé chez le destinataire.
  Étiqueter le dossier qui est partagé.
- Toutes les limites, avec les constats qui les fondent :
  [exclusion.fr.md](exclusion.fr.md).

## 3. Réduire la surface des fichiers : NC_MCP_FILES_ROOT

Avec `NC_MCP_FILES_ROOT=/Documents/IA`, ce répertoire devient la racine des
outils de fichiers, et aucun outil de fichiers n'atteint les dossiers
au-dessus. Utile quand l'assistant n'a besoin que d'une zone de travail ;
tout le reste cesse d'être accessible par les outils de fichiers.

## 4. Fermer le canal sortant : NC_MCP_TALK_SEND

Ce serveur détient des données privées, reçoit des contenus non fiables et
possède exactement un canal sortant, `talk_send`. Ces trois éléments réunis
forment la « lethal trifecta », et retirer un ingrédient est le geste le plus
fort disponible : désactiver `talk_send` pour toute l'instance (Paramètres,
Administration, Sécurité) ferme le canal, la lecture reste intacte. Mail est
en lecture seule par conception et n'apporte aucune sortie propre.

Si l'assistant n'a pas besoin d'écrire dans Talk : désactiver, et toute cette
classe d'exfiltration s'arrête à la frontière de l'instance.

## 5. Ce que la désactivation des bundles ne fait PAS

`NC_MCP_DISABLED_TOOLS` masque des outils pour que les clients aux petits
modèles ou aux limites d'outils strictes en voient moins. Ce n'est **pas un
contrôle d'accès** : `search`, `fetch` et `prepare_context` atteignent
toujours le contenu d'un bundle désactivé. Cela vaut aussi pour le bundle
`tasks` : avec `tasks` désactivé, `fetch` lit toujours un id `task:` et
`search` trouve toujours les tâches via le fournisseur de recherche de
Nextcloud. La limite est et reste celle des sections 1, 2 et 3. C'est écrit
aussi dans le README, et répété ici à dessein, car c'est la lecture erronée
la plus tentante de la configuration de ce serveur.

## 6. Injection de prompt : le reste honnête

Un courriel ou un message Talk est écrit par quelqu'un d'autre, un document
peut l'être aussi, et un modèle de langage ne sépare pas de façon fiable les
données des instructions. Aucune défense complète n'est connue. Ce serveur
borne le dégât à la place :

- aucun outil ne supprime, n'écrase, ne déplace, ne renomme ni ne modifie
  des partages ou des droits ; l'écriture est création seule, et un test de
  contrat échoue au premier appel destructif,
- les contenus reviennent avec leur origine en champs structurés, le client
  peut voir d'où vient un texte,
- le canal sortant peut être fermé pour toute l'instance (section 4).

Ce qui reste, avec chaque contre-mesure en détail : [privacy.md](privacy.md)
(en anglais). Côté client, laisser activées les confirmations d'écriture de
l'assistant si le client les propose.

## 7. Activer le journal d'audit

Désactivé par défaut, un interrupteur dans les paramètres d'administration de
cette application. Activé, chaque appel d'outil est consigné avec le compte,
l'outil, l'heure, l'application appelante et l'issue, jamais avec une valeur
de paramètre ni une partie d'un résultat. Les entrées sont chaînées par
hachage ; `occ mcp_connector:audit:read` les lit et
`occ mcp_connector:audit:verify` nomme le premier maillon rompu en cas de
manipulation. Sur des données confidentielles, c'est la différence entre
« nous pensons qu'il ne s'est rien passé » et « nous pouvons montrer ce qui
s'est passé ».

## 8. Local ne veut pas dire que le modèle est local

Ce serveur n'indexe, ne met en cache et ne copie rien, et aucun contenu ne
quitte vos machines, **sauf** vers l'assistant qui a demandé. Un assistant en
nuage reçoit les extraits que ses outils récupèrent. Si cela n'est pas
acceptable pour vos données, il faut un modèle local ; le connecteur ne peut
pas rendre local un modèle distant.

## 9. Avant la production : essayer de s'introduire

Dérouler ces épreuves une fois, comme second utilisateur et comme
l'utilisateur connecté, et garder les résultats avec les notes
d'exploitation :

1. `php occ mcp_connector:exclusion:check --admin=<uid>` ne signale rien.
2. Un fichier étiqueté `kein-ki` n'est atteignable ni par `files_search`, ni
   par `unified_search`, `search`, `fetch` ou `prepare_context`.
3. Un fichier partagé **vers** le compte depuis un dossier dont l'étiquette
   est au-dessus de la racine du partage : confirmer qu'il est atteignable,
   puis étiqueter le dossier partagé lui-même s'il ne doit pas l'être
   (section 2).
4. Un fichier que l'utilisateur connecté ne peut pas lire dans Nextcloud
   n'est atteignable par aucun outil.
5. Avec `NC_MCP_TALK_SEND` désactivé, `talk_send` refuse pour toute
   l'instance.

Le cas de partage de la section 2 est celui que les installations réelles
ratent ; le tester avec sa propre arborescence, pas seulement sur le papier.

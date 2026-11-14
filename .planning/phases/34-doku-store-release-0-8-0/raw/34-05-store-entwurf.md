# Entwurf der Store-Texte für 0.8.0 (Plan 34-05, EXAPP-13, E11)

Stand: 2026-11-14, Basis appinfo/info.xml auf 13bdfdc (Version 0.7.3, Pin "release 0.7.0").
info.xml und der SHA-256-Pin bleiben unverändert, bis der Owner diesen Entwurf freigibt.

Belege für jede Aussage:

- Ordner anlegen, fehlende Elternordner, höchstens 10 je Aufruf, nichts überschrieben: `MAX_NEW_FOLDERS = 10` in src/mcp_connector/tools/files.py:69, README.md Tabelle `files_create_folder`, CHANGELOG.md [Unreleased].
- Aufgaben suchen, lesen, anlegen (Bundle `tasks`, ab Werk an, neu seit 0.7.3): CHANGELOG.md [Unreleased], README.md Tabelle `tasks_search`, `tasks_read`, `tasks_create`.
- Abhaken, wieder öffnen, ändern, verschieben nur mit Schalter `NC_MCP_TASKS_UPDATE` (ab Werk aus) und nur mit dem ETag aus `tasks_read`; Verschieben mit Unteraufgaben; wiederkehrende Aufgaben werden abgelehnt: README.md Zeilen 49 bis 55 und 95 bis 97, info.xml Variable `NC_MCP_TASKS_UPDATE`.
- Kein Löschen, auch keiner Aufgabe; einzige Verschiebe-Ausnahme `tasks_move`: README.md Zeilen 42 und 58, Registry-Test tests/contract/test_write_promise_truth.py (genau vier ändernde Werkzeuge: files_update, tasks_complete, tasks_update, tasks_move).
- Keine Werkzeugnamen und keine Zahl außer "10" und den Versionsnummern; kein Backtick, keine Tabelle (Gate test_exapp_env_setup.py).

## 1. summary (alle drei unverändert)

| Sprache | Text | Zeichen |
|---|---|---|
| EN | MCP server for Nextcloud: Claude, ChatGPT, n8n and other AI assistants read, search, create and edit, as the signed-in user. | 124 |
| DE | MCP Server für Nextcloud: Claude, ChatGPT, n8n und andere KI-Assistenten lesen, suchen und bearbeiten als angemeldeter Nutzer. | 126 |
| FR | Serveur MCP pour Nextcloud : Claude, ChatGPT, n8n et autres assistants IA lisent, cherchent et modifient, comme l'utilisateur. | 126 |

Begründung: Alle drei liegen bei 124 bis 126 von 128 Zeichen; "Aufgaben/tasks/tâches" passt nicht hinein, ohne ein Suchwort (MCP server, Claude, ChatGPT, n8n) zu opfern. "create and edit" deckt Ordner und Aufgaben schon ab.

## 2. description EN

Neuer Text, Zeilen mit [NEU] oder [GEÄNDERT] markiert, alle anderen wörtlich wie heute:

```
What MCP Connector does:

- Connects MCP assistants (Claude, ChatGPT, n8n, your own agent) to Nextcloud; every request runs as the signed-in user (OAuth sign-in; a per-account switch pauses access, one click can disconnect an assistant)
- Tools: files (Office and PDF read as Markdown), calendar, tasks, notes, Deck, contacts, Tables, Talk, mail (read only) and one search across all of it   [GEÄNDERT]
- Nothing destructive: no delete, tasks included; no share; no move except one task when the admin enables changing tasks; nothing in the background, no telemetry   [GEÄNDERT]
- New in 0.8.0: create folders, missing parent folders too (at most 10 per call, nothing is overwritten); search, read and create tasks   [NEU, ersetzt "New in 0.7.0"]
- Change existing tasks, off by default: complete, reopen, edit, or move a task with its subtasks into another list; the admin enables it, and a task is only changed when it is unchanged since it was read; recurring tasks are not changed, and tasks are never deleted   [NEU]
- Edit existing text files, off by default; the admin enables it, and a file is only replaced when it has not changed in the meantime
- Files and folders with the collaborative tag kein-ki stay invisible to every assistant; occ mcp_connector:exclusion:check shows whether the tag is set up correctly

Together with [Findling](https://apps.nextcloud.com/apps/findling), search hits include the contents of your documents, scans included, with exactly the rights of the asking user.

### Enterprise

(ab hier unverändert bis zum Ende)
```

Diff gegen heute (info.xml):

```
alt 68: - Tools: files (Office and PDF read as Markdown), calendar, notes, Deck, contacts, Tables, Talk, mail (read only) and one search across all of it
neu   : - Tools: files (Office and PDF read as Markdown), calendar, tasks, notes, Deck, contacts, Tables, Talk, mail (read only) and one search across all of it

alt 69: - Nothing destructive: no delete, no move, no share; nothing in the background, no telemetry
neu   : - Nothing destructive: no delete, tasks included; no share; no move except one task when the admin enables changing tasks; nothing in the background, no telemetry

alt 70: - New in 0.7.0: a file attached to a ChatGPT message lands straight in your Nextcloud; only trusted ChatGPT download hosts, checked before anything is written, and uploads never overwrite
neu   : - New in 0.8.0: create folders, missing parent folders too (at most 10 per call, nothing is overwritten); search, read and create tasks

neu   : - Change existing tasks, off by default: complete, reopen, edit, or move a task with its subtasks into another list; the admin enables it, and a task is only changed when it is unchanged since it was read; recurring tasks are not changed, and tasks are never deleted
```

## 3. description DE

```
Was der MCP Connector kann:

- Verbindet MCP-Assistenten (Claude, ChatGPT, n8n, eigene Agenten) mit Nextcloud; jede Anfrage läuft als der angemeldete Nutzer (OAuth-Anmeldung; ein Schalter je Konto pausiert den Zugriff, ein Klick kann einen Assistenten trennen)
- Werkzeuge: Dateien (Office und PDF als Markdown lesbar), Kalender, Aufgaben, Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen) und eine Suche über alles   [GEÄNDERT]
- Nichts Destruktives: kein Löschen, auch keiner Aufgabe; kein Teilen; kein Verschieben, außer einer einzelnen Aufgabe, wenn der Admin das Ändern von Aufgaben freischaltet; nichts im Hintergrund, keine Telemetrie   [GEÄNDERT]
- Neu in 0.8.0: Ordner anlegen, auch fehlende Elternordner (höchstens 10 je Aufruf, nichts wird überschrieben); Aufgaben suchen, lesen und anlegen   [NEU, ersetzt "Neu in 0.7.0"]
- Bestehende Aufgaben ändern, ab Werk aus: abhaken, wieder öffnen, bearbeiten oder mit ihren Unteraufgaben in eine andere Liste verschieben; der Admin schaltet es frei, und eine Aufgabe wird nur geändert, wenn sie seit dem Lesen unverändert ist; wiederkehrende Aufgaben bleiben unberührt, und Aufgaben werden nie gelöscht   [NEU]
- Bestehende Textdateien bearbeiten, ab Werk aus; der Admin schaltet es frei, und eine Datei wird nur ersetzt, wenn sie sich zwischenzeitlich nicht geändert hat
- Dateien und Ordner mit dem kollaborativen Tag kein-ki bleiben für jeden Assistenten unsichtbar; occ mcp_connector:exclusion:check zeigt, ob das Tag richtig eingerichtet ist

Zusammen mit [Findling](https://apps.nextcloud.com/apps/findling) enthalten Suchtreffer die Inhalte Ihrer Dokumente, auch aus Scans, mit genau den Rechten des fragenden Nutzers.

### Enterprise

(ab hier unverändert bis zum Ende)
```

Diff gegen heute (info.xml):

```
alt 88: - Werkzeuge: Dateien (Office und PDF als Markdown lesbar), Kalender, Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen) und eine Suche über alles
neu   : - Werkzeuge: Dateien (Office und PDF als Markdown lesbar), Kalender, Aufgaben, Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen) und eine Suche über alles

alt 89: - Nichts Destruktives: kein Löschen, kein Verschieben, kein Teilen; nichts im Hintergrund, keine Telemetrie
neu   : - Nichts Destruktives: kein Löschen, auch keiner Aufgabe; kein Teilen; kein Verschieben, außer einer einzelnen Aufgabe, wenn der Admin das Ändern von Aufgaben freischaltet; nichts im Hintergrund, keine Telemetrie

alt 90: - Neu in 0.7.0: eine an die ChatGPT-Nachricht angehängte Datei landet direkt in Ihrer Nextcloud; nur vertrauenswürdige ChatGPT-Hosts, geprüft bevor etwas geschrieben wird, und Uploads überschreiben nie
neu   : - Neu in 0.8.0: Ordner anlegen, auch fehlende Elternordner (höchstens 10 je Aufruf, nichts wird überschrieben); Aufgaben suchen, lesen und anlegen

neu   : - Bestehende Aufgaben ändern, ab Werk aus: abhaken, wieder öffnen, bearbeiten oder mit ihren Unteraufgaben in eine andere Liste verschieben; der Admin schaltet es frei, und eine Aufgabe wird nur geändert, wenn sie seit dem Lesen unverändert ist; wiederkehrende Aufgaben bleiben unberührt, und Aufgaben werden nie gelöscht
```

## 4. description FR

```
Ce que sait faire le MCP Connector :

- Connecte les assistants MCP (Claude, ChatGPT, n8n, vos propres agents) à Nextcloud ; chaque requête s'exécute comme l'utilisateur connecté (connexion OAuth ; un interrupteur par compte suspend l'accès, un clic peut déconnecter un assistant)
- Outils : fichiers (Office et PDF lus en Markdown), calendrier, tâches, notes, Deck, contacts, Tables, Talk, mail (lecture seule) et une recherche sur tout   [GEÄNDERT]
- Rien de destructif : pas de suppression, tâches comprises ; pas de partage ; pas de déplacement, sauf celui d'une seule tâche quand l'administrateur active la modification des tâches ; rien en arrière-plan, pas de télémétrie   [GEÄNDERT]
- Nouveau en 0.8.0 : créer des dossiers, dossiers parents manquants compris (10 au plus par appel, rien n'est écrasé) ; chercher, lire et créer des tâches   [NEU, ersetzt "Nouveau en 0.7.0"]
- Modifier des tâches existantes, désactivé par défaut : marquer comme terminée, rouvrir, modifier ou déplacer une tâche avec ses sous-tâches vers une autre liste ; l'administrateur l'active, et une tâche n'est modifiée que si elle n'a pas changé depuis sa lecture ; les tâches récurrentes ne sont pas modifiées, et aucune tâche n'est jamais supprimée   [NEU]
- Modifier des fichiers texte existants, désactivé par défaut ; l'administrateur l'active, et un fichier n'est remplacé que s'il n'a pas changé entre-temps
- Les fichiers et dossiers portant l'étiquette collaborative kein-ki restent invisibles pour tout assistant ; occ mcp_connector:exclusion:check indique si l'étiquette est correctement configurée

Avec [Findling](https://apps.nextcloud.com/apps/findling), les résultats de recherche incluent le contenu de vos documents, numérisations comprises, avec exactement les droits de l'utilisateur qui demande.

### Enterprise

(ab hier unverändert bis zum Ende)
```

Diff gegen heute (info.xml):

```
alt 108: - Outils : fichiers (Office et PDF lus en Markdown), calendrier, notes, Deck, contacts, Tables, Talk, mail (lecture seule) et une recherche sur tout
neu    : - Outils : fichiers (Office et PDF lus en Markdown), calendrier, tâches, notes, Deck, contacts, Tables, Talk, mail (lecture seule) et une recherche sur tout

alt 109: - Rien de destructif : pas de suppression, pas de déplacement, pas de partage ; rien en arrière-plan, pas de télémétrie
neu    : - Rien de destructif : pas de suppression, tâches comprises ; pas de partage ; pas de déplacement, sauf celui d'une seule tâche quand l'administrateur active la modification des tâches ; rien en arrière-plan, pas de télémétrie

alt 110: - Nouveau en 0.7.0 : un fichier joint au message ChatGPT arrive directement dans votre Nextcloud ; seuls les hôtes ChatGPT de confiance, vérifiés avant toute écriture, et les envois n'écrasent jamais rien
neu    : - Nouveau en 0.8.0 : créer des dossiers, dossiers parents manquants compris (10 au plus par appel, rien n'est écrasé) ; chercher, lire et créer des tâches

neu    : - Modifier des tâches existantes, désactivé par défaut : marquer comme terminée, rouvrir, modifier ou déplacer une tâche avec ses sous-tâches vers une autre liste ; l'administrateur l'active, et une tâche n'est modifiée que si elle n'a pas changé depuis sa lecture ; les tâches récurrentes ne sont pas modifiées, et aucune tâche n'est jamais supprimée
```

## 5. Vorschlag zum Punkt "New in 0.7.0"

Vorschlag: streichen (in allen drei Sprachen ersetzt durch "New in 0.8.0"). Begründung: Owner-Regel "nur Neuerungen"; der Punkt war die Neuerung von 0.7.0 und steht vollständig im CHANGELOG. Kosten: die ChatGPT-Dateiübernahme wird im Store-Text nicht mehr genannt.

Variante B (falls die Fähigkeit sichtbar bleiben soll), als normaler Punkt ohne Versionsnummer:

- EN: Files attached to a ChatGPT message land in your Nextcloud; only trusted ChatGPT hosts, and uploads never overwrite
- DE: An eine ChatGPT-Nachricht angehängte Dateien landen in Ihrer Nextcloud; nur vertrauenswürdige ChatGPT-Hosts, und Uploads überschreiben nie
- FR : Les fichiers joints à un message ChatGPT arrivent dans votre Nextcloud ; seuls les hôtes ChatGPT de confiance, et les envois n'écrasent jamais rien

## 6. Offene Frage: discussion-Link

Das Runbook (docs/store-submission.md, Zeile 0.7.0) sah den `<discussion>`-Link für 0.8.0 vor: "travels with 0.8.0 once the forum thread exists". Laut Owner-Entscheid vom 12.11. ist der Forum-Post zurückgestellt (erst nach PII Redaction und Audio & Video Search). Frage an den Owner: Gibt es eine Forum-URL für `<discussion>`, oder bleibt es bei "kein Link"? Ohne URL vom Owner kommt kein `<discussion>`-Element in info.xml.

Antwortform: `freigabe`, `aenderung: ...` oder `nein`; dazu `discussion=<url>` oder `discussion=kein`.

# Entwurf der Store-Texte für 0.9.0 (Plan 35-02, Owner-Entscheid 2 vom 2026-11-19)

Stand: 2026-11-19, Basis appinfo/info.xml auf 23dd21b2 (Version 0.8.0, Pin "release 0.8.0", EXPECTED_SHA256 4e510fec...).
info.xml und der SHA-256-Pin bleiben unverändert, bis der Owner diesen Entwurf freigibt.

Was sich ändert (nach Owner-Entscheid 2):

1. Der Punkt "New in 0.8.0" / "Neu in 0.8.0" / "Nouveau en 0.8.0" entfällt als Versionspunkt. Ordner anlegen und Aufgaben suchen, lesen, anlegen wandern in die normale Liste: Variante A (im Punkt "Tools") oder Variante B (eigener Punkt ohne Version).
2. Neuer Punkt "New in 0.9.0" / "Neu in 0.9.0" / "Nouveau en 0.9.0" zu Profile Fields, an der Stelle des alten Versionspunkts.
3. Alle übrigen Punkte, die Absätze Findling, Enterprise und Anforderungen wörtlich wie heute, insbesondere die Löschgrenze ("no delete, tasks included" und "tasks are never deleted").

Empfehlung: Variante A (kürzer bei gleicher Aussage, siehe Abschnitt 6).

## Belege

Geprüft in diesem Plan (gegen den Code gelesen):

- Nur lesend: src/mcp_connector/tools/profile_fields.py ruft ausschließlich ocs.ocs_get auf (Zeilen 35, 78, 98, 131), kein anderer HTTP-Aufruf in der Datei.
- Eigene Werte für jedes Konto: Ebene me, Route /me/values, profile_fields.py Zeile 78.
- Feldkatalog: Ebene definitions, Route /definitions, profile_fields.py Zeile 98.
- Werte anderer Konten: Ebene values, Route /users/{uid}/values, profile_fields.py Zeilen 131 bis 133.
- Exakte Suche nach Feldwert: Ebene search, Route /users/search mit operator eq, profile_fields.py Zeilen 35 bis 46.
- Keine eigene Rechteprüfung im Connector und keine erhöhten Rechte: der Aufruf läuft mit clients.creds des verbundenen Kontos (alle vier ocs_get-Aufrufe); die Grenze zieht die App Profile Fields selbst. Darum sagt der Text "checked by Profile Fields itself" und nicht "checked by MCP Connector".

Angenommen, nicht in diesem Plan gemessen:

- Dass die App Profile Fields die Routen definitions, users/{uid}/values und users/search Administratoren vorbehält: aus 35-RULES Abschnitt 8, README.md Zeile 110 und raw/35-01-faktencheck.txt Zeile 56 (urteil=stimmt). Der Livebeweis mit einem Konto ohne Adminrechte gehört in den Volltest (35-04/35-05); zeigt er etwas anderes, ist der Satz falsch und der Release hält an (35-RULES Abschnitt 11).
- Schalter ab Werk aus, der Admin schaltet ihn ein: 35-RULES Abschnitt 8, raw/35-01-faktencheck.txt Zeile 66 (config.py:767).

Bewusst nicht im Store-Text: die Suche über alles erreicht den Suchanbieter von Profile Fields auch ohne Schalter (docs/threat-model.md Zeile 230). Der Punkt "one search across all of it" bleibt wahr; die Einzelheit steht in README und threat-model.

## 1. summary (alle drei unverändert)

- EN (124 Zeichen): MCP server for Nextcloud: Claude, ChatGPT, n8n and other AI assistants read, search, create and edit, as the signed-in user.
- DE (126 Zeichen): MCP Server für Nextcloud: Claude, ChatGPT, n8n und andere KI-Assistenten lesen, suchen und bearbeiten als angemeldeter Nutzer.
- FR (126 Zeichen): Serveur MCP pour Nextcloud : Claude, ChatGPT, n8n et autres assistants IA lisent, cherchent et modifient, comme l'utilisateur.

Begründung: 124 bis 126 von 128 Zeichen; "Profile Fields" passt nicht hinein, ohne ein Suchwort (MCP server, Claude, ChatGPT, n8n) zu opfern, und "read" deckt das Lesen der Felder ab.

## 2. description EN

Variante A (empfohlen), Zeilen mit [GEÄNDERT] oder [NEU] markiert, alle anderen wörtlich wie heute:

```
What MCP Connector does:

- Connects MCP assistants (Claude, ChatGPT, n8n, your own agent) to Nextcloud; every request runs as the signed-in user (OAuth sign-in; a per-account switch pauses access, one click can disconnect an assistant)
- Tools: files (Office and PDF read as Markdown; create folders, missing parent folders too, at most 10 per call, nothing is overwritten), calendar, tasks (search, read and create), notes, Deck, contacts, Tables, Talk, mail (read only) and one search across all of it   [GEÄNDERT]
- Nothing destructive: no delete, tasks included; no share; no move except one task when the admin enables changing tasks; nothing in the background, no telemetry
- New in 0.9.0: read the fields of the Profile Fields app, read only and off by default; the admin enables it; every account reads its own values, while the field catalogue, the values of other accounts and the exact search by field value are for administrators only, checked by Profile Fields itself   [NEU, ersetzt "New in 0.8.0"]
- Change existing tasks, off by default: complete, reopen, edit, or move a task with its subtasks into another list; the admin enables it, and a task is only changed when it is unchanged since it was read; recurring tasks are not changed, and tasks are never deleted
- Files attached to a ChatGPT message land in your Nextcloud; only trusted ChatGPT hosts, and uploads never overwrite
- Edit existing text files, off by default; the admin enables it, and a file is only replaced when it has not changed in the meantime
- Files and folders with the collaborative tag kein-ki stay invisible to every assistant; occ mcp_connector:exclusion:check shows whether the tag is set up correctly

Together with [Findling](https://apps.nextcloud.com/apps/findling), search hits include the contents of your documents, scans included, with exactly the rights of the asking user.

### Enterprise

(ab hier unverändert bis zum Ende)
```

Diff Variante A gegen heute (info.xml):

```
alt 68: - Tools: files (Office and PDF read as Markdown), calendar, tasks, notes, Deck, contacts, Tables, Talk, mail (read only) and one search across all of it
neu   : - Tools: files (Office and PDF read as Markdown; create folders, missing parent folders too, at most 10 per call, nothing is overwritten), calendar, tasks (search, read and create), notes, Deck, contacts, Tables, Talk, mail (read only) and one search across all of it

alt 70: - New in 0.8.0: create folders, missing parent folders too (at most 10 per call, nothing is overwritten); search, read and create tasks
neu   : - New in 0.9.0: read the fields of the Profile Fields app, read only and off by default; the admin enables it; every account reads its own values, while the field catalogue, the values of other accounts and the exact search by field value are for administrators only, checked by Profile Fields itself
```

Variante B, Diff gegen heute (Zeile 68 bleibt wie heute):

```
alt 70: - New in 0.8.0: create folders, missing parent folders too (at most 10 per call, nothing is overwritten); search, read and create tasks
neu   : - New in 0.9.0: (wie Variante A)
neu   : - Create folders, missing parent folders too (at most 10 per call, nothing is overwritten); search, read and create tasks
```

Beleg Rechte: profile_fields.py Zeile 78 (eigene Werte), Zeile 98 (Feldkatalog), Zeile 131 (Werte anderer Konten), Zeile 38 (exakte Suche), nur ocs_get.

## 3. description DE

Variante A (empfohlen):

```
Was der MCP Connector kann:

- Verbindet MCP-Assistenten (Claude, ChatGPT, n8n, eigene Agenten) mit Nextcloud; jede Anfrage läuft als der angemeldete Nutzer (OAuth-Anmeldung; ein Schalter je Konto pausiert den Zugriff, ein Klick kann einen Assistenten trennen)
- Werkzeuge: Dateien (Office und PDF als Markdown lesbar; Ordner anlegen, auch fehlende Elternordner, höchstens 10 je Aufruf, nichts wird überschrieben), Kalender, Aufgaben (suchen, lesen und anlegen), Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen) und eine Suche über alles   [GEÄNDERT]
- Nichts Destruktives: kein Löschen, auch nicht von Aufgaben; kein Teilen; kein Verschieben, außer einer einzelnen Aufgabe, wenn der Admin das Ändern von Aufgaben freischaltet; nichts im Hintergrund, keine Telemetrie
- Neu in 0.9.0: Felder der App Profile Fields lesen, nur lesend und ab Werk aus; der Admin schaltet es frei; jedes Konto liest seine eigenen Werte, während Feldkatalog, Werte anderer Konten und die exakte Suche nach Feldwerten Administratoren vorbehalten sind; das prüft Profile Fields selbst   [NEU, ersetzt "Neu in 0.8.0"]
- Bestehende Aufgaben ändern, ab Werk aus: abhaken, wieder öffnen, bearbeiten oder mit ihren Unteraufgaben in eine andere Liste verschieben; der Admin schaltet es frei, und eine Aufgabe wird nur geändert, wenn sie seit dem Lesen unverändert ist; wiederkehrende Aufgaben bleiben unberührt, und Aufgaben werden nie gelöscht
- An eine ChatGPT-Nachricht angehängte Dateien landen in Ihrer Nextcloud; nur vertrauenswürdige ChatGPT-Hosts, und Uploads überschreiben nie
- Bestehende Textdateien bearbeiten, ab Werk aus; der Admin schaltet es frei, und eine Datei wird nur ersetzt, wenn sie sich zwischenzeitlich nicht geändert hat
- Dateien und Ordner mit dem kollaborativen Tag kein-ki bleiben für jeden Assistenten unsichtbar; occ mcp_connector:exclusion:check zeigt, ob das Tag richtig eingerichtet ist

Zusammen mit [Findling](https://apps.nextcloud.com/apps/findling) enthalten Suchtreffer die Inhalte Ihrer Dokumente, auch aus Scans, mit genau den Rechten des fragenden Nutzers.

### Enterprise

(ab hier unverändert bis zum Ende)
```

Diff Variante A gegen heute (info.xml):

```
alt 90: - Werkzeuge: Dateien (Office und PDF als Markdown lesbar), Kalender, Aufgaben, Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen) und eine Suche über alles
neu   : - Werkzeuge: Dateien (Office und PDF als Markdown lesbar; Ordner anlegen, auch fehlende Elternordner, höchstens 10 je Aufruf, nichts wird überschrieben), Kalender, Aufgaben (suchen, lesen und anlegen), Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen) und eine Suche über alles

alt 92: - Neu in 0.8.0: Ordner anlegen, auch fehlende Elternordner (höchstens 10 je Aufruf, nichts wird überschrieben); Aufgaben suchen, lesen und anlegen
neu   : - Neu in 0.9.0: Felder der App Profile Fields lesen, nur lesend und ab Werk aus; der Admin schaltet es frei; jedes Konto liest seine eigenen Werte, während Feldkatalog, Werte anderer Konten und die exakte Suche nach Feldwerten Administratoren vorbehalten sind; das prüft Profile Fields selbst
```

Variante B, Diff gegen heute (Zeile 90 bleibt wie heute):

```
alt 92: - Neu in 0.8.0: Ordner anlegen, auch fehlende Elternordner (höchstens 10 je Aufruf, nichts wird überschrieben); Aufgaben suchen, lesen und anlegen
neu   : - Neu in 0.9.0: (wie Variante A)
neu   : - Ordner anlegen, auch fehlende Elternordner (höchstens 10 je Aufruf, nichts wird überschrieben); Aufgaben suchen, lesen und anlegen
```

Beleg Rechte: profile_fields.py Zeile 78 (eigene Werte), Zeile 98 (Feldkatalog), Zeile 131 (Werte anderer Konten), Zeile 38 (exakte Suche), nur ocs_get.

## 4. description FR

Variante A (empfohlen):

```
Ce que sait faire le MCP Connector :

- Connecte les assistants MCP (Claude, ChatGPT, n8n, vos propres agents) à Nextcloud ; chaque requête s'exécute comme l'utilisateur connecté (connexion OAuth ; un interrupteur par compte suspend l'accès, un clic peut déconnecter un assistant)
- Outils : fichiers (Office et PDF lus en Markdown ; créer des dossiers, dossiers parents manquants compris, 10 au plus par appel, rien n'est écrasé), calendrier, tâches (chercher, lire et créer), notes, Deck, contacts, Tables, Talk, mail (lecture seule) et une recherche sur tout   [GEÄNDERT]
- Rien de destructif : pas de suppression, tâches comprises ; pas de partage ; pas de déplacement, sauf celui d'une seule tâche quand l'administrateur active la modification des tâches ; rien en arrière-plan, pas de télémétrie
- Nouveau en 0.9.0 : lire les champs de l'application Profile Fields, en lecture seule et désactivé par défaut ; l'administrateur l'active ; chaque compte lit ses propres valeurs, tandis que le catalogue des champs, les valeurs des autres comptes et la recherche exacte par valeur de champ sont réservés aux administrateurs, ce que vérifie l'application Profile Fields elle-même   [NEU, ersetzt "Nouveau en 0.8.0"]
- Modifier des tâches existantes, désactivé par défaut : marquer comme terminée, rouvrir, modifier ou déplacer une tâche avec ses sous-tâches vers une autre liste ; l'administrateur l'active, et une tâche n'est modifiée que si elle n'a pas changé depuis sa lecture ; les tâches récurrentes ne sont pas modifiées, et aucune tâche n'est jamais supprimée
- Les fichiers joints à un message ChatGPT arrivent dans votre Nextcloud ; seuls les hôtes ChatGPT de confiance, et les envois n'écrasent jamais rien
- Modifier des fichiers texte existants, désactivé par défaut ; l'administrateur l'active, et un fichier n'est remplacé que s'il n'a pas changé entre-temps
- Les fichiers et dossiers portant l'étiquette collaborative kein-ki restent invisibles pour tout assistant ; occ mcp_connector:exclusion:check indique si l'étiquette est correctement configurée

Avec [Findling](https://apps.nextcloud.com/apps/findling), les résultats de recherche incluent le contenu de vos documents, numérisations comprises, avec exactement les droits de l'utilisateur qui demande.

### Enterprise

(ab hier unverändert bis zum Ende)
```

Diff Variante A gegen heute (info.xml):

```
alt 112: - Outils : fichiers (Office et PDF lus en Markdown), calendrier, tâches, notes, Deck, contacts, Tables, Talk, mail (lecture seule) et une recherche sur tout
neu    : - Outils : fichiers (Office et PDF lus en Markdown ; créer des dossiers, dossiers parents manquants compris, 10 au plus par appel, rien n'est écrasé), calendrier, tâches (chercher, lire et créer), notes, Deck, contacts, Tables, Talk, mail (lecture seule) et une recherche sur tout

alt 114: - Nouveau en 0.8.0 : créer des dossiers, dossiers parents manquants compris (10 au plus par appel, rien n'est écrasé) ; chercher, lire et créer des tâches
neu    : - Nouveau en 0.9.0 : lire les champs de l'application Profile Fields, en lecture seule et désactivé par défaut ; l'administrateur l'active ; chaque compte lit ses propres valeurs, tandis que le catalogue des champs, les valeurs des autres comptes et la recherche exacte par valeur de champ sont réservés aux administrateurs, ce que vérifie l'application Profile Fields elle-même
```

Variante B, Diff gegen heute (Zeile 112 bleibt wie heute):

```
alt 114: - Nouveau en 0.8.0 : créer des dossiers, dossiers parents manquants compris (10 au plus par appel, rien n'est écrasé) ; chercher, lire et créer des tâches
neu    : - Nouveau en 0.9.0 : (wie Variante A)
neu    : - Créer des dossiers, dossiers parents manquants compris (10 au plus par appel, rien n'est écrasé) ; chercher, lire et créer des tâches
```

Beleg Rechte: profile_fields.py Zeile 78 (eigene Werte), Zeile 98 (Feldkatalog), Zeile 131 (Werte anderer Konten), Zeile 38 (exakte Suche), nur ocs_get.

## 5. Prüfungen am Entwurf

Probelauf auf Kopien von info.xml im Scratchpad p35 (Variante A und B je als ganze Datei, das Repo-info.xml nur gelesen), mit den Prüffunktionen der Tests selbst (importiert aus tests/unit/test_exapp_env_setup.py und tests/contract/test_write_promise_truth.py):

- description_problems: leer (A und B). Damit: kein Backtick, keine Tabelle, kein Bild, keine Linie, kein HTML, mindestens zwei Absätze je Sprache, summary unter 128, kein verbotenes Wort.
- variable_problems: leer.
- FAQ-Marker (background/switch/disconnect/read only und DE/FR): alle vorhanden.
- claim_findings: keine verbotene Zusage.
- store_delete_problems und store_move_problems je Sprache: leer; Positivkontrolle "ein Punkt über Verschieben existiert" je Sprache wahr.
- Kein "RAG".
- Gegenprobe über dieselben Funktionen, nicht über das Muster der Umsetzung: ein gepflanzter Backtick in der DE-Zeile wird gemeldet; mit dem alten Punkt "no delete, no move, no share" und ohne "tasks are never deleted" meldet store_delete_problems einen Fehler.
- Dash-Prüfung (mit Positivkontrolle) dieser Datei: 0 Treffer.
- Abgleich: jede neue Zeile der Kopien info_A.xml und info_B.xml steht wörtlich in diesem Entwurf (6 von 6 je Variante).
- UMLAUT neue DE-Zeilen (3) geprueft=0 fehler=0 (keine Fundstelle von ae, oe, ue, ss; Positivkontrolle der Suche mit "Strasse Muellers" findet beide).
- FRANZ neue FR-Zeilen (3) geprueft=3 fehler=0 (vor jedem ":" und ";" ein Leerzeichen; Apostroph durchgehend gerade wie im übrigen info.xml, 0 typografische).

## 6. Längen und Empfehlung

| | heute | Variante A | Variante B |
|---|---|---|---|
| EN | 2096 | 2376 (+280) | 2383 (+287) |
| DE | 2306 | 2575 (+269) | 2585 (+279) |
| FR | 2502 | 2850 (+348) | 2862 (+360) |

Variante A ist in allen drei Sprachen kürzer (7 bis 12 Zeichen) bei gleicher Aussage und hält die Liste bei acht Punkten; empfohlen. Kosten von A: der Punkt "Tools" wird länger und trägt eine Klammer mit Strichpunkt. Variante B liest sich leichter, hat aber einen Punkt mehr.

## 7. Antwortform

`freigabe`, `aenderung: ...` oder `nein`, dazu `variante=A` oder `variante=B`.

# Kurzer Entwurf der Store-Texte für 0.9.0 (Plan 35-02, Owner-Entscheid 2026-11-20)

Owner 2026-11-20: "viel zu viel Text, es soll keine Doku sein, sondern auf die Doku in GitHub verlinken und nur die nötigen Informationen beinhalten." Der Entwurf 32340786 (lang) und die Variante "A kurz" sind damit überholt. info.xml und der Pin bleiben unverändert, bis der Owner diesen Entwurf freigibt.

Stand: HEAD 985c0ea8 (nach 35-10), info.xml Version 0.8.0, Pin "release 0.8.0".

## 1. Gates, die summary oder description heute halten

| Nr | Gate (Datei, Test) | verlangt | Herkunft | kurzer Text erfüllbar? | Empfehlung |
|---|---|---|---|---|---|
| G1 | test_store_texts_frozen.py: test_store_texts_are_the_six_expected_elements | genau 6 Store-Texte (summary/description je EN/DE/FR) in fester Reihenfolge | EXCL-F02, Phase 29 | ja | bleibt |
| G2 | test_store_texts_frozen.py: test_store_texts_are_unchanged_since_the_frozen_commit | SHA-256 der 6 Texte gleich EXPECTED_SHA256 | EXCL-F02; erneuert 0.4.0, 0.6.0, 0.8.0 | ja, Pin wird nach Freigabe erneuert | bleibt (Erneuerung in Task 3) |
| G3 | test_exapp_env_setup.py: description_problems über test_the_manifest_text_passes_its_own_gate | summary höchstens 128 Zeichen; description ohne Backtick, Tabelle, Bild, Linie, HTML; mindestens 2 Absätze je Sprache; Wort "archiv" nirgends im Elementtext | XSD l10n-string; 05-RESEARCH Pitfall 4 (zwei Render-Pfade); Vokabelregel des Projekts | ja | bleibt |
| G4 | test_exapp_env_setup.py: test_every_description_carries_the_answer_of_the_faq | Marker je Sprache: background/switch/disconnect/read only, Hintergrund/Schalter/trenn/nur lesen, arrière-plan/interrupteur/déconnect/lecture seule | 05-RESEARCH offene Frage 2 (FAQ-Antwort im Store-Text); 4. Marker SEC-01 (Mail nur lesen) | ja, kostet einen Halbsatz im ersten und dritten Punkt | bleibt |
| G5 | test_exapp_env_setup.py: test_no_description_names_a_blocked_mailbox | kein "archiv" in der description | Mail-Familie, Vokabelregel | ja | bleibt |
| G6 | test_exapp_env_setup.py: test_no_description_carries_the_rag_acronym | kein Wort "RAG" | Entscheid zur Store-Sprache (Leser entscheidet über klare Wörter) | ja | bleibt |
| G7 | test_exapp_env_setup.py: test_no_public_text_carries_a_forbidden_claim (claim_findings) | keine der vier Zusagen revisionssicher, AI-Act-konform, DSGVO-konform, SIEM-zertifiziert | AUDIT-06, D-v1.5-02, Plan 19-03 | ja | bleibt |
| G8 | test_exapp_env_setup.py: test_the_enterprise_paragraph_carries_its_markers_at_all_six_places (enterprise_section) | genau eine Überschrift "### Enterprise" je description, darunter "audit log", "off by default", "group policies" (DE Audit-Log, ab Werk aus, Gruppen-Policies; FR journal d'audit, désactivé par défaut, politiques de groupe), gleich wie in den 3 READMEs | AUDIT-06, Plan 19-08, T-19-31 (Abdriften zwischen 6 Stellen) | ja, aber nur mit Enterprise-Abschnitt; ein Satz reicht | bleibt; ohne Enterprise-Abschnitt müsste der Test die Store-Hälfte aufgeben (Owner-Entscheid) |
| G9 | test_exapp_env_setup.py: test_no_place_calls_the_audit_log_planned | keine Zeile mit "audit log" und "planned" zugleich im Enterprise-Abschnitt | AUDIT-06, Phase 18/19 | ja | bleibt |
| G10 | test_exapp_env_setup.py: variable_problems | kein leeres default in environment-variables (nicht Store-Text, aber im selben Lauf) | Pitfall 3 05-RESEARCH | unberührt | bleibt |
| G11 | test_write_promise_truth.py: test_the_store_description_names_the_task_delete_limit (store_delete_problems) | ein Punkt nennt Löschen zusammen mit Aufgaben (delet/lösch/suppr plus task/aufgabe/tâche) | EXAPP-13, Plan 34-05, E11 | ja | bleibt |
| G12 | test_write_promise_truth.py: Verschiebe-Test (store_move_problems plus Positivkontrolle) | es GIBT einen Punkt über Verschieben (Positivkontrolle), und jeder solche Punkt nennt die Aufgabe als Ausnahme | EXAPP-13, Plan 34-05 | ja, erzwingt aber den Verschiebe-Halbsatz | bleibt; wer ihn streichen will, muss die Positivkontrolle lockern (Owner-Entscheid) |
| G13 | test_tasks_spike.py: test_positive_control_names_each_of_the_six_places_a_hit_stands_in | zitiert "appinfo/info.xml", 69, "Nothing destructive..." nur als Literal | Phase 30 Spike | liest info.xml nicht | unberührt |

Geprüft: alle Testdateien unter tests/ nach `_localised(`, `store_description(`, `_store_texts`, `description_problems`, `enterprise_section`, `info.xml` und `"description"` durchsucht; weitere Fundstellen betreffen Routen, Variablen, occ-Beschreibungen oder Werkzeugschemas, nicht die Store-Texte. Das Gate aus 35-10 (test_tool_text_assurances.py) liest info.xml nicht (35-10 STORETEXT chatgpt_liest=nein).

Ergebnis: Der kurze Entwurf unten erfüllt alle Gates ohne Änderung an einem Test. Was er dafür mitnehmen muss: FAQ-Marker (G4), die Löschgrenze mit Aufgaben (G11), den Verschiebe-Halbsatz (G12) und einen Enterprise-Satz (G8).

## 2. summary (unverändert, sachlich richtig)

- EN (124): MCP server for Nextcloud: Claude, ChatGPT, n8n and other AI assistants read, search, create and edit, as the signed-in user.
- DE (126): MCP Server für Nextcloud: Claude, ChatGPT, n8n und andere KI-Assistenten lesen, suchen und bearbeiten als angemeldeter Nutzer.
- FR (126): Serveur MCP pour Nextcloud : Claude, ChatGPT, n8n et autres assistants IA lisent, cherchent et modifient, comme l'utilisateur.

## 3. description EN (Grundfassung)

```
What MCP Connector does:

- Claude, ChatGPT, n8n or your own agent work in Nextcloud as the signed-in user (OAuth sign-in); a per-account switch pauses access, one click can disconnect an assistant
- Areas: files (Office and PDF as Markdown), folders, calendar, tasks, notes, Deck, contacts, Tables, Talk, mail (read only), Profile Fields (optional) and one search across all of it
- No delete, tasks included; no share; no move except one task when the admin enables changing tasks; nothing in the background, no telemetry
- Creating works out of the box; changing existing text files and tasks is off by default, the admin enables it
- Requirements: Nextcloud 32 to 35 with AppAPI, runs as an External App

Documentation: [README on GitHub](https://github.com/street1983nk/nextcloud-mcp-connector/blob/main/README.md)

### Enterprise

Built-in audit log, off by default; group policies are next.
```

## 4. description DE (Grundfassung)

```
Was der MCP Connector kann:

- Claude, ChatGPT, n8n oder eigene Agenten arbeiten in Nextcloud als der angemeldete Nutzer (OAuth-Anmeldung); ein Schalter je Konto pausiert den Zugriff, ein Klick kann einen Assistenten trennen
- Bereiche: Dateien (Office und PDF als Markdown), Ordner, Kalender, Aufgaben, Notizen, Deck, Kontakte, Tables, Talk, Mail (nur lesen), Profile Fields (optional) und eine Suche über alles
- Kein Löschen, auch nicht von Aufgaben; kein Teilen; kein Verschieben, außer einer einzelnen Aufgabe, wenn der Admin das Ändern von Aufgaben freischaltet; nichts im Hintergrund, keine Telemetrie
- Anlegen geht ab Werk; das Ändern bestehender Textdateien und Aufgaben ist ab Werk aus, der Admin schaltet es frei
- Voraussetzungen: Nextcloud 32 bis 35 mit AppAPI, läuft als External App

Dokumentation: [README auf GitHub](https://github.com/street1983nk/nextcloud-mcp-connector/blob/main/README.de.md)

### Enterprise

Audit-Log eingebaut und ab Werk aus; als Nächstes kommen Gruppen-Policies.
```

## 5. description FR (Grundfassung)

```
Ce que sait faire le MCP Connector :

- Claude, ChatGPT, n8n ou vos propres agents travaillent dans Nextcloud comme l'utilisateur connecté (connexion OAuth) ; un interrupteur par compte suspend l'accès, un clic peut déconnecter un assistant
- Domaines : fichiers (Office et PDF en Markdown), dossiers, calendrier, tâches, notes, Deck, contacts, Tables, Talk, mail (lecture seule), Profile Fields (facultatif) et une recherche sur tout
- Pas de suppression, tâches comprises ; pas de partage ; pas de déplacement, sauf celui d'une seule tâche quand l'administrateur active la modification des tâches ; rien en arrière-plan, pas de télémétrie
- La création fonctionne dès l'installation ; la modification des fichiers texte et des tâches existants est désactivée par défaut, l'administrateur l'active
- Prérequis : Nextcloud 32 à 35 avec AppAPI, fonctionne comme External App

Documentation : [README sur GitHub](https://github.com/street1983nk/nextcloud-mcp-connector/blob/main/README.fr.md)

### Enterprise

Le journal d'audit est intégré et désactivé par défaut ; ensuite viendront les politiques de groupe.
```

## 6. Optionen (Owner-Frage)

Option K, kein-ki als Punkt direkt nach den Grenzen:

- EN: - Files and folders with the collaborative tag kein-ki stay invisible to every assistant
- DE: - Dateien und Ordner mit dem kollaborativen Tag kein-ki bleiben für jeden Assistenten unsichtbar
- FR : - Les fichiers et dossiers portant l'étiquette collaborative kein-ki restent invisibles pour tout assistant

Option F, Findling als Absatz vor der Dokumentationszeile:

- EN: With [Findling](https://apps.nextcloud.com/apps/findling), search also finds the contents of your documents, with the rights of the asking user.
- DE: Mit [Findling](https://apps.nextcloud.com/apps/findling) findet die Suche auch die Inhalte Ihrer Dokumente, mit den Rechten des fragenden Nutzers.
- FR : Avec [Findling](https://apps.nextcloud.com/apps/findling), la recherche trouve aussi le contenu de vos documents, avec les droits de l'utilisateur qui demande.

Was rausfällt (steht im README): Versionszeilen "Neu in", Detailgrenzen (ETag, höchstens 10 Ordner, wiederkehrende Aufgaben), ChatGPT-Dateiübernahme, Standalone-Weg ohne AppAPI, n8n-Satz, langer Enterprise-Absatz (OIDC seit 0.2.0), occ-Befehl zu kein-ki.

## 7. Längen der description (Zeichen)

| Sprache | heute | Grundfassung | mit K und F |
|---|---|---|---|
| EN | 2096 | 897 | 1132 |
| DE | 2306 | 1006 | 1251 |
| FR | 2502 | 1108 | 1377 |

## 8. Prüfungen

Geprüft auf Kopien von info.xml im Scratchpad p35 (Grundfassung und mit K und F, CRLF), mit den Prüffunktionen der Tests selbst:

- description_problems leer, variable_problems leer, summaries 124/126/126.
- FAQ-Marker alle vorhanden; Enterprise-Marker alle vorhanden, keine Zeile "audit log" plus "planned"; claim_findings leer; kein "RAG", kein "archiv".
- store_delete_problems und store_move_problems je Sprache leer, Positivkontrolle Verschieben wahr.
- Gegenproben über dieselben Funktionen: Backtick gemeldet; Grenzpunkt ohne Aufgaben gemeldet; Enterprise ohne "group policies" gemeldet.
- DASH 0 (Positivkontrolle ok).
- UMLAUT DE (15 Zeilen inkl. Optionen) geprueft=3 fehler=0: "Assistenten" (2x), "Voraussetzungen", alle echt.
- FRANZ FR (15 Zeilen inkl. Optionen) geprueft=15 fehler=0: Leerzeichen vor ":" und ";", Apostroph gerade wie im übrigen info.xml.
- Links: README.md, README.de.md, README.fr.md existieren auf main (gh api contents); apps.nextcloud.com/apps/findling antwortet 200.

Inhalt gegen Code und README:

- Kein Löschen, Verschieben nur tasks_move unter NC_MCP_TASKS_UPDATE: tests/contract/test_write_promise_truth.py (ändernde Werkzeuge genau files_update, tasks_complete, tasks_update, tasks_move).
- "Anlegen ab Werk": acht create-only-Werkzeuge im Standard (files_upload, files_create_folder, calendar_create_event, tasks_create, notes_create, deck_create_card, tables_create_row, talk_send), README.md Tools-Tabelle; keines davon in OPTIONAL_TOOLS (tests/contract/optional_surface.py).
- "Ändern bestehender Textdateien und Aufgaben ab Werk aus": OPTIONAL_TOOLS files_update (NC_MCP_FILES_UPDATE), tasks_complete/tasks_update/tasks_move (NC_MCP_TASKS_UPDATE).
- "Profile Fields (optional)": profile_fields_browse unter NC_MCP_PROFILE_FIELDS_READ, ab Werk aus.
- Nextcloud 32 bis 35, AppAPI, External App: wie der heutige Text (min/max-version unverändert).

Markdown-Links: angenommen, nicht live gemessen. Der heutige Store-Text trägt schon [Findling](...); der Docstring von description_problems nennt `a` in der Erlaubnisliste beider Pfade (Store: markdown plus bleach; Instanz: marked plus dompurify mit a). docs/store-submission.md (2026-08-22) belegt nur die Links aus `<website>`/`<documentation>`, nicht einen Link im Text. Zusätzlich verlinkt die Store-Seite die Doku ohnehin über `<documentation><user>` (docs/client-setup.md) und `<admin>` (docs/exapp-install.md) sowie `<website>`.

## 9. Antwortform

`freigabe`, `aenderung: ...` oder `nein`; dazu `kein-ki=ja|nein` und `findling=ja|nein`.

# README-Nachträge für Plan 31-06 (vom Owner freigegeben)

Freigabe: Owner, 13.11.2026 ("Go für beide"), auf den am 12.11.2026 vorgelegten Entwurf.
Umfang: `README.de.md` und `README.fr.md` bekommen den Abschnitt zum Abschalten von Tool-Bundles
und je zwei fehlende Tabellenzeilen. Quelle ist der Abschnitt "Switching tool bundles off" in `README.md`.

Zusätzlich freigegeben:

1. `files_update` in die Bundle-Liste (`files`) aller drei Sprachen aufnehmen, mit dem Zusatz
   "nur wenn aktiviert". Vorher am Code belegen, dass `files_update` mit dem Bundle `files`
   abgeschaltet wird; trifft das nicht zu, nichts eintragen und den Befund melden.
2. Netzfehler in der Ordnerkette (31-04b) und die Ablehnung von Ordnernamen mit Leerraum am Rand
   (31-05b) stehen nur in den drei CHANGELOGs, nicht in den READMEs.

## Deutsch: zwei Tabellenzeilen

Nach der Zeile `files_download`:

```markdown
| `files_read_as_markdown` | read | Eine DOCX-, XLSX-, PPTX- oder PDF-Datei, in Markdown umgewandelt, in Abschnitten |
```

Nach der Zeile `files_create_folder`:

```markdown
| `files_update` | conditional-update | Ersetzt eine bestehende UTF-8-Textdatei nur mit ihrem zuvor gelesenen ETag; nur verfügbar, wenn der Admin `NC_MCP_FILES_UPDATE` aktiviert |
```

## Deutsch: neuer Abschnitt (vor "Ordner ausnehmen: das Tag kein-ki")

```markdown
## Tool-Bundles abschalten

- Variable: `NC_MCP_DISABLED_TOOLS`, Bundle-Namen durch Komma getrennt, wird beim Start gelesen.
- Wo sie gesetzt wird: als Deploy-Umgebungsvariable der ExApp, entweder in den Deploy-Optionen
  des Installations- und Update-Dialogs oder auf der Kommandozeile:
  `occ app_api:app:register mcp_connector --env "NC_MCP_DISABLED_TOOLS=mail,calendar"`
  (bei einer bestehenden Installation vorher abmelden; die Verbindungen der Nutzer bleiben
  erhalten, der Container wird neu erstellt). Das Startprotokoll nennt die abgeschalteten Bundles.
- Standard: nicht gesetzt, jedes Bundle ist an.
- Beispiel: `export NC_MCP_DISABLED_TOOLS=mail,calendar`, nützlich, wenn ein zweiter MCP-Server
  schon Mail und Kalender anbietet und ein kleineres Modell die beiden verwechselt.
- Bundles und ihre Tools:
  - `calendar`: `calendar_list_events`, `calendar_create_event`
  - `chatgpt`: `search`, `fetch`
  - `contacts`: `contacts_search`
  - `context`: `prepare_context`
  - `deck`: `deck_browse`, `deck_create_card`
  - `files`: `files_search`, `files_list`, `files_read`, `files_download`,
    `files_read_as_markdown`, `files_upload`, `files_create_folder`
  - `mail`: `mail_browse`
  - `notes`: `notes_search`, `notes_read`, `notes_create`
  - `search`: `unified_search`
  - `tables`: `tables_browse`, `tables_create_row`
  - `talk`: `talk_browse`, `talk_send`
- Ein unbekannter Name oder alle Namen auf einmal stoppen den Server beim Start mit einer
  Meldung, die die gültigen Namen auflistet.
- Keine Zugriffskontrolle: `search`, `fetch` und `prepare_context` erreichen weiterhin die
  Inhalte eines abgeschalteten Bundles. Um Inhalte vom Assistenten fernzuhalten, dienen die
  Nextcloud-Berechtigungen, das Tag `kein-ki` oder `NC_MCP_FILES_ROOT`.
- ChatGPT-Konnektoren erwarten das Bundle `chatgpt` (`search`, `fetch`).
- Die ExApp deklariert die Variable und protokolliert beim Start, welche Bundles abgeschaltet sind.
```

## Französisch: zwei Tabellenzeilen

Nach der Zeile `files_download`:

```markdown
| `files_read_as_markdown` | read | Un fichier DOCX, XLSX, PPTX ou PDF converti en Markdown, par tranches |
```

Nach der Zeile `files_create_folder`:

```markdown
| `files_update` | conditional-update | Remplace un fichier texte UTF-8 existant uniquement avec son ETag lu auparavant ; disponible seulement si l'admin active `NC_MCP_FILES_UPDATE` |
```

## Französisch: neuer Abschnitt (an derselben Stelle wie im Deutschen, vor dem Abschnitt zum Tag kein-ki)

```markdown
## Désactiver des bundles d'outils

- Variable : `NC_MCP_DISABLED_TOOLS`, noms de bundles séparés par des virgules, lue au démarrage.
- Où la définir : comme variable d'environnement de déploiement de l'ExApp, soit dans les options
  de déploiement de la boîte de dialogue d'installation ou de mise à jour, soit en ligne de commande :
  `occ app_api:app:register mcp_connector --env "NC_MCP_DISABLED_TOOLS=mail,calendar"`
  (désenregistrer d'abord sur une installation existante ; les connexions des utilisateurs sont
  conservées, le conteneur est recréé). Le journal de démarrage nomme les bundles désactivés.
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
    `files_read_as_markdown`, `files_upload`, `files_create_folder`
  - `mail` : `mail_browse`
  - `notes` : `notes_search`, `notes_read`, `notes_create`
  - `search` : `unified_search`
  - `tables` : `tables_browse`, `tables_create_row`
  - `talk` : `talk_browse`, `talk_send`
- Un nom inconnu, ou tous les noms à la fois, arrête le serveur au démarrage avec un message
  qui énumère les noms valides.
- Ce n'est pas un contrôle d'accès : `search`, `fetch` et `prepare_context` atteignent toujours
  le contenu d'un bundle désactivé. Pour tenir un contenu à l'écart de l'assistant, utilisez les
  permissions Nextcloud, l'étiquette `kein-ki` ou `NC_MCP_FILES_ROOT`.
- Les connecteurs ChatGPT attendent le bundle `chatgpt` (`search`, `fetch`).
- L'ExApp déclare la variable et consigne au démarrage les bundles désactivés.
```

## Hinweise für die Umsetzung

- Schreibweise, Typografie (zum Beispiel Apostrophe und Leerzeichen vor Doppelpunkt im Französischen)
  und Zeilenlänge an den Bestand der jeweiligen README angleichen; der Inhalt bleibt wie freigegeben.
- Die Werkzeugzahl in den READMEs muss danach zur Tabelle passen (24 feste Werkzeuge, `files_update`
  nur wenn aktiviert); wie `README.md` das zählt, am Bestand ablesen.
- Keine Gedankenstriche (U+2013, U+2014), keine Emojis, deutsche Fassung mit echten Umlauten.

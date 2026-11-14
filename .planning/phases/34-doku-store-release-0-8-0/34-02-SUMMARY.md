---
phase: 34-doku-store-release-0-8-0
plan: 02
subsystem: doku
tags: [doc-04, readme, faktencheck, update-only]
requires: ["34-01", "34-04"]
provides:
  - "READMEs EN/DE/FR auf dem Faktenstand 0.8.0, inhaltsgleich"
  - "Prüfprotokoll raw/34-02-faktencheck.txt (FAKT-, PUNKT-, ZUSATZ-Zeilen)"
affects: [34-05, 34-06]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-02-faktencheck.txt
  modified:
    - README.md
    - README.de.md
    - README.fr.md
decisions:
  - "Punkt 7: README.de.md schreibt durchgehend 'Tools' (Mehrheit, auch Tabellenkopf, Abschnittsname und 'Tool-Aufruf' in Architektur); 'Werkzeug' kommt nicht mehr vor"
  - "DE/FR nennen das übersetzte Schalter-Label (vom Test SWITCH_LABELS gehalten) und zusätzlich den englischen Text der Oberfläche, weil das Admin-Formular nur englisch ausgeliefert wird (strings.py, kein l10n)"
  - "Der Satz 'A key that was never set is created by the same command without --update-only' in docs/exapp-install.md bleibt: im AppAPI-Quelltext stable32 bis stable35 belegt"
  - "EN 'writable shared' und FR 'partagée/accessible en écriture' bleiben; nur DE wird natürlicher ('mit Schreibrecht')"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 4
---

# Phase 34 Plan 02: Faktencheck der READMEs in drei Sprachen Summary

Alle Aussagen der drei READMEs gegen Registry, Code und info.xml geprüft (Protokoll mit Beleg je Aussage); EN, DE und FR nennen jetzt Ordner und Aufgaben in der Einleitung, die occ-Zeile mit `--update-only` beim Aufgabenschalter, die Befundlinks, und DE/FR haben die in EN vorhandenen Fakten (FILES_ROOT, Upload beliebiger Größe, Token-Austausch) nachgezogen.

## Commits

| Task | Commit | Text |
|------|--------|------|
| 1+2 | 746e4df | docs(34-02): readme fact check of all three languages for 0.8.0 |

Task 1 (Protokoll) ging laut Plan mit Task 2 in einen Commit.

## Geänderte nutzersichtbare Sätze

- **Einleitung** EN "files and folders, calendar, tasks, notes, ...", DE "Dateien und Ordner, Kalender, Aufgaben, ...", FR "fichiers et dossiers, agenda, tâches, ...".
- **Schalter NC_MCP_TASKS_UPDATE**, alle drei: neue Zeile "On a running installation the admin changes the switch with `occ app_api:app:config:set mcp_connector tasks_update --value on --update-only`, see docs/exapp-install.md#write-switches" (DE "Auf einer laufenden Installation ändert der Admin den Schalter mit ...", FR "Sur une installation en service, l'administrateur change l'interrupteur avec ...").
- **Befundlinks** nach der Tabelle, alle drei: wie Ordner- und Aufgaben-Tools auf Nextcloud 32 und 35 antworteten und was ungemessen blieb (Beispiel: neuer Ordner auf nur lesbarem externem Speicher), Links auf docs/folder-evidence.md und docs/tasks-evidence.md.
- **Nur DE/FR** (in EN schon vorhanden): "oder App-Passwort" / "ni de mot de passe d'application"; Label-Zusatz "in der Oberfläche englisch "Allow changing existing tasks"" / "en anglais dans l'interface : « Allow changing existing tasks »"; `files_upload` "Binär-Upload beliebiger Größe" / "envoi binaire de toute taille"; `NC_MCP_FILES_ROOT` im Clients-Beispiel plus Erklärsatz; Token-Austausch-Satz mit Link docs/token-exchange.md im Abschnitt Enterprise.
- **Nur DE**: "schreibbar geteilte Aufgabenliste" -> "mit Schreibrecht geteilte Aufgabenliste"; Tabelle `tasks_move` "genannte beschreibbare Liste" -> "genannte Liste mit Schreibrecht"; Enterprise "Werkzeugaufruf ... das Werkzeug" -> "Tool-Aufruf ... das Tool".

## Neun Punkte aus 31-06

1, 2, 5, 6 erledigt vorher (bestätigt: Rechtetabellen-Test drei Parameter grün, Legende mit vier Stufen deckt files_create_folder als create-only ab, FR 0 typografische Apostrophe). 3, 4, 7 in 34-02 behoben. 8 und 9 (CHANGELOGs, test_changelog_translations.py) an 34-06 übergeben (Zeile UEBERGABE im Protokoll).

## Zusatzpunkte der Hauptsitzung

1. **Wortlaut "schreibbar geteilt":** DE an zwei Stellen geändert (siehe oben). EN "writable shared" (README, privacy.md, threat-model.md) und FR "partagée en écriture"/"accessible en écriture" sind natürlich und gleichbedeutend; unverändert. docs/*.de.md enthalten den Ausdruck nicht.
2. **Satz zu `--update-only` in docs/exapp-install.md:73-74: hält, bleibt.** Quelle nextcloud/app_api (nur gelesen), `lib/Command/ExAppConfig/SetConfig.php`: ohne `--update-only` meldet ein vorhandener Schlüssel "already exists. Use --update-only flag." mit Exit 1, ein fehlender wird über `setAppConfigValue` angelegt: stable32 (514f8e4) und stable33 (a1230aa) Zeilen 57-63, stable34 (747c8c6) Zeilen 57-63, stable35 (918fcc1) Zeilen 56-62. `lib/Service/ExAppConfigService.php::setAppConfigValue` legt an: stable32 bis 34 `mapper->insert` (Zeile 69), stable35 `appConfig->setValueString` (Zeile 82). Nebenbefund aus derselben Datei: mit `--update-only` auf einem nie gesetzten Schlüssel antwortet occ "config ... not found" (Exit 1); nicht in die Doku aufgenommen, nur vermerkt.
3. **Hausregel README-Faktencheck:** 27 Werkzeuge im Standard und 31 mit allen Schaltern (check_tool_budget), zehn Familien und zwölf Bundle-Namen aus `bundle_names()`, Rechtetabelle per Test über drei READMEs, Bundle-Listen gleich, Schalterabschnitt mit occ-Zeile. PER_LIST_TIMEOUT (3.0 s): die READMEs nennen kein Zeitbudget der Aufgabensuche, daher nicht neu eingeführt. "das ETag" geprüft: `grep "die ETag\|der ETag" README.de.md` leer.

## Gates (vor dem Commit, alle Exit 0)

- pytest unit+contract: 8204 passed, 35 skipped
- Teilauswahl Rechtetabelle/Schalter/Schreibzusage: 57 passed; Rechtetabelle und Schaltertest je drei Parameter: 6 passed
- check_tool_budget: 22198 Bytes / 31 Werkzeuge (Budget 26000), 18770 Bytes / 27 Werkzeuge, unverändert
- ruff check grün; ruff format --check: 407 Dateien formatiert
- pyright: 0 errors, 0 warnings
- vulture: Exit 0
- Strich-Prüfung: Positivkontrolle Exit 0; README.md, README.de.md, README.fr.md Exit 1; keine Emojis (Exit 1)
- Diff-Beweis: Basis-Positivkontrolle grün; `git diff --stat $B -- src/` ohne andere Datei als `server/__init__.py` (aus 34-01)
- Protokoll: 9 PUNKT-Zeilen, keine FAKT-Zeile mit falsch/fehlt-in-de/fehlt-in-fr

UMLAUT README.de.md geprueft=8 fehler=0 (Assistenten, Passwort, gemessenen, neue, neuer, ungemessen, zuerst: echt; value: Code `--value`)

Französisch: Leerzeichen vor `:` und `;` in allen neuen Zeilen, Guillemets wie im Bestand mit Leerzeichen, 0 typografische Apostrophe.

## Deviations from Plan

1. **[Rule 2] Label der Oberfläche:** DE/FR nannten als Schalter-Label nur eine Übersetzung, die es in der Oberfläche nicht gibt (Formular nur englisch). Ergänzt um den englischen Text; das übersetzte Label bleibt, weil es der Test `SWITCH_LABELS` hält (D-33-01). Bitte vom Owner bestätigen, ob das übersetzte Label auf Dauer bleiben soll.
2. **[Rule 2] Token-Austausch in DE/FR:** der Abschnitt Enterprise hatte den Satz mit Link auf docs/token-exchange.md nicht; nachgezogen (fehlte im Plan-Interface, gefunden im Faktencheck).
3. **[Rule 2] App-Passwort in DE/FR:** "or an app password" fehlte; nachgezogen.
4. Die occ-Zeile steht mit `--value on` (Einschalten ist der Fall im README); docs/exapp-install.md zeigt das Protokollbeispiel mit `off`.
5. `tasks_create`-Zeile ist gegenüber dem Code vereinfacht (Fall Elternaufgabe in eigener ungeteilter Liste fehlt); keine falsche Zusage, daher `stimmt` und unverändert.

## Known Stubs

Keine.

## Self-Check: PASSED

- raw/34-02-faktencheck.txt vorhanden, README.md/.de.md/.fr.md geändert
- Commit 746e4df im Log

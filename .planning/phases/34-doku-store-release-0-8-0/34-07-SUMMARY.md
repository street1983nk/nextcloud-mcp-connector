---
phase: 34-doku-store-release-0-8-0
plan: 07
subsystem: release-volltest
tags: [volltest, nc35, sprache, abnahme, files_update, tasks, labels]
requires: ["34-06"]
provides:
  - "raw/34-07-volltest.txt: Volltest-Protokoll (VOLLTEST je Werkzeug an/aus, ZAEHLUNG, SPRACHE je Fläche)"
  - "Abnahmeskript ruft files_update mit frischem und veraltetem ETag"
  - "Ein Label je Schreibschalter in Formular und Manifest (Test)"
  - "Stiltest für zusammengesetzte Attribute in tools/list"
affects: [34-08]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-07-volltest.txt
    - tests/contract/test_tool_text_style.py
  modified:
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
    - appinfo/info.xml
    - tests/unit/test_exapp_admin_settings.py
    - scripts/acceptance_all_tools.py
    - README.de.md
    - README.fr.md
    - docs/hardening.de.md
    - docs/hardening.fr.md
    - src/mcp_connector/server/reg_mail.py
    - src/mcp_connector/server/reg_search.py
    - docs/conference-talk.md
    - docs/privacy.md
    - docs/tasks-evidence.md
    - docs/threat-model.md
    - docs/uninstall.md
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-freigaben.txt
decisions:
  - "Owner: Volltest auf nc35 komplett (option-a), Lücke files_update im Abnahmeskript schließen und neu laufen (option-a)"
  - "Owner: \"Allow editing existing text files\" ist das eine Label von NC_MCP_FILES_UPDATE, auch im Manifest"
  - "Owner: Volltest abgenommen; Stilhinweise A (Bindestrich in tools/list) und B (read-only als Attribut) sofort umgesetzt"
  - "Store-Text unverändert, store-text-2 entfällt; Pin unverändert (deckt nur summary/description direkt unter info)"
metrics:
  completed: 2026-11-14
  tasks: 5
---

# Phase 34 Plan 07: Volltest 0.8.0 auf Nextcloud 35 und Sprachdurchsicht Summary

Alle 31 Werkzeuge von 0.8.0 haben live auf Nextcloud 35 geantwortet (über die ExApp-Kette 31 mit Schaltern an, 27 aus; stdio 31 und 27, kein FAIL), jede nutzersichtbare Fläche in DE/EN/FR ist durchgesehen (8 Fehler behoben, 0 offen), und der Owner hat abgenommen.

## Commits

| Commit | Inhalt |
|--------|--------|
| 70e7d05 | CHANGELOG DE/FR nennen das englische Admin-Label "Allow changing existing tasks" mit Glosse |
| 5a5aa8b | Lauf 1, angehalten: das Abnahmeskript rief files_update nie auf |
| e37a3fb | test (RED): ein Label je Schreibschalter in Formular und Manifest |
| c223311 | info.xml display-name von NC_MCP_FILES_UPDATE = "Allow editing existing text files" (GREEN) |
| 098f699 | test: Abnahmeskript ruft files_update mit frischem und veraltetem ETag |
| dd83679 | Sprachkorrekturen README.de/fr, hardening.de/fr |
| f9fa8f0 | Volltest-Protokoll Lauf 2 |
| bc26060 | Sprachdurchsicht |
| 8dfb026 | store-text-2 entfällt |
| a5310d4 | test (RED): Stiltest tools/list (rot nur die 6 Fundstellen der 3 Texte) |
| 9025f17 | fix: "Comma-separated", "space-separated", "Percent-encode" in tools/list (GREEN) |
| 23189a5 | docs: "read-only" als Attribut (14 Stellen in 5 Dateien) |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer und ohne Schließwörter, nur lokal. STATE, ROADMAP und REQUIREMENTS nicht angefasst.

## Freigaben

```
FREIGABE volltest-nc35 antwort=option-a datum=2026-11-14
FREIGABE luecke-files-update antwort=option-a datum=2026-11-14
FREIGABE label-files-update antwort=allow-editing-existing-text-files datum=2026-11-14
FREIGABE store-text-2 antwort=entfaellt datum=2026-11-14
FREIGABE volltest antwort=abgenommen datum=2026-11-14
```

## Volltest (raw/34-07-volltest.txt)

```
WERKZEUGE anzahl=31 tasks=ja familien=10 aendernd=tasks_complete,tasks_update,tasks_move
WERKZEUGE nach_aus anzahl=27 tasks=ja familien=10 aendernd=keine
ZAEHLUNG an=31 erwartet_an=31 aus=27 erwartet_aus=27 gleich=ja
SPRACHE gesamt fehler=0 (8 Fehler gefunden und behoben, 0 offen; 2 Stilhinweise offen beim Owner)
DOCKER ende eigene=0
```

- ExApp 0.8.0 auf nc35 registriert (Image sha256:a3b60b04...), Rückweg als `127.0.0.1:5000/mcp_connector:0.7.2-vor34`. Beide Schalter am Ende aus.
- Beide stdio-Läufe enden mit Exit 3: PREREQ Mail-Volltext (GreenMail nach dem Neustart leer, die Mail-App selbst antwortet 500), wie der Plan es zulässt.
- BASELINE alice (1/31/0/0) und bob (2/1/0/0) vorher gleich nachher in beiden Läufen.
- Die beiden Stilhinweise der Sprachdurchsicht (A, B) hat der Owner bei der Abnahme umsetzen lassen (9025f17, 23189a5); danach ist nichts mehr offen.

## Geänderte Zeichenketten nach der Abnahme

- unified_search `providers`: "Comma separated provider ids" -> "Comma-separated provider ids"
- mail_browse `filter`: "space separated type:value" -> "space-separated type:value"
- mail_browse Beschreibung: "Percent encode a filter value" -> "Percent-encode a filter value"
- docs: "read only share/list/lists/shared list/mounted database/one" -> "read-only ..." (conference-talk 2, privacy 1, tasks-evidence 7, threat-model 2, uninstall 2); prädikative Fälle, die Kategorie "read only and write", occ-Ausgaben und wörtliche Rohzeilen unverändert

## Gates (Endstand, alle Exit 0)

- pytest unit+contract: 8217 passed, 35 skipped
- check_tool_budget: 22198 Bytes, 31 Werkzeuge mit allen Schaltern an (Budget 26000), Standard 18770 Bytes und 27 Werkzeuge; mail_browse 1237 Bytes (Decke 1400). Zahlen unverändert, weil der Bindestrich ein Leerzeichen ersetzt; keine Neuverankerung
- ruff check grün, ruff format --check 408 Dateien
- pyright (latest): 0 errors
- vulture: Exit 0
- Ganze Suite (vor den Stil-Änderungen, nach den Label-Änderungen): 8202 passed, 35 skipped, Exit 0
- Dash-Prüfung mit Positivkontrolle: 0 Treffer
- Store-Text-Pin: grün, unverändert

UMLAUT README.de.md geprueft=0 fehler=0
UMLAUT CHANGELOG.de.md geprueft=0 fehler=0
UMLAUT docs/hardening.de.md geprueft=1 fehler=0 ("lassen", echt)

## Deviations from Plan

1. **[Rule 4, Owner] Lücke im Abnahmeskript.** `files_update` hatte keinen Schritt (Lauf 1 Exit 1, "never called"). Angehalten, Owner entschied: Schritt ergänzen, neu laufen.
2. **[Owner] Label des Dateien-Schalters.** info.xml sagte "Allow updating existing files", das Formular "Allow editing existing text files"; angeglichen, testgetrieben. Der RED-Commit e37a3fb trug außerdem drei pyright-Fehler im neuen Testcode, behoben im GREEN-Commit c223311.
3. **[Owner] Produktcode außerhalb der zwei benannten Stellen.** `reg_mail.py` und `reg_search.py` geändert (nur Bindestriche in Werkzeugtexten, Owner-Auftrag bei der Abnahme); der Diff-Check von 34-RULES Abschnitt 4 nennt sie deshalb.
4. **files_update-Schlüssel fehlte nach der Neuregistrierung.** `--update-only` meldete "not found"; der Schlüssel wurde ohne die Option angelegt.
5. **Kalenderobjekte landeten trotz `X-NC-CalDAV-No-Trashbin` im Papierkorb**; danach aus dem Papierkorb gelöscht. Kalenderobjekte von Deck-Karten (403) bleiben wie Notiz, Dateien, Tabellenzeile und Talk-Nachricht im Testkonto (nicht in der BASELINE).
6. **Sprachdurchsicht:** jede in Phase 34 hinzugefügte Zeile, die CHANGELOG-Blöcke, die Store-Texte und tools/list ganz gelesen, der Rest der Dateien maschinell geprüft; unveränderte README-Zeilen früherer Releases nicht erneut Zeile für Zeile.
7. **Ein Gate-Lauf wurde wegen Speichermangel vom Harness gestoppt;** nach Owner-Freigabe seriell fortgesetzt (pyright, vulture, Dash, Pin).

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche. T-34-07-01 (Geheimnisprüfung, 0 Treffer, Talk-Raum maskiert), -02 (Schalter aus, 27 belegt), -03 (Fremdcontainer- und RAM-Gate vor jedem Start, eine Instanz) umgesetzt.

## Self-Check: PASSED

Alle zwölf Commits im Log; raw/34-07-volltest.txt, tests/contract/test_tool_text_style.py und die FREIGABE-Zeilen vorhanden; die Verify-Zeilen des Plans (VOLLTEST, kein urteil=FAIL, DOCKER ende eigene=0, ZAEHLUNG gleich=ja, SPRACHE gesamt fehler=0, FREIGABE volltest, FREIGABE store-text-2) greifen.

---
phase: 35-release-0-9-0-profile-fields
plan: 02
subsystem: store-text
tags: [release, store-text, info-xml, pin]
requires: [35-01, 35-10]
provides:
  - appinfo/info.xml mit kurzer description EN/DE/FR (Owner-Entscheid 2026-11-20)
  - Pin "release 0.9.0" in tests/unit/test_store_texts_frozen.py
  - raw/35-02-store-entwurf.md (langer Entwurf, überholt) und raw/35-02-store-entwurf-kurz.md (kurzer Entwurf mit Gate-Tabelle)
  - FREIGABE store-text und ANTWORT in raw/35-freigaben.txt
affects: [35-03, 35-04, 35-05, 35-08]
tech-stack:
  added: []
  patterns: [Gate-Probelauf auf Kopien von info.xml mit den Prüffunktionen der Tests selbst]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-02-store-entwurf.md
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-02-store-entwurf-kurz.md
  modified:
    - appinfo/info.xml
    - tests/unit/test_store_texts_frozen.py
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
decisions:
  - "Owner 2026-11-20: Store-Text kurz, keine Doku, Link auf das README der jeweiligen Sprache; ersetzt Owner-Entscheid 2 (Zeile New in 0.9.0) und die Variante A kurz"
  - "Owner 2026-11-20: kein-ki-Punkt bleibt, Findling-Absatz bleibt wörtlich wie bisher, Enterprise-Einzeiler und Verschiebe-Halbsatz bleiben, alle Store-Text-Gates unverändert"
  - "summaries unverändert (sachlich richtig)"
metrics:
  duration: ca. 2 h über zwei Tage (mit drei Owner-Runden)
  completed: 2026-11-20
---

# Phase 35 Plan 02: Store-Texte für 0.9.0 Summary

Die drei Store-Beschreibungen sind auf eine kurze Fassung mit Link auf das README der jeweiligen Sprache geschnitten (EN 2096 auf 1167, DE 2306 auf 1282, FR 2502 auf 1423 Zeichen), mit kein-ki-Punkt und dem bisherigen Findling-Absatz wörtlich; der Pin steht auf "release 0.9.0".

## Verlauf und Owner-Entscheide

1. 2026-11-19, Task 1: langer Entwurf nach Owner-Entscheid 2 (Zeile "New in 0.9.0" zu Profile Fields, Ordner und Aufgaben in die normale Liste, Varianten A/B), Commit 32340786, raw/35-02-store-entwurf.md.
2. 2026-11-20: Owner wählt "A, Neu-Zeile kürzer"; gekürzte Neu-Zeile DE/EN/FR geprüft und vorgelegt (kein Commit).
3. 2026-11-20: Owner: "viel zu viel Text, es soll keine Doku sein, sondern auf die Doku in GitHub verlinken und nur die nötigen Informationen beinhalten." Kurzer Entwurf mit Gate-Inventar, Commit b0e8777e, raw/35-02-store-entwurf-kurz.md.
4. 2026-11-20 (AskUserQuestion, wörtlich in raw/35-freigaben.txt): "Nein der Text zu Findling soll bleiben"; Optionen "kein-ki-Tag, Findling-Hinweis"; Gates "Beide bleiben (Empfohlen)"; Doku-Link "README je Sprache (Empfohlen)". Umgesetzt: Kurzfassung plus kein-ki-Punkt plus der bisherige Findling-Absatz wörtlich (aus info.xml gelesen, nicht abgetippt), Tests unverändert.

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 | langer Entwurf (überholt) | 32340786 docs(35-02): draft of the store texts for 0.9.0 |
| 1b | kurzer Entwurf mit Gate-Tabelle | b0e8777e docs(35-02): short draft of the store texts for 0.9.0 |
| 2 | FREIGABE store-text und ANTWORT angehängt | mit Task 3 |
| 3 | info.xml, Pin, Freigabezeilen | 999dd3d1 docs(35-02): store texts for 0.9.0 as approved by the owner |

## Gate-Tabelle (Store-Texte)

| Nr | Gate | Herkunft | Ergebnis |
|---|---|---|---|
| G1 | test_store_texts_frozen: sechs Elemente | EXCL-F02 | bleibt, grün |
| G2 | test_store_texts_frozen: Hash | EXCL-F02 | erneuert auf release 0.9.0 |
| G3 | description_problems (Form, 128 Zeichen, 2 Absätze, archiv) | XSD, 05-RESEARCH Pitfall 4 | bleibt, grün |
| G4 | FAQ-Marker | 05-RESEARCH Frage 2, SEC-01 | bleibt, grün |
| G5 | kein blockiertes Postfach | Mail-Familie | bleibt, grün |
| G6 | kein "RAG" | Store-Sprache | bleibt, grün |
| G7 | verbotene Zusagen | AUDIT-06, D-v1.5-02 | bleibt, grün |
| G8 | Enterprise-Marker an sechs Stellen | AUDIT-06, 19-08, T-19-31 | bleibt (Owner), grün mit Einzeiler |
| G9 | Audit-Log nicht "planned" | AUDIT-06 | bleibt, grün |
| G10 | variable_problems | Pitfall 3 | unberührt |
| G11 | Löschgrenze nennt Aufgaben | EXAPP-13, 34-05, E11 | bleibt, grün |
| G12 | Verschieben nur mit Aufgabe, Positivkontrolle | EXAPP-13, 34-05 | bleibt (Owner), grün |
| G13 | test_tasks_spike Literal | Phase 30 | liest info.xml nicht |

## Längen der description (Zeichen)

| Sprache | 0.8.0 | 0.9.0 |
|---|---|---|
| EN | 2096 | 1167 |
| DE | 2306 | 1282 |
| FR | 2502 | 1423 |

summaries unverändert: EN 124, DE 126, FR 126.

## Prüfungen

- Probelauf auf der Kopie (danach als info.xml übernommen, CRLF): description_problems leer, variable_problems leer, FAQ- und Enterprise-Marker vollständig, keine Zeile Audit-Log plus planned, claim_findings leer, store_delete_problems und store_move_problems leer, Positivkontrolle Verschieben wahr, kein RAG, kein archiv.
- Gegenproben über dieselben Funktionen: Backtick gemeldet, Grenzpunkt ohne Aufgaben gemeldet, Enterprise ohne group policies gemeldet.
- PIN rot_vor_erneuerung=ja (1 failed, 1 passed gegen das neue info.xml mit altem Hash).
- DASH 0 (Positivkontrolle ok). UMLAUT info.xml-DE neu geprueft=3 fehler=0 (Assistenten 2x, Voraussetzungen). FRANZ info.xml-FR neu geprueft=8 fehler=0.
- Links: README.md, README.de.md, README.fr.md auf main vorhanden (gh api contents); Findling-Seite 200.
- git diff --numstat: appinfo/info.xml 27/45 (nur die drei description-Blöcke), test_store_texts_frozen.py 8/3.
- Diff-Beweis src/: unverändert durch diesen Plan.

Angenommen, nicht gemessen: dass der Store Markdown-Links im Text rendert (Grund: bisheriger Findling-Link, Erlaubnisliste a in beiden Render-Pfaden laut description_problems). Prüfung bei Schritt 8 des Runbooks (35-09) auf der Store-Seite.

## Gates (35-RULES Abschnitt 3)

Gelaufen mit info.xml und Pin des Commits, alle Exit 0:

- pytest unit+contract: 8338 passed, 35 skipped
- check_tool_budget: Standard 27 Werkzeuge 18606 Bytes, alle Schalter 32 Werkzeuge 22933 Bytes, Budget 26000, größtes files_upload 1377 (gleich BUDGET nachher aus raw/35-10-tooltexte.txt)
- ruff check: All checks passed; ruff format --check: 417 Dateien
- pyright (latest): 0 errors, 0 warnings
- vulture: 0 Funde

## Deviations from Plan

1. [Owner-Entscheid] Inhalt weicht vom Plan (Zeile "New in 0.9.0", Ordner und Aufgaben in der Liste) ab: der Owner hat am 2026-11-20 die kurze Fassung ohne Versionszeile entschieden; Profile Fields steht als "optional" in der Bereichsliste. Plan-Verify `grep -q "New in 0.9.0" appinfo/info.xml` trifft daher nicht zu und ist durch den Owner-Entscheid überholt; die Abwesenheit der 0.8.0-Zeilen gilt weiter.
2. Zweiter Entwurfs-Commit b0e8777e (nicht im Plan), auf Anweisung des Koordinators.
3. Session-Trailer des Harness weggelassen (35-RULES Abschnitt 2).

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche. T-35-02-01: keine Rechte-Aussage zu Profile Fields mehr im Store-Text außer "optional"; Owner-Freigabe vor dem Schreiben. T-35-02-02: Beschreibungsgates grün. T-35-02-03: test_write_promise_truth.py unverändert grün.

## Self-Check: PASSED

- Dateien vorhanden: raw/35-02-store-entwurf.md, raw/35-02-store-entwurf-kurz.md, appinfo/info.xml, tests/unit/test_store_texts_frozen.py.
- Commits im Branch: 32340786, b0e8777e, 999dd3d1.
- Scratchpad p35 am Planende gelöscht.

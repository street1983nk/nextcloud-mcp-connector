---
phase: 34-doku-store-release-0-8-0
plan: 05
subsystem: doku
tags: [exapp-13, doc-05, store-text, pin]
requires: ["34-01", "34-02"]
provides:
  - "Store-Texte EN/DE/FR für 0.8.0 wie vom Owner freigegeben"
  - "SHA-256-Pin auf release 0.8.0"
  - "Löschgrenzen- und Verschiebetest der drei Store-Beschreibungen"
affects: [34-06, 34-10]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-05-store-entwurf.md
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-05-inventar.txt
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-freigaben.txt
  modified:
    - appinfo/info.xml
    - tests/unit/test_store_texts_frozen.py
    - tests/contract/test_write_promise_truth.py
decisions:
  - "Owner-Freigabe 2026-11-14: freigabe-mit-aenderung (DE 'kein Löschen, auch nicht von Aufgaben'), Punkt 0.7.0 als Variante B ohne Version, kein discussion-Element, summaries unverändert"
metrics:
  completed: 2026-11-14
  tasks: 3
  files: 6
---

# Phase 34 Plan 05: Store-Text 0.8.0 Summary

Die drei Store-Beschreibungen nennen Aufgaben, die Löschgrenze (auch keine Aufgabe), das Verschieben nur einer Aufgabe mit Admin-Schalter, die Neuerungen von 0.8.0 (Ordner, Aufgaben suchen/lesen/anlegen, Aufgaben ändern ab Werk aus) und behalten den ChatGPT-Upload ohne Versionsnummer; der Pin steht auf release 0.8.0.

## Commits

| Task | Commit | Text |
|------|--------|------|
| 1 | e017d9c | docs(34-05): draft of the store texts for 0.8.0 |
| 3 (RED) | 75acf0c | test(34-05): store descriptions name the task delete limit |
| 3 (GREEN) | 76937a6 | docs(34-05): store texts for 0.8.0 as approved by the owner |

Task 2 (Checkpoint): Owner-Antwort als `FREIGABE store-text antwort=freigabe-mit-aenderung discussion=kein datum=2026-11-14` in raw/34-freigaben.txt (mit RED-Commit committet).

## RED-Commit: rote Tests

Nur die neuen Tests (6 failed, 8206 passed, 35 skipped); alle anderen Gates grün:

- `test_the_store_description_names_the_task_delete_limit[en|de|fr]`
- `test_every_store_point_about_moving_names_the_task_exception[en|de|fr]`

Grün im RED-Lauf: die zwei Gegenproben über den festen alten Punkt "Nothing destructive: no delete, no move, no share; ...".

## Gates (vor GREEN-Commit, alle Exit 0)

- pytest unit+contract: 8212 passed, 35 skipped
- check_tool_budget: 22198 Bytes / 31 Werkzeuge (Budget 26000), 18770 Bytes / 27 Werkzeuge, unverändert
- ruff check grün; ruff format --check: 407 Dateien formatiert
- pyright: 0 errors, 0 warnings
- vulture: Exit 0
- Strich-Prüfung: Positivkontrolle Exit 0; info.xml, beide Testdateien, Entwurf, Inventar, Freigaben Exit 1
- Diff-Beweis: Basis-Positivkontrolle grün, `src/` ohne andere Datei als `server/__init__.py` (aus 34-01)
- Neuer Hash 4e510fec45ca96e341b53968a31c6cc5c84fd2d3d683a7135122381b281ba902, gleich bei LF- und CRLF-Checkout geprüft
- Kein `<discussion>`-Element; 3 ERLEDIGT-Zeilen in raw/34-05-inventar.txt (69 -> 69, 89 -> 91, 109 -> 113)

UMLAUT appinfo/info.xml geprueft=1 fehler=0 (vertrauenswürdige: echt)

## Deviations from Plan

1. Der Punkt "New in 0.7.0" wurde nach Owner-Entscheid nicht gestrichen, sondern als Punkt ohne Versionsnummer gekürzt behalten (Variante B), nach dem Punkt zum Ändern von Aufgaben.
2. Der Verschiebetest nutzt für EN ein Wortmuster (`\bmov(e|es|ed|ing)\b`), damit "remove" nicht als Verschieben zählt; alle Vergleiche nach casefold, weil DE "Löschen" großschreibt.
3. Während des ersten RED-Gatelaufs lag info.xml kurz geändert im Arbeitsbaum; vor dem RED-Commit wiederhergestellt. Das Ergebnis (Pin grün, nur die sechs neuen Tests rot) zeigt, dass der Lauf das alte info.xml gelesen hat.

## Known Stubs

Keine.

## Self-Check: PASSED

- Entwurf, Inventar, Freigaben, info.xml, Pin-Test vorhanden; `FROZEN_AT = "release 0.8.0"`
- Commits e017d9c, 75acf0c, 76937a6 im Log

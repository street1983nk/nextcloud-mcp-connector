---
phase: 30-mess-spike-aufgaben-und-ordner
plan: 05
subsystem: messung / Abschluss des Messberichts, Übergabe der Abbruchkriterien an die Phasen 31 bis 33, Owner-Entscheid E15
tags: [spike, bericht, owner-entscheid, e15, admin-schalter, abbruchkriterien, annahmen, report-check]
requires:
  - 30-01 (Messskript, Bericht mit festen Überschriften, MESS-01 und MESS-02)
  - 30-02 (MESS-05, Browser-Sitzung, Inventar und Kette von NC_MCP_FILES_UPDATE)
  - 30-03 (MESS-06: MOVE, Löschmatrix, Ergebniswort nach E13)
  - 30-04 (MESS-03 und MESS-04, Fixtures)
provides:
  - scripts/tasks_spike.py (Block report-check; Funktionen assumption_rows, missing_assumptions, abort_rows, e15_recommendation, headings_intact, has_dash)
  - docs/spike-tasks.md (Abschnitte 8 bis 11, Owner-Entscheid in 10.4, Kopfblock abgeschlossen)
  - .planning/PROJECT.md (Key Decision E15, Ergebniswort bei E13)
  - .planning/REQUIREMENTS.md (E15 als Scope-Entscheidung, TMOD-01, TMOD-03, TMOD-07, TMOD-08 nach dem Entscheid, Verweis auf Abschnitt 8)
  - .planning/ROADMAP.md (Phase 33: E15 entschieden, Zeile "Aus Phase 30")
affects: [31, 32, 33, 34]
tech-stack:
  added: []
  patterns:
    - "ein Bericht prüft sich selbst gegen seine Rohdateien: Zitate, Annahmen, Abbruchzeilen, Ergebniswort, Striche, Geheimnisse, Kopfblock (report-check, Exit 1 bei Abweichung)"
    - "die Regel hinter einer Empfehlung steht als getestete Funktion fest, bevor die Messwerte eingesetzt werden; die Entscheidung steht an genau einer Stelle (Bericht 10.4)"
    - "eine Owner-Antwort wird wörtlich, mit Datum und Kanal festgehalten; was der Orchestrator daraus liest, steht als Lesart daneben und nicht als Zitat"
key-files:
  created: []
  modified:
    - scripts/tasks_spike.py
    - tests/unit/test_tasks_spike.py
    - vulture_whitelist.py
    - docs/spike-tasks.md
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
decisions:
  - "E15 entschieden am 2026-11-12 (Owner, Claude-Code-Sitzung, vom Orchestrator übermittelt, wörtlich \"Empfehlungen übernehmen\"): Option empfehlung, also eigener Admin-Schalter für die ändernden Aufgaben-Werkzeuge, ab Werk aus, nach dem Vorbild NC_MCP_FILES_UPDATE"
  - "A15, mit derselben Antwort vom 2026-11-12: wiederkehrende Aufgaben bleiben für ändernde Zugriffe abgelehnt"
  - "A16, mit derselben Antwort vom 2026-11-12: das Abhaken einer Elternaufgabe hakt ihre Unteraufgaben mit ab, wie die Tasks-App; TMOD-03 ist nachgezogen"
  - "A21, mit derselben Antwort vom 2026-11-12: Unteraufgaben ziehen beim Verschieben mit und werden mitgelöscht; TMOD-07 und TMOD-08 sind nachgezogen"
  - "Nicht festgelegt: welche Werkzeuge der Schalter im Einzelnen umfasst, sein Name und seine Texte; das klärt die discuss-phase von Phase 33"
  - "Kein Abbruchkriterium ist ausgelöst (MESS-01 nein, MESS-05 nein, MESS-06 MOVE nein, Löschwort wiederherstellbar): die Phasen 31, 32 und 33 samt TMOD-07 und TMOD-08 sind planbar"
  - "Stand der Annahmen: 14 belegt, 5 widerlegt (A5, A9, A16, A17, A19), keine als Ganzes ungemessen; maßgeblich ist Bericht Abschnitt 8"
metrics:
  duration: "nicht gemessen; zwei Aufträge am 2026-11-12 (Task 1 und Task 2), dazwischen der Owner-Checkpoint"
  completed: 2026-11-12
  tasks: 2
  files: 7
---

# Phase 30 Plan 05: Messbericht abgeschlossen, Übergabe an die Phasen 31 bis 33, Owner-Entscheid E15 Summary

Der Messbericht führt alle neunzehn Annahmen mit Status, kein Abbruchkriterium ist ausgelöst, und der Owner hat E15 am 2026-11-12 entschieden: die ändernden Aufgaben-Werkzeuge bekommen einen eigenen Admin-Schalter, ab Werk aus, nach dem Vorbild `NC_MCP_FILES_UPDATE`.

## Der Entscheid

- **Datum:** 2026-11-12. **Kanal:** Claude-Code-Sitzung, Antwort vom Orchestrator übermittelt.
- **Wörtliche Antwort des Owners:** "Empfehlungen übernehmen"
- **Gewählte Option:** `empfehlung` (Empfehlung aus Bericht 10.3 übernehmen). Die Empfehlung lautete nach der vorab festgelegten Regel "eigener Schalter", Auslöser S1, kein ungemessener Auslöser.
- **Lesart des Orchestrators, kein Zitat:** der Plural deckt die Empfehlung zu E15 und die drei Vorschläge zu A15, A16 und A21.
- **Abbruchkriterien:** keines ausgelöst, deshalb gibt es dazu keine Antwort des Owners.

| Punkt | Vorschlag, wie vorgelegt | Folge |
|---|---|---|
| A15 | die Vorgabe "ablehnen" bleibt bestehen | TMOD-01 im Wortlaut unverändert |
| A16 | dem Verhalten der Tasks-App folgen und mit abhaken | TMOD-03 nachgezogen, Out-of-Scope-Punkt entfernt |
| A21 | der Connector folgt dem Gemessenen (Kinder ziehen mit und werden mitgelöscht) | TMOD-07 und TMOD-08 nachgezogen |

Nicht festgelegt hat der Owner, welche Werkzeuge der Schalter im Einzelnen umfasst. Es gilt der Wortlaut der vorgelegten Option ("für die ändernden Aufgaben-Werkzeuge, ab Werk aus").

## Was die Phasen 31 bis 33 jetzt wissen

- **Phase 31:** MESS-01 nicht ausgelöst, planbar. Übergabe in Bericht 9.1.
- **Phase 32:** planbar. Übergabe in Bericht 9.2.
- **Phase 33:** MESS-05 und MOVE nicht ausgelöst, Löschwort "wiederherstellbar": TMOD-07 und TMOD-08 sind planbar. Übergabe in Bericht 9.3, Entscheid in 10.4, Zeile "Aus Phase 30" in ROADMAP.md.

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | bc230d2 (Tests, RED), fbfe0b6 (Block report-check, Empfehlungsregel), b233406 (Bericht 8 bis 11) | Bericht abgeschlossen, Entscheidungsgrundlage E15 |
| 2 | 81fdeff | Owner-Entscheid in Bericht 10.4, PROJECT.md, REQUIREMENTS.md, ROADMAP.md |

Prüfläufe nach Task 2, alle Exit 0: verify-Befehl des Plans, `--block report-check` (acht Zeilen PRUEFUNG mit ergebnis=ok, 1245 Zitate, 0 fehlend), `--block secret-scan` (50 Dateien, 0 Funde), `pytest tests/unit tests/contract`, `scripts/check_tool_budget.py`, `ruff check .`, `ruff format --check .`, `pyright`, `vulture`. Unter `src/` ist nichts geändert.

## Geänderte Stellen in Task 2

- **docs/spike-tasks.md:** Abschnitt 10.4 (Datum, Antwort, Option, Lesart, die drei Punkte, was offen bleibt); Kopfblock-Status "abgeschlossen, Owner-Entscheid E15 vom 2026-11-12"; in 9.3 vier Verweise auf 10.4 (Wiederholung, Unteraufgaben beim Abhaken, Unteraufgaben beim Verschieben und Löschen, E15).
- **.planning/PROJECT.md:** neue Zeile E15 in Key Decisions; Outcome von E13 um das Ergebniswort ergänzt; Fußzeile.
- **.planning/REQUIREMENTS.md:** E15 in die Tabelle der Scope-Entscheidungen, Unterabschnitt der offenen Entscheidung entfernt; TMOD-01, TMOD-03, TMOD-07, TMOD-08 (siehe Abweichungen); Out of Scope; Verweiszeile unter der Tabelle Annahmen.
- **.planning/ROADMAP.md:** Phase 33, Punkt E15 ersetzt und Zeile "Aus Phase 30".

## Deviations from Plan

Task 1 wurde in einem früheren Auftrag ausgeführt und vom Orchestrator geprüft; Abweichungen dort sind diesem Auftrag nicht bekannt und hier nicht aufgeführt.

### Auf Anweisung des Orchestrators über den Plan hinaus (Task 2)

**1. TMOD-03 nach A16 nachgezogen.** Der letzte Satz lautete "hakt Unteraufgaben nicht mit ab, sofern MESS-05 nichts anderes ergibt" und sagt jetzt, dass die Unteraufgaben mit abgehakt werden, mit Verweis auf den Entscheid.

**2. TMOD-07 und TMOD-08 nach A21 nachgezogen.** Der Plan sieht vor, dass TMOD-07 bei positivem Ergebniswort unverändert bleibt. Geändert ist je genau der Halbsatz zu den Unteraufgaben (TMOD-07: mitlöschen statt ablehnen; TMOD-08: "die Kinder ziehen mit" statt "ablehnen oder die Kinder ziehen mit").

**3. TMOD-01 um einen Satz ergänzt.** "Jeder ändernde Zugriff trifft genau die eine genannte Aufgabe" widerspricht A16 und A21; der neue Schlusssatz nennt die Unteraufgaben als einzige Ausnahme, mit Verweis auf den Entscheid.

**4. Out of Scope in REQUIREMENTS.md.** Der Punkt "Unteraufgaben beim Abhaken der Elternaufgabe mit abhaken" ist entfernt und im Absatz "Nicht hier" mit Verweis genannt. Dazu ein Absatz "Stand nach dem Mess-Spike" mit Ergebniswort und Stand von TMOD-07 und TMOD-08 (der Plan nennt ihn im Frontmatter als Artefakt, die action regelt nur den negativen Fall).

**5. Bericht 9.3.** Vier Stellen, die "offen" oder "nicht entschieden" sagten, verweisen jetzt auf 10.4; der Plan nennt nur 10.4 und den Kopfblock.

### Bewusst nicht geändert, aber im Widerspruch zum Entscheid

- **ROADMAP.md, Phase 33, Erfolgskriterium 1** ("Unteraufgaben bleiben dabei unberührt") widerspricht A16. Der Plan lässt Erfolgskriterien nur mit freigegebenem Wortlaut ändern; der Widerspruch steht in der Zeile "Aus Phase 30" und ist vor der Planung von Phase 33 nachzuziehen.
- **PROJECT.md:** die Zeile E13 nennt in der Begründung "Elternaufgabe mit Unteraufgaben abgelehnt", der Abschnitt Out of Scope "mehrere Aufgaben je Aufruf". Der Plan sagt für PROJECT.md "sonst nichts ändern"; DOC-05 (Phase 34) zieht die Schreibzusage ohnehin nach.
- **REQUIREMENTS.md, Out of Scope:** "Mehrere Aufgaben in einem Aufruf ändern" steht weiter dort; gemeint ist der Aufruf mit mehreren genannten Aufgaben, die Ausnahme für Unteraufgaben steht in TMOD-01.
- **MESS-03 und MESS-04** stehen in REQUIREMENTS.md weiter ohne Haken; Plan 30-04 hat sie gemessen, aber nicht abgehakt. Dieser Plan hakt nur MESS-06 ab.

## Was ungemessen blieb

Dieser Plan hat nichts gemessen. Die Sammlung steht in docs/spike-tasks.md, Abschnitt 11.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche. T-30-26: wörtliche Antwort mit Datum und Option in Bericht, PROJECT.md, REQUIREMENTS.md und hier; die Requirements sind nur an den genannten Stellen und mit Verweis auf den Entscheid geändert. T-30-27 und T-30-29: report-check und secret-scan Exit 0 nach der Änderung. T-30-28: die Entscheidung steht allein in 10.4, die Lesart des Orchestrators ist als Lesart gekennzeichnet. T-30-30: Ergebniswort "wiederherstellbar", TMOD-07 bleibt im Umfang. Kein Push, kein Tag, kein Kommentar in #32 oder #44, kein Docker-Lauf, keine Installation.

## Self-Check: PASSED

- Dateien vorhanden: docs/spike-tasks.md, .planning/PROJECT.md, .planning/REQUIREMENTS.md, .planning/ROADMAP.md, scripts/tasks_spike.py
- Commits vorhanden: bc230d2, fbfe0b6, b233406, 81fdeff

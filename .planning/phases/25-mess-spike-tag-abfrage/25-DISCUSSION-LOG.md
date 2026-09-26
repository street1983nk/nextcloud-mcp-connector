# Phase 25: Mess-Spike Tag-Abfrage - Discussion Log

**Date:** 2026-09-26
**Mode:** default (interactive), 4 Bereiche, alle vom Owner ausgewaehlt

## Bereich 1: NC-Versions-Matrix

**Frage:** Wie decken wir NC 32-34 ab?
Optionen: Sequenziell live (Empfehlung) / Nur 35 live + Quelltext-Beleg / Alle parallel
**Antwort:** Sequenziell live.

**Frage:** Welche Messungen laufen auf 32-34, welche nur auf 35?
Optionen: Versionsabhaengiges auf 32-34 (Empfehlung) / Volle Matrix ueberall
**Antwort:** Versionsabhaengiges auf 32-34 (App-aus, 412, REPORT-Grundform), Rest nur nc35.

## Bereich 2: Latenz-Messaufbau

**Frage:** Datenbestand fuer 1/100/5000 getaggte Knoten?
Optionen: Synthetisch + Extremfall PR #64298 (Empfehlung) / Nur kleiner Baum
**Antwort:** Synthetisch + Extremfall.

**Frage:** Harte Schwelle fuer Designumschwenk?
Optionen: 1 s bei 5000 (Empfehlung) / Keine Schwelle / Andere Schwelle
**Antwort:** 1 s bei 5000, darueber Owner-Checkpoint.

## Bereich 3: Checkpoint-Regime

**Frage:** Wann schaut der Owner drauf?
Optionen: Nach kritischen Messungen (Empfehlung) / Erst am Ende
**Antwort:** Nach den kritischen Messungen (Notes, App-aus, Latenz), vor Ableitungen.

## Bereich 4: Beleg-Ablage

**Frage:** Wo landet der Messbericht?
Optionen: Intern in .planning (Empfehlung) / Oeffentlich unter docs/
**Antwort:** Intern in .planning/phases/25-*.

## Nebenstrang (nicht Phase 25)

Waehrend der Discussion meldete sich Saket7002 auf Design-Issue #9 (files_update).
Owner-Entscheid im selben Gespraech: Daniel ist einverstanden, Saket baut;
Maintainer-Antwort mit den vier Design-Antworten wurde entworfen, auf Owner-Wunsch
ohne den Daniel-Satz gepostet. Gehoert zur files_update-Spur, nicht zu v1.7.

## Deferred Ideas

Keine neuen; die vier offenen v1.7-Designfragen bleiben an Phase 26/27.

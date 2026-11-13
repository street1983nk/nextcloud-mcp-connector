---
phase: 33-aufgaben-aendern
plan: 01c
subsystem: messung
tags: [tasks, caldav, kette, etag, chain_cap]
requires: ["33-01b"]
provides:
  - "KETTE-, ETAGFORM-, MESSWERT- und OWNERFRAGE-Zeilen in raw/33-01-messung.txt"
  - "docs/tasks-evidence.md Abschnitt '## Measurements before the modifying tools'"
affects: [33-02, 33-04, 33-05, 33-06]
tech-stack:
  added: []
  patterns: ["Ausgabe erst in den Scratchpad, Geheimnisprüfung, dann ins Rohprotokoll", "Fremd-Container-Prüfung zwischen den Messreihen"]
key-files:
  created:
    - .planning/phases/33-aufgaben-aendern/33-01c-SUMMARY.md
  modified:
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt
    - docs/tasks-evidence.md
decisions:
  - "chain_cap=50 bleibt: langsamste ganze Kette 3,688 s (nc32, move, Tiefe 1), Budget 8 s gegen Grenze 30 s (D-33-10 bestätigt)"
  - "etag_nach_veraendertem_text=fehlt: ändert der Server den Text beim Speichern, trägt die 204 keine ETag; das Werkzeug muss neu lesen"
  - "OWNERFRAGE entfällt: keiner der vier Auslöser greift"
metrics:
  completed: 2026-11-13
  tasks: 4
---

# Phase 33 Plan 01c: Kettenkosten auf 35 und 32, ETag-Form nach verändertem Text Summary

Eine Kette mit 50 Nachfahren kostet auf nc35 und Nextcloud 32 für PUT und MOVE je rund 2 s (Maximum 3,688 s), damit bleibt chain_cap=50; ein PUT, dessen Text der Server verändert, antwortet ohne ETag; keine Abweichung, keine Owner-Frage.

## Werte für die Folgepläne

Wörtlich aus raw/33-01-messung.txt (auch die aus 33-01 und 33-01b):

```
FREIGABE zustand=option-a datum=2026-11-13 umfang=nc35+nc32 quelle=owner-antwort-checkpoint-33-01-task-3
ENTSCHEID wiederoeffnen_kinder=bleiben quelle=M1 (D-33-05 bestätigt, kein Auslöser für 33-01c Task 4)
ENTSCHEID entfernen_due=zeile-weg quelle=M2
ENTSCHEID entfernen_start=zeile-weg quelle=M2
ENTSCHEID entfernen_description=leer quelle=M2 rohzeile=DESCRIPTION:
ENTSCHEID entfernen_parent=zeile-weg quelle=M2
ENTSCHEID entfernen_priority=zeile-weg quelle=M2 (wie D-33-07)
ENTSCHEID entfernen_tags=zeile-weg quelle=M2 (wie D-33-07)
ENTSCHEID pflegefelder_entfernen=DTSTAMP,LAST-MODIFIED
ENTSCHEID cancelled_kette=unberuehrt quelle=CANCELLED kette (wie D-33-14)
ENTSCHEID cancelled_direkt=abhaken-und-oeffnen abhaken=STATUS:COMPLETED,PERCENT-COMPLETE:100,COMPLETED(UTC) oeffnen=STATUS:NEEDS-ACTION,COMPLETED und PERCENT-COMPLETE entfernt pflegefelder=DTSTAMP,LAST-MODIFIED (wie D-33-14)
ENTSCHEID etag_nach_veraendertem_text=fehlt quelle=ETAGFORM nc35 (fall=ohne-prodid: der Server ändert den Text beim Speichern, text_gleich_gesendet=nein, die Antwort 204 trägt keine ETag; fall=lf und fall=uid-case speichert er unverändert und antwortet mit ETag gleich GET)
MESSWERT kette_max_gesamt_s=3.688 quelle=KETTE nc32 modus=move tiefe=1 lauf=1 (über nc35 und nc32, beide Modi, beide Tiefen, je 5 Läufe; größter Wert auf nc35: 2.466 s, move tiefe=3)
MESSWERT chain_cap=50 regel=derive_budget(max_gesamt_s)<=30 budget_s=8 quelle=nc35+nc32 (D-33-10 bestätigt)
MESSWERT kette_antwort_ids=50 (gleich chain_cap)
OWNERFRAGE entfaellt grund=keine-abweichung
```

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 | M-3 (vier Reihen je 5 Läufe) und M-4 auf nc35, Rückbau, nc35 gestoppt | 95cce2e |
| 2 | M-3 auf Nextcloud 32 (option-a), Rückbau, gestoppt | e3d88f1 |
| 3 | ENTSCHEID/MESSWERT-Zeilen, Abschnitt im Beleg, volle Gates | 66ac378 |
| 4 | Auslöser geprüft, `OWNERFRAGE entfaellt grund=keine-abweichung` | 92b4ea3 |

## Messwerte

| Instanz | Modus | Tiefe | min ms | median ms | max ms |
|---|---|---|---|---|---|
| nc35 | put | 1 | 2037 | 2080 | 2164 |
| nc35 | put | 3 | 2051 | 2074 | 2199 |
| nc35 | move | 1 | 2063 | 2095 | 2173 |
| nc35 | move | 3 | 2077 | 2103 | 2466 |
| nc32 | put | 1 | 1935 | 1947 | 1964 |
| nc32 | put | 3 | 1920 | 1961 | 2454 |
| nc32 | move | 1 | 1961 | 1991 | 3688 |
| nc32 | move | 3 | 2016 | 2043 | 2135 |

Alle PUT 204, alle MOVE 201. M-4 (nc35): `ohne-prodid` ohne ETag im Kopf, `lf` und `uid-case` mit ETag gleich GET.

## Rückbau und Baseline

- nc35: `BASELINE alice calendars=1 objekte=31`, `bob calendars=2 objekte=1`, vorher gleich nachher; je Lauf 51 Objekte ohne Papierkorb gelöscht, Listen gelöscht, Papierkorb 0, Reste 0.
- nc32: `alice calendars=1 objekte=3`, `bob calendars=2 objekte=1`, vorher gleich nachher; gleicher Rückbau.
- Am Planende läuft kein eigener und kein fremder Container.

## Deviations from Plan

1. Docker-Gate: vor dem ersten nc32-Start lief der fremde Container `avs-phpcheck-17b2` (Parallelsitzung) und der RAM lag bei 3,99 GB; das Gate brach vor jedem Start ab. Nach 5 Minuten (erste Prüfung) war er weg, Cache geleert, zweiter Anlauf mit 4,14 GB. Der erste Anlauf steht eingerückt im Rohprotokoll. Zwischen den nc32-Reihen wurde zusätzlich auf fremde Container geprüft (keiner).
2. RAM-Gate vor nc35 und nc32 je einmal mit Cache-Leeren nach 33-RULES Abschnitt 5 (Docker leer).
3. nc32 über `tasks_measure.py up --instance nc32` gestartet (nur `nc-mcp-exapp-nc` und `nc-mcp-exapp-caddy`, `docker start`), wie in 32-10; für Messungen unter Impersonation reicht das.
4. Geheimnisprüfung meldet nur Kontonamen (alice, bob) in BASELINE-, RUECKBAU- und PAPIERKORB-Zeilen, keine Geheimnisse (wie 33-01b).
5. Eine Protokollzeile `DOCKER planende ... fremde=` war leer, auf `fremde=keine` korrigiert (Commit der SUMMARY).

## Gates

- pytest unit+contract: 6480 passed, 35 skipped
- check_tool_budget: 18770 Bytes, 27 Werkzeuge, Budget 22000
- ruff check, ruff format --check, pyright (0 Fehler), vulture: grün
- TASK-01-Diff gegen 33-BASE leer, Gegentreffer in docs/tasks-evidence.md; `src/` unverändert

## Known Stubs

Keine.

## Self-Check: PASSED

Commits 95cce2e, e3d88f1, 66ac378, 92b4ea3 im Log; Abschnitt im Beleg und alle Zeilen im Protokoll vorhanden; keine eigene Instanz läuft.

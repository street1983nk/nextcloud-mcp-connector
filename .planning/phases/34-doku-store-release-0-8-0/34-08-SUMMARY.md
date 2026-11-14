---
phase: 34-doku-store-release-0-8-0
plan: 08
subsystem: release-vorlauf
tags: [release-notiz, issue-entwuerfe, push, ci]
requires: ["34-07"]
provides:
  - "raw/34-08-release-notes.md: Release-Notiz v0.8.0, englische Faktenliste, vom Owner freigegeben"
  - "raw/34-08-issue-32.md, raw/34-08-issue-44.md: Antwortentwürfe mit deutscher Übersetzung, nichts gepostet"
  - "raw/34-08-push.txt: PRUEFUNG vor dem Push und CI-Zeilen je Job"
affects: [34-09]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-08-release-notes.md
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-08-issue-32.md
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-08-issue-44.md
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-08-push.txt
  modified:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-freigaben.txt
decisions:
  - "Owner: Texte ok und pushen, mit einer Korrektur der Release-Notiz (\"No tool deletes anything.\")"
  - "Issue-Entwürfe postet der Owner nach dem Store-Release"
metrics:
  completed: 2026-11-14
  tasks: 3
---

# Phase 34 Plan 08: Release-Notiz, Issue-Entwürfe, Push und CI Summary

Release-Notiz und die Antwortentwürfe für #32 und #44 liegen vor und sind vom Owner gesehen; der Branch ist nach Freigabe gepusht (f464455..7866c51) und alle acht Jobs des PR #48 sind auf 7866c51 grün, einschließlich canary-nc35.

## Commits

| Commit | Inhalt |
|--------|--------|
| cbbbbc4 | Release-Notiz und Antwortentwürfe #32/#44 |
| b18471d | Owner-Antwort auf die Push-Frage |
| 7866c51 | Prüfung aller Commits vor dem Push |
| 120df3c | CI des Release-Stands (lokal, geht mit 34-09) |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer und ohne Schließwörter. STATE, ROADMAP und REQUIREMENTS nicht angefasst.

## Freigaben

```
FREIGABE push-branch antwort=push datum=2026-11-14
```

## Prüfung vor dem Push

```
PRUEFUNG vor=push-branch bereich=origin/plan/v1.8-tasks-080..HEAD commits=48 autor_committer_fremd=0 trailer=0 closes_woerter=0
```

Positivkontrolle mit gepflanzten Zeilen ("Signed-off-by: a", "resolved #3"): 2 Treffer. origin/main ist Vorfahr von HEAD. Push ohne force durch die Hauptsitzung.

## CI auf 7866c51 (je ein Lauf, alle final)

| Plan-Name | Angezeigter Jobname | Lauf | Ergebnis |
|-----------|---------------------|------|----------|
| unit | unit | 43576923068 | success |
| image | image | 43576923068 | success |
| exapp | exapp | 43576923068 | success |
| canary-nc35 | canary-nc35 | 43576923068 | success |
| integration | integration | 43576923068 | success |
| codeql | CodeQL (python) | 43576923108 | success |
| reuse | REUSE licensing lint | 43576923108 | success |
| pip-audit | pip-audit over the locked set | 43576923108 | success |

## Deviations from Plan

1. **Jobnamen in security.yml weichen ab.** GitHub zeigt "CodeQL (python)", "REUSE licensing lint" und "pip-audit over the locked set"; im Protokoll stehen die angezeigten Namen (Zuordnung oben), wie der Plan es vorsieht. Die automatische Verify-Zeile des Plans sucht `^CI codeql`, `^CI reuse`, `^CI pip-audit` und greift deshalb für diese drei nicht; inhaltlich sind alle drei grün und final.
2. **Owner-Korrektur der Release-Notiz** ("No tool deletes anything.") vor dem Push übernommen.

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche. T-34-08-01 und -02 durch die PRUEFUNG mit Positivkontrolle, T-34-08-03 durch Protokoll nur mit Job, Ergebnis und Run-Id.

## Self-Check: PASSED

Vier Commits im Log; drei Entwürfe und raw/34-08-push.txt vorhanden; FREIGABE push-branch antwort=push, PRUEFUNG vor=push-branch mit 0/0/0 und acht CI-Zeilen mit conclusion=success final=ja vorhanden.

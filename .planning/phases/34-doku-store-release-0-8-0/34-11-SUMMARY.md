---
phase: 34-doku-store-release-0-8-0
plan: 11
subsystem: release-nachweise
tags: [runbook, nachweise, push, issues]
requires: ["34-10"]
provides:
  - "docs/store-submission.md: Zeilen Schritte 1-7 und Schritt 8 für 0.8.0"
  - "raw/34-11-nachweise.txt: NACHWEIS-Zeilen, Gates, PRUEFUNG, CI-MAIN"
affects: []
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-11-nachweise.txt
  modified:
    - docs/store-submission.md
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-freigaben.txt
decisions:
  - "Owner: Nachtrag pushen (FREIGABE push-runbook antwort=push)"
  - "Owner: Issue-Antworten durch Claude posten und #32/#44 schließen (FREIGABE post-issues, close-issues)"
metrics:
  completed: 2026-11-14
  tasks: 3
---

# Phase 34 Plan 11: Store-Nachweise, Runbook-Nachtrag und Übergabe Summary

Alle Nachweise aus Runbook Schritt 8 stimmen für 0.8.0 (Detailseite, Asset 302/200 mit 62491 B, OCI-Index amd64+arm64, Tag 0.8.0, Autor-Mail gleich, Katalog nach Regeneration 0.8.0), der Runbook-Nachtrag ist nach Owner-Freigabe auf main (00525cb) und die CI dort grün.

## Commits

| Commit | Inhalt |
|--------|--------|
| aa72ca0 | docs(store): release record of 0.8.0 (Executor; Gates 8217 passed, 35 skipped, ruff, pyright 0, vulture, Budget, Dash) |
| 37e78af | Owner-Antworten zu den Issue-Kommentaren |
| (2 Commits) | Owner-Antwort Push, PRUEFUNG 10 Commits 0/0/0 |
| 00525cb | = origin/main = origin/plan/v1.8-tasks-080 |
| (folgend) | Katalog nach Regeneration, CI-MAIN, diese SUMMARY (lokal) |

## Nachweise

- Erster Durchlauf 09:05Z: Katalog noch 0.7.3 (Cache, Last-Modified 08:30:14Z), alles andere 0.8.0.
- Nach Regeneration (appapi_apps.json Last-Modified 09:15:16Z): Releases 0.8.0, 0.7.3, 0.7.2.
- CI-MAIN auf 00525cb: CI 43580117707, Security 43580117724, Scorecard 43580117713, alle success.

## Übergabe an den Owner

- Abweichend vom Plan hat der Owner das Posten an Claude gegeben: Antworten auf #32 (issuecomment-6874963457) und #44 (issuecomment-6874963631) gepostet, danach beide Issues auf Owner-Wort als completed geschlossen.
- Offen: Audit-Grund "unspecified" bei veraltetem ETag; Tag-Alias no-ai als eigene Phase nach 0.8.0 (Schreibweise fragen); Forum-Post zurückgestellt (bis PII Redaction und Audio & Video Search fertig).
- Die Runbook-Zeile Schritt 8 sagt noch "re-measure after its next one"; die Nachmessung (0.8.0) steht im Rohprotokoll und kann beim nächsten Runbook-Eintrag nachgezogen werden.

## Deviations from Plan

1. Testzahl 8217 statt 8212 (34-06 maß vor den Tests aus 34-07; Baum außerhalb .planning gleich dem Tag).
2. Pin der Store-Texte stand in keinem Rohprotokoll; gemessen (4e510fec...) und als PIN-Zeile protokolliert.
3. Runbook-Zeilen enthalten wie die Vorbilder das Auslassungszeichen U+2026.
4. Issue-Antworten durch Claude statt Owner gepostet (Owner-Anweisung).

## Known Stubs

Keine.

## Self-Check: PASSED

Runbook enthält "Steps 1 to 7 are done for 0.8.0" und "Step 8 for 0.8.0"; NACHWEIS autor gleich=ja; FREIGABE push-runbook antwort=push; PRUEFUNG vor=push-runbook 0/0/0; origin/main..00525cb = 0.

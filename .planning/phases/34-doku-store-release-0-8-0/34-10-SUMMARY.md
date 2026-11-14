---
phase: 34-doku-store-release-0-8-0
plan: 10
subsystem: store
tags: [signatur, store-submit]
requires: ["34-09"]
provides:
  - "mcp_connector-0.8.0.tar.gz.sig (512 B) am Release v0.8.0, Verified OK"
  - "0.8.0 im Nextcloud App Store (HTTP 201)"
affects: [34-11]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-10-store.txt
  modified:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-freigaben.txt
decisions:
  - "Owner: signieren und hochladen (FREIGABE signatur)"
  - "Owner: über store-submit.yml einreichen (FREIGABE submit antwort=workflow)"
metrics:
  completed: 2026-11-14
  tasks: 4
---

# Phase 34 Plan 10: Signatur und Store-Einreichung 0.8.0 Summary

Das heruntergeladene Asset ist mit dem App-Schlüssel signiert, gegen das Zertifikat geprüft (Verified OK, Gegenprobe schlägt fehl), die .sig hängt am Release, und der Store hat die Einreichung über store-submit.yml mit HTTP 201 angenommen.

## Protokoll (raw/34-10-store.txt)

- DOWNLOAD 62491 B, SHA256 im Protokoll; gleich der ASSET-Zeile aus 34-09.
- SIGNATUR Verified OK, 512 B; SIG-UPLOAD ja.
- SUBMIT weg=workflow run=43578762697 http=201.
- Store-Seite nennt 0.8.0.

## Deviations from Plan

1. Hauptsitzung führte den Plan selbst aus. Die Freigabe-Antwort heißt `signieren-und-hochladen` statt `signieren` (Wortlaut der Owner-Auswahl).
2. SIGNATUR- und SUBMIT-Zeilen standen zuerst in raw/34-09-release.txt; in raw/34-10-store.txt verschoben, SHA256 dafür aus einem zweiten Download der öffentlichen URL neu berechnet.
3. Commit-Text der Signatur `docs(34-10): signature of the store archive` statt des Planwortlauts.
4. Scratchpad (Asset, .sig, pub.pem) gelöscht; die Base64-Signatur stand nur in einer Shell-Variable.

## Known Stubs

Keine.

## Self-Check: PASSED

FREIGABE signatur und submit vorhanden, `SIGNATUR verify=Verified OK`, .sig am Release, `SUBMIT ... http=201`, kein privater Schlüssel unter raw/.

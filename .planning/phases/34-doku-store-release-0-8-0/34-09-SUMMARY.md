---
phase: 34-doku-store-release-0-8-0
plan: 09
subsystem: release
tags: [merge, tag, release-workflow]
requires: ["34-08"]
provides:
  - "main = b4b6518, PR #48 MERGED per Fast-Forward"
  - "Tag v0.8.0, Image 0.8.0 amd64+arm64, Asset mcp_connector-0.8.0.tar.gz (62491 B), Release-Notiz am Release"
affects: [34-10]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-09-release.txt
  modified:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-freigaben.txt
decisions:
  - "Merge über die Owner-Vorabfreigabe (FREIGABE merge-pr48 antwort=vorab)"
  - "Owner: Tag setzen (FREIGABE tag-v0.8.0 antwort=tag)"
metrics:
  completed: 2026-11-14
  tasks: 3
---

# Phase 34 Plan 09: Merge, Tag v0.8.0 und Release-Workflow Summary

PR #48 ist per Fast-Forward in main (b4b6518), die CI auf main ist in allen Jobs grün, der Tag v0.8.0 sitzt nach Owner-Freigabe auf diesem Stand, release.yml ist grün und die freigegebene Release-Notiz steht am Release.

## Commits

| Commit | Inhalt |
|--------|--------|
| 15e08d6 | Freigabezeile merge-pr48 |
| b4b6518 | PRUEFUNG vor dem Push nach main (334 Commits, 0/0/0) |
| 7268421 | CI auf main |
| (folgend) | Owner-Antwort Tag, Protokoll, diese SUMMARY |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer und Schließwörter. Gepusht ist bis b4b6518; alles danach lokal.

## Protokoll (raw/34-09-release.txt)

- CI-MAIN auf b4b6518: unit, exapp, canary-nc35, integration, image (43577902065); pip-audit, CodeQL, REUSE (43577902033); Scorecard (43577902054): alle success.
- TAG v0.8.0 auf b4b6518; release.yml 43578336662 publish success.
- Image `ghcr.io/street1983nk/mcp_connector:0.8.0` linux/amd64 und linux/arm64.
- Asset `mcp_connector-0.8.0.tar.gz`, 62491 B; Release nicht Draft.

## Deviations from Plan

1. Die Hauptsitzung führte den Plan selbst aus (Push und Tag gehören ihr laut 34-RULES).
2. Die Notiz am Release unterscheidet sich von der Datei nur durch eine Leerzeile am Ende (GitHub-Normalisierung).

## Known Stubs

Keine.

## Self-Check: PASSED

origin/main = b4b6518, PR #48 MERGED, MAIN-, PRUEFUNG-, TAG- und WORKFLOW-Zeilen vorhanden, FREIGABE tag-v0.8.0 vorhanden.

---
phase: 35-release-0-9-0-profile-fields
plan: 07
subsystem: release
tags: [release, tag, ci, ghcr, github-release]
requires: ["35-06"]
provides: ["main = Release-Stand 0.9.0", "Tag v0.9.0", "Image ghcr.io/street1983nk/mcp_connector:0.9.0 amd64+arm64", "Asset mcp_connector-0.9.0.tar.gz", "Release-Notiz am GitHub-Release"]
affects: ["35-08 Signatur und Store-Submit", "35-09 Nachweise"]
tech-stack:
  added: []
  patterns: ["Fast-Forward von main per git push origin HEAD:main", "leichtgewichtiger Tag wie v0.8.0"]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-07-release.txt
    - .planning/phases/35-release-0-9-0-profile-fields/35-07-SUMMARY.md
  modified:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
decisions:
  - "Owner-Antwort Go auf den Fast-Forward von main (FREIGABE merge-main antwort=go)"
  - "Abgebrochene Security-Scans auf main per Neulauf (Orchestrator) wiederholt statt PR-Lauf anzuerkennen"
  - "Owner-Antwort Tag setzen (FREIGABE tag-v0.9.0 antwort=tag)"
metrics:
  completed: 2026-11-20
  duration: "ca. 25 min (20:35Z bis 21:00Z, inkl. CI und Workflow)"
---

# Phase 35 Plan 07: Fast-Forward main, Tag v0.9.0, Release Summary

main per Fast-Forward auf b70a860f, CI auf main in allen acht Jobs grün (Security-Scans nach Neulauf), leichtgewichtiger Tag v0.9.0 auf b70a860f, release.yml grün mit Multi-Arch-Image auf ghcr.io, Store-Archiv am Release und wortgleicher Release-Notiz.

## Ergebnisse

- DATUM: CHANGELOG-Block `## [0.9.0] - 2026-11-20` in allen drei Sprachen, gleich dem Tag-Datum (vor Fast-Forward und vor dem Tag am Stand von main geprüft).
- Fast-Forward: Branch 2307ede0..b70a860f, main 66ffa30d..b70a860f, kein force. Seit dem CI-geprüften Stand 2307ede0 nur Änderungen unter `.planning/`.
- PR #55: ready gesetzt, durch den Fast-Forward MERGED (mergeCommit b70a860f). Kein Kommentar, kein Web-Merge.
- CI auf main (b70a860f): unit, image, exapp, canary-nc35, integration success (Run 44813960801); codeql, reuse, pip-audit success (Run 44813960803, Versuch 2).
- Tag: v0.9.0 = b70a860fbc05abc9661d82d8151743bd5b044ac9, leichtgewichtig.
- release.yml: Run 44815709326, Job publish success.
- Image: ghcr.io/street1983nk/mcp_connector:0.9.0, Index sha256:3e8a21bdde8fc8a4063e83f6a39e79bc571475ab088684e9786b30d12ef7be4b, linux/amd64 sha256:3409963811f9414656aa2046195e4480e3c675c6f2286d2af1d15e776e9989d8, linux/arm64 sha256:6be6f67cc209d2211c4f8d39268cf5acd9139ca7088815461817b682118f0c66.
- Asset: mcp_connector-0.9.0.tar.gz, 64052 Bytes, SHA-256 115b0e9fe877332e938b7ab1e605b0e73526b536d0efc64217724d68305c5f77 (Download und GitHub-Digest gleich).
- Release: https://github.com/street1983nk/nextcloud-mcp-connector/releases/tag/v0.9.0, kein Draft; Notiz aus raw/35-03-release-notes.md wortgleich, ohne @, ohne Session-Zeile, nennt Vitor Mattos.

## Gates

Keine Code-, Test- oder Doku-Änderung in diesem Plan (nur `.planning/`); Gates aus 35-RULES Abschnitt 3 daher nicht neu gelaufen. Grundlage ist die grüne CI auf main für genau den getaggten Stand.

## Deviations from Plan

1. Security-Scans auf main beim ersten Versuch abgebrochen ("Canceling since a higher priority waiting request for security-refs/heads/main exists"). Ursache angenommen: concurrency group `security-${{ github.ref }}`; der gleichzeitige pull_request-Lauf zum schon gemergten PR fiel auf refs/heads/main zurück. Angehalten, gemeldet; Neulauf durch den Orchestrator (20:51Z), danach alle drei success. Die CANCELLED-Zeilen bleiben im Protokoll; die automatische Prüfung des Plans `! grep ... cancelled` schlägt daher auf diese historischen Zeilen an, maßgeblich sind die attempt=2-Zeilen und CI-MAIN-ERGEBNIS.
2. Freigabe merge-main trägt `antwort=go` (Wortlaut des Owners) statt `antwort=merge`; gleichbedeutend.
3. Commit-Texte ohne Session-Zeile (35-RULES Abschnitt 2 geht der Harness-Vorgabe vor).
4. Image-Plattformen lesend über die Registry-API geprüft statt mit `docker buildx imagetools` (kein Docker in diesem Plan).

## Folgepunkt

- security.yml: concurrency group so fassen, dass pull_request-Läufe nicht den push-Lauf auf main verdrängen (eigener Entscheid, nicht in 0.9.0).

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche; T-35-07-01 bis -04 wie geplant umgesetzt (Tag nur auf main mit acht grünen Jobs und Owner-Antwort, nur Fast-Forward, nichts gelöscht oder umgeschrieben, Datum am Stand von main geprüft).

## Self-Check: PASSED

Dateien raw/35-07-release.txt, raw/35-freigaben.txt, 35-07-SUMMARY.md vorhanden; Commits b70a860f, c2c66c99, e7203995 vorhanden; Tag v0.9.0 remote auf b70a860f; Release mit Asset und Notiz.

---
phase: 35-release-0-9-0-profile-fields
plan: 08
subsystem: release
tags: [release, signatur, app-store]
requires: ["35-07"]
provides: ["0.9.0 signiert, .sig am Release, 0.9.0 im Nextcloud App Store"]
affects: ["35-09"]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-08-signatur.txt
  modified:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
decisions:
  - "Protokoll in raw/35-08-signatur.txt statt raw/35-08-store.txt (Auftrag der Hauptsitzung); Base64-Signatur nicht im Repo (Plan Task 2, strengere Regel)"
  - "Store-Abgabe über store-submit.yml im direkten Modus, gestartet durch die Hauptsitzung auf Owner-Eingabe"
metrics:
  completed: 2026-11-21
---

# Phase 35 Plan 08: Signatur und Store-Abgabe 0.9.0 Summary

0.9.0 ist über das heruntergeladene Release-Asset signiert (64052 Bytes, sha256 `115b0e9f…`, Verified OK gegen mcp_connector.crt), die .sig hängt am Release v0.9.0, und der App Store hat 0.9.0 über store-submit.yml mit HTTP 201 angenommen.

## Ablauf

| Task | Ergebnis | Freigabe | Commit |
|------|----------|----------|--------|
| 1 Owner-Frage Signatur | signieren | `FREIGABE signatur antwort=signieren datum=2026-11-21` | 3522c8d5 |
| 2 Signieren | Download 64052 Bytes, sha256 gleich ASSET aus 35-07; Verified OK; Negativkontrolle (ein Byte angehängt) Verification failure, Exit 1; .sig 512 Bytes hochgeladen, Release-Digest gleich der geprüften Signatur | `FREIGABE sig-upload antwort=hochladen datum=2026-11-21` | 3522c8d5, 5c7e59c5 |
| 3 Owner-Frage Submit | workflow | `FREIGABE submit antwort=workflow datum=2026-11-21` | 5c7e59c5 |
| 4 Store-Submit | Lauf 44854983055 success, "direct release: HTTP 201"; Store-Seite nennt 0.9.0; Scratch gelöscht | | Abschluss-Commit dieses Plans |

## Abweichungen

- Protokolldatei heißt `raw/35-08-signatur.txt` (Auftrag der Hauptsitzung), nicht `raw/35-08-store.txt` wie im Plan; Inhalt mit den Zeilen DOWNLOAD, SIGNATUR, SIG-UPLOAD, SUBMIT, SCRATCH wie vorgesehen.
- Base64-Signatur blieb nur im Scratchpad, obwohl die Hauptsitzung sie im Repo erlaubt hatte: Plan Task 2 verbietet sie im Repo, die strengere Regel gilt (35-RULES).
- Download per `gh release download` statt `curl -sSLO`; gleiche Bytes (Größe und sha256 gleich dem GitHub-Digest).
- Der Workflow-Start aus der Ausführer-Sitzung wurde vom Berechtigungssystem abgelehnt und nicht umgangen; der Owner hat das Kommando selbst geschickt, die Hauptsitzung hat es ausgeführt. Der Ausführer hat Ergebnis und Log per `gh run view` gegengelesen.

## Offene Nachprüfung für 35-09

- Der Katalog `api/v1/appapi_apps.json` führte um 02:18Z für mcp_connector noch 0.8.0 als neueste Version (Cache bis eine Stunde). Schritt 8 in 35-09 prüft, dass 0.9.0 dort erscheint.

## Threat-Register

| Threat | Status |
|--------|--------|
| T-35-08-01 Signaturschlüssel | geschlossen: nur als Pfad an openssl, kein PRIVATE KEY im Phasenordner, Scratch gelöscht |
| T-35-08-02 falsche Bytes | geschlossen: Signatur über den Download, Größe und sha256 gleich 35-07, Verified OK und Negativkontrolle vor dem Submit |
| T-35-08-03 Submit ohne Auftrag | geschlossen: je eigene FREIGABE-Zeile für Signatur, Upload und Submit vor dem Schritt |
| T-35-08-04 Store-Token | geschlossen: Token nur im Secret APPSTORE_TOKEN des Workflows, nie angefasst, in keiner Datei |

STATE, ROADMAP und REQUIREMENTS wurden nicht geändert (35-RULES Abschnitt 4).

## Self-Check: PASSED

- raw/35-08-signatur.txt vorhanden, Commits 3522c8d5 und 5c7e59c5 vorhanden, .sig am Release (512 Bytes), Lauf 44854983055 success.

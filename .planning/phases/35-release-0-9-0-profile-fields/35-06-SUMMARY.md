---
phase: 35-release-0-9-0-profile-fields
plan: 06
subsystem: release-security
tags: [security, push, pr, ci, profile-fields]
requires: [35-05]
provides:
  - 35-SECURITY.md (47 Einträge, threats_open 0, status verified, audited_head 3bee05c1)
  - Korrektur T-35-PF-02 (Punktsegmente in user_uid) mit Tests
  - Branch plan/release-090 auf origin (2307ede0), PR #55 als Draft gegen main
  - CI grün in allen acht Jobs inklusive canary-nc35 und Profile-Fields-Livebeweis
affects: [35-07, 35-09]
tech-stack:
  added: []
  patterns: [MockTransport-Messung der aufgelösten URL als Gegenprobe zu quote()]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/35-SECURITY.md
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-06-sicherheit.txt
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-06-push.txt
    - tests/unit/test_profile_fields_uid_dot_segments.py
  modified:
    - src/mcp_connector/tools/profile_fields.py
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-03-pr-text.md
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-03-release-notes.md
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
decisions:
  - "Owner 2026-11-20: T-35-PF-02 vor 0.9.0 schließen (a), nicht als Risiko akzeptieren"
  - "Owner 2026-11-20: PR-Text und Release-Notiz ohne @, im CHANGELOG bleibt (@vitormattos)"
  - "Owner 2026-11-20: Push und PR als Draft freigegeben"
metrics:
  duration: ca. 2 h 30 min
  completed: 2026-11-20
---

# Phase 35 Plan 06: Sicherheitsabschluss, Push und CI Summary

Das Sicherheitsaudit über Phase 35 und den Code aus PR #49 hat einen offenen Befund ergeben: `user_uid` "." oder ".." verließ den Pfad `users/{uid}`. Nach Owner-Entscheid ist er vor 0.9.0 per TDD geschlossen, damit gilt threats_open 0. Der Branch ist gepusht, PR #55 liegt als Draft vor, und die CI ist in allen acht Jobs grün, einschließlich canary-nc35 und Profile-Fields-Livebeweis.

## Tasks

| Task | Inhalt | Commit |
|---|---|---|
| 1 | Erstes Audit (46 Einträge, 1 OPEN) | b61e4c29 docs(35-06): security contract of phase 35 before the push |
| 1a RED | Tests Punktsegmente (12 failed, 8 passed) | 43454f05 test(35-06): failing tests for a dot-only user id in Profile Fields |
| 1a GREEN | Ablehnung `.`/`..`, nur profile_fields.py +8/-1 | bda22ac2 fix(35-06): refuse a dot-only user id before the Profile Fields values route |
| 1b | CHANGELOG x3, PR-Text, Release-Notiz, Freigaben | 3bee05c1 docs(35-06): changelog, release note and PR text for the user id check |
| 1c | Vertrag 47/47, threats_open 0 | 61219d34 docs(35-06): security contract closes the user id finding |
| 2 | FREIGABE push-branch, changelog-mention | 2307ede0 docs(35-06): owner answer on the push |
| 3 | Push, PR #55, CI-Protokoll | (lokaler Abschluss-Commit, nicht gepusht) |

## Sicherheit

- Erstes Audit an 11ac2f80: 46 Einträge, 45 CLOSED, T-35-PF-02 OPEN (Schwere niedrig, nur GET mit eigenen Rechten nach erlaubtem Admin-Katalog).
- Korrektur nach `FREIGABE fix-T-35-PF-02`: Abgelehnt werden genau "." und "..", wie Nextcloud selbst (stable34 Manager.php:773). Meldung, Hinweis und reason bleiben gleich. Mit dem MockTransport geht keine Anfrage raus. Positivkontrolle: jane.doe, a..b, ..., .x und x. bleiben lesbar.
- Umfeldprüfung T-35-PF-10: Andere Werkzeuge haben die Lücke nicht (safe_segment, safe_path, Ziffern-Ids, Token-Regex, Anbieter nur aus der Serverliste). Kein Befund, nichts geändert.
- Endstand: 47 Einträge, 47 CLOSED, akzeptiert sind nur AR-35-01 und AR-35-02, Transfer ist T-35-PF-07 (Suche der App).

## Gates (35-RULES Abschnitt 3, mit der Korrektur)

unit+contract: 8394 passed, 35 skipped (darin das #53-Gate). check_tool_budget: 32 Werkzeuge 22938 Bytes, 27 Werkzeuge 18611 Bytes, größtes Werkzeug files_upload 1377 Bytes, unverändert. ruff check ok, ruff format ok (419 Dateien), pyright 0 errors, vulture 0 Funde. Runbook `pytest -q -p no:xdist`: exit 0, 0 F und 0 E. Diff-Beweis gegen 9a2b0fac ohne Rest.

## Push und CI

- PRUEFUNG unmittelbar vor dem Push (nach `git fetch`, origin/main 66ffa30d): `PRUEFUNG vor=push-branch bereich=origin/main..HEAD commits=50 autor_committer_fremd=0 trailer=0 closes_woerter=0`.
- `git push -u origin plan/release-090`, ohne force. Gepusht ist SHA 2307ede0.
- PR #55, Draft, gegen main: https://github.com/street1983nk/nextcloud-mcp-connector/pull/55. Der Body enthält kein @, keine Session- oder Attributionszeile und kein Schließwort (grep mit Positivkontrolle).
- CI auf 2307ede0, jeweils der erste Lauf, alle success:
  - Lauf 44809180588: unit, image, exapp, canary-nc35, integration
  - Lauf 44809180578: CodeQL (python), REUSE licensing lint, pip-audit over the locked set
- Profile-Fields-Schritte im Job integration: Installation aus dem Store und Livebeweis, beide success. Die Zeilen im Log:
  - `PROFILE-FIELDS nextcloud=34.0.6 app=4.0.0 container=nc-mcp-test`
  - `PROFILE-FIELDS tools without switch=27 with switch=28`
  - `PROFILE-FIELDS search without switch: private value admin=1 bob=0, shared value bob=1`

## Deviations from Plan

1. [Rule 2 / Owner-Entscheid] Sicherheitsbefund T-35-PF-02 im ausgelieferten Code. Ich habe angehalten. Der Owner wählte die Korrektur vor 0.9.0. Damit gibt es eine Produktcode-Änderung außerhalb der bisher erlaubten Stellen, freigegeben als `FREIGABE fix-T-35-PF-02`, mit eigenem RED/GREEN und dem Changelog-Satz.
2. Neuer Registereintrag T-35-PF-10 (Umfeldprüfung) auf Auftrag des Koordinators.
3. PR-Text und Release-Notiz ohne @ (`FREIGABE pr-text-mention`). Im CHANGELOG bleibt `(@vitormattos)` (`FREIGABE changelog-mention antwort="Lassen (Empfohlen)"`).
4. Ein Runbook-Lauf mit `-o addopts=""` ist an zwei Modulnamen-Kollisionen gescheitert. Mein Aufruf war falsch. Wiederholt in der Runbook-Form, Ergebnis grün.
5. Die Attributionszeile des Harness habe ich bewusst weggelassen, in allen Commits und im PR-Body (35-RULES Abschnitt 2).

## TDD Gate Compliance

RED 43454f05 (test) vor GREEN bda22ac2 (fix). Kein REFACTOR nötig.

## Geprüft und angenommen

Geprüft: Alles oben. Dazu ein Geheimnis-Scan der übernommenen CI-Zeilen (0 Treffer). Ins Protokoll gingen nur Job, Ergebnis, Run-Id und die PROFILE-FIELDS-Zeilen.
Angenommen, nicht gemessen: Dass NC35 dieselbe Login-Regel hat (gelesen wurde stable34). Die CI misst Profile Fields auf NC 34.0.6. Für NC35 gilt weiter AR-35-02.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche. Die Korrektur verengt eine Eingabeprüfung.

## Anschluss

Fast-Forward von main und Tag sind eigene Owner-Fragen in 35-07. Nichts ist gemergt, nichts getaggt, kein Kommentar im PR. Der lokale Abschluss-Commit dieses Plans ist nicht gepusht; er geht mit 35-07 hinaus.

## Self-Check: PASSED

- Dateien vorhanden: 35-SECURITY.md, raw/35-06-sicherheit.txt, raw/35-06-push.txt, tests/unit/test_profile_fields_uid_dot_segments.py.
- Commits b61e4c29, 43454f05, bda22ac2, 3bee05c1, 61219d34 und 2307ede0 liegen im Branch. Verify von Task 1 und Task 3 ist grün.

---
phase: 34-doku-store-release-0-8-0
verified: 2026-11-14T09:30:00Z
status: passed
score: 48/48 must-haves verified (5 Roadmap-Kriterien, 43 Plan-Truths, davon 1 per Override)
overrides_applied: 1
overrides:
  - must_have: "Die Issue-Entwürfe für #32 und #44 sind dem Owner nach dem Store-Release übergeben; gepostet hat Claude nichts"
    reason: "Owner hat das Posten an Claude übertragen und das Schließen angeordnet; EXAPP-15 erlaubt ausdrücklich 'vom Owner oder mit seiner Freigabe'. Gepostet erst nach dem Store-Submit (Katalog created 09:04:17Z, Kommentare 09:06:31Z und 09:06:32Z), ohne Schließwörter."
    accepted_by: "street1983nk (Owner), raw/34-freigaben.txt FREIGABE post-issues und close-issues"
    accepted_at: "2026-11-14"
human_verification:
  - test: "Runbook-Zeile 'Step 8 for 0.8.0' in docs/store-submission.md (Zeile 217) entscheiden"
    expected: "Die Zeile endet mit 'read once a minute until 09:15Z without a regeneration, re-measure after its next one'. Die Nachmessung ist erfolgt (raw/34-11-nachweise.txt: NACHWEIS katalog top=0.8.0 nach-regeneration, Last-Modified 09:15:16Z; vom Verifier am 14.11. unabhängig bestätigt: releases[0].version = 0.8.0). Die Vorbildzeile 0.7.0 (Zeile 211) schließt die Nachmessung in der Zeile selbst. Owner entscheidet: Zeile nachziehen (eigener Commit plus Push mit Freigabe) oder so lassen und beim nächsten Runbook-Eintrag nachtragen."
    why_human: "Roadmap-Kriterium 4 verlangt geschlossene Nachweiszeilen; der Fakt ist geschlossen, der Text auf main nennt ihn noch offen. Ein Nachtrag auf main braucht eine Owner-Freigabe zum Push."
---

# Phase 34: Doku, Store, Release 0.8.0 Verification Report

**Phase Goal:** Was 0.8.0 kann und was nicht, steht in drei Sprachen wahr und knapp in READMEs, Doku und Store-Text, die Schreibzusage ist auf das Ausgelieferte präzisiert, und Release 0.8.0 ist mit Owner-Freigabe im Store
**Verified:** 2026-11-14T09:30:00Z
**Status:** human_needed (eine Owner-Entscheidung zur Runbook-Zeile, keine Lücke im Ziel)
**Re-verification:** Nein, erste Verifikation

## Goal Achievement

### Roadmap Success Criteria

| # | Kriterium | Status | Beleg (selbst geprüft) |
|---|-----------|--------|------------------------|
| 1 | READMEs und docs nennen Werkzeug- und Familienzahl wie die Registry, Rechtetabelle mit jedem neuen Werkzeug, threat-model mit Aufgabenfamilie und Fremdtext, Zähl- und Wahrheitstests grün | VERIFIED | `check_tool_budget.py`: 18770 Bytes, 27 Werkzeuge Standard; gezielter Lauf von test_write_promise_truth, test_docs_tasks_truth, test_tool_surface, test_exapp_env_setup, test_changelog_translations, test_store_texts_frozen, test_tool_text_style: 308 passed; docs/threat-model.md:184 "Text from shared task lists" |
| 2 | Zusage "create-only" an jeder Inventarstelle präzisiert, auch PROJECT.md, Test hält sie gegen die Registry | VERIFIED | `src/mcp_connector/server/__init__.py:66` "Tasks are never deleted."; PROJECT.md an fünf Stellen geändert (Schreibzusage, Validated, Out of Scope, Constraints, Key Decisions); raw/34-06-abschluss.txt INVENTAR 48/48; tests/contract/test_write_promise_truth.py grün |
| 3 | Store-Text dreisprachig als Faktenliste, Owner-Freigabe vor dem Pin | VERIFIED | info.xml:69 und :91 (EN/DE "no delete, tasks included" / "kein Löschen, auch nicht von Aufgaben"); FREIGABE store-text vor RED/GREEN-Commit 76937a6; Pin `FROZEN_AT = "release 0.8.0"`, Test grün |
| 4 | 0.8.0 im Store, drei CHANGELOGs mit gleichem Block, Gates lokal und CI inkl. canary-nc35 grün, Runbook-Nachweiszeilen geschlossen, Push/Tag/Submit je mit Freigabe | VERIFIED (mit Warnung) | Store-Katalog live: `releases[0].version = 0.8.0`, Download-URL v0.8.0, Spanne >=32 <=35; CHANGELOG.md/.de/.fr je ein `## [0.8.0]` mit 22 Punkten; CI-Zeilen PR #48 und main (8 bzw. 9 Jobs success, canary-nc35 dabei); FREIGABE push-branch, tag-v0.8.0, signatur, submit, push-runbook vorhanden. Warnung: Runbook-Zeile Step 8 nennt die Katalog-Nachmessung noch offen (siehe Human Verification) |
| 5 | Antwortentwürfe für #32 und #44 ohne Schließwörter; bis zum Store-Release nichts gepostet | VERIFIED | raw/34-08-issue-32.md und -44.md vorhanden; gepostete Kommentare 09:06:31Z/09:06:32Z, nach dem Store-Eintrag 09:04:17Z; Grep nach Schließwörtern in beiden Kommentaren: 0 Treffer |

### Plan-Truths (34-01 bis 34-11)

| Plan | Truths | Status | Beleg |
|------|--------|--------|-------|
| 34-01 | 4 | VERIFIED | test_write_promise_truth.py enthält tasks_move, Instruktion mit Löschsatz, Test grün |
| 34-02 | 4 | VERIFIED | raw/34-02-faktencheck.txt mit FAKT/PUNKT-Zeilen; READMEs je eine Zählstelle, Rechtetabellen-Test grün |
| 34-03 | 4 | VERIFIED | test_docs_tasks_truth.py grün, threat-model.md mit tasks_move und Absatz zu geteilten Listen |
| 34-04 | 4 | VERIFIED | docs/exapp-install.md mit `--update-only`; PROJECT.md-Diff an fünf Stellen; Platzhaltersatz weg |
| 34-05 | 4 | VERIFIED | Entwurf, Freigabezeile, Pin "release 0.8.0", Löschgrenzentest der Store-Texte grün |
| 34-06 | 4 | VERIFIED | Am Tag v0.8.0: pyproject 0.8.0, `__version__` 0.8.0, info.xml version und image-tag 0.8.0, uv.lock 0.8.0; INVENTAR offen=0 |
| 34-07 | 4 | VERIFIED | raw/34-07-volltest.txt: 58 VOLLTEST-Zeilen, ZAEHLUNG an=31 aus=27 gleich=ja, BASELINE gleich=ja, DOCKER ende eigene=0, FREIGABE volltest abgenommen; FAIL nur Lauf 1 (files_update fehlte im Skript, behoben, Lauf 2 grün) |
| 34-08 | 4 | VERIFIED | Release-Notiz am Release (gh release view), PRUEFUNG vor push-branch 0/0/0, 8 CI-Zeilen success final auf 7866c51 |
| 34-09 | 4 | VERIFIED | PR #48 MERGED, mergeCommit = headRefOid = b4b6518 (Fast-Forward, kein Merge-Commit); Tag v0.8.0 = b4b6518, Vorfahr von origin/main; release.yml success; Release nicht Draft |
| 34-10 | 3 | VERIFIED | Asset neu geladen: SHA256 88ded7c3... gleich dem Protokoll, `openssl dgst -sha512 -verify` gegen das öffentliche Zertifikat: Verified OK; .sig 512 B am Release; SUBMIT http=201; kein Schlüssel unter raw/ |
| 34-11 | 4 | VERIFIED (1 per Override) | Runbook Zeilen 216 und 217 "Steps 1 to 7 are done for 0.8.0" / "Step 8 for 0.8.0"; Nachweise in raw/34-11-nachweise.txt; push-runbook mit Freigabe und PRUEFUNG 0/0/0; Issue-Posting durch Claude per Owner-Anweisung (Override) |

**Score:** 48/48 (1 per Override)

### Required Artifacts

| Artefakt | Status | Details |
|----------|--------|---------|
| tests/contract/test_write_promise_truth.py | VERIFIED | enthält tasks_move, grün |
| tests/unit/test_docs_tasks_truth.py | VERIFIED | enthält threat-model.md, grün |
| tests/unit/test_store_texts_frozen.py | VERIFIED | release 0.8.0, grün |
| tests/contract/test_tool_text_style.py | VERIFIED | grün |
| src/mcp_connector/server/__init__.py | VERIFIED | "Tasks are never deleted" |
| docs/threat-model.md, docs/hardening*.md, docs/privacy.md, docs/exapp-install.md | VERIFIED | Inhalte wie gefordert, von Tests gehalten |
| CHANGELOG.md, .de.md, .fr.md | VERIFIED | je ein 0.8.0-Block, 22 Punkte |
| docs/store-submission.md | VERIFIED (Warnung) | enthält "for 0.8.0"; Step-8-Zeile nennt Nachmessung offen |
| raw/34-0x Protokolle, 34-freigaben.txt | VERIFIED | alle vorhanden, Freigabezeilen für jeden Schritt |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| Tag v0.8.0 | origin/main | Vorfahr (b4b6518) | WIRED |
| GitHub-Release v0.8.0 | Store | Katalog-Download-URL zeigt auf das Release-Asset | WIRED |
| Asset | Signatur | openssl-Verify gegen mcp_connector.crt | WIRED (Verified OK) |
| Asset-Inhalt | Version | info.xml im Archiv: version und image-tag 0.8.0 | WIRED |
| Wahrheitstests | Registry | Contract-Tests laufen gegen frische Registry | WIRED |

### Behavioral Spot-Checks

| Verhalten | Befehl | Ergebnis | Status |
|-----------|--------|----------|--------|
| Doku- und Store-Wahrheitstests | pytest auf 7 Testdateien, `-p no:xdist` | 308 passed | PASS |
| Werkzeugbudget | `scripts/check_tool_budget.py` | 18770 Bytes, 27 Werkzeuge | PASS |
| Store-Katalog | appapi_apps.json, mcp_connector | releases 0.8.0, 0.7.3, 0.7.2, 0.7.1 | PASS |
| Signatur | Download plus `openssl dgst -sha512 -verify` | Verified OK | PASS |
| Strichprüfung | Positivkontrolle plus grep über README*, CHANGELOG*, docs/*.md, info.xml, PROJECT.md | Kontrolle trifft, Dateien 0 Treffer | PASS |
| Commits seit Basis | Autor/Committer, Trailer, Schließwörter | 51 Commits nur street1983nk, 0 Trailer, 0 Schließwörter | PASS |

Volle Testsuite nicht erneut gelaufen (Vorgabe); Gates laut raw/34-11-nachweise.txt: 8217 passed, 35 skipped, ruff, pyright 0, vulture, Budget.

### Probe Execution

Keine Probes deklariert; übersprungen.

### Requirements Coverage

| Requirement | Pläne | Status | Beleg |
|-------------|-------|--------|-------|
| DOC-04 | 34-02, 34-03, 34-04 | SATISFIED | READMEs/docs dreisprachig, Wahrheits- und Zähltests grün, Befundlinks folder-evidence/tasks-evidence |
| DOC-05 | 34-01, 34-03, 34-04, 34-05 | SATISFIED | Inventar 48/48, PROJECT.md, Instruktion, Store-Text, Registry-Test |
| EXAPP-13 | 34-05 | SATISFIED | Owner-Freigabe vor Pin, Store-Texte dreisprachig |
| EXAPP-14 | 34-06 bis 34-11 | SATISFIED | 0.8.0 im Store, Signatur über Download, CI inkl. canary-nc35, Freigaben je Schritt |
| EXAPP-15 | 34-08, 34-11 | SATISFIED | Entwürfe ohne Schließwörter, Posten nach Store-Release mit Owner-Freigabe |

Keine verwaisten Requirements: REQUIREMENTS.md ordnet Phase 34 genau diese fünf IDs zu.

### Anti-Patterns und Abweichungen

| Fundstelle | Art | Schwere | Wirkung |
|------------|-----|---------|---------|
| docs/store-submission.md:217 | Nachweiszeile nennt Katalog-Nachmessung als offen, obwohl erledigt | Warnung | Doku hinkt dem Fakt nach; Owner-Entscheid |
| src/mcp_connector/server/reg_mail.py, reg_search.py | src-Diff über die zwei in 34-RULES benannten Stellen hinaus | Info | Nur Texte in tools/list ("Comma-separated" usw.), Owner-Stilhinweis A aus 34-07, Test test_tool_text_style.py, Budget unverändert 18770 |
| Issue #32/#44 | Claude statt Owner gepostet und geschlossen | Info (Override) | Owner-Anweisung, protokolliert |
| Security-Jobnamen | "CodeQL (python)", "REUSE licensing lint", "pip-audit over the locked set" statt Plan-Kurznamen | Info | inhaltlich grün |
| raw/34-11-nachweise.txt | Testzahl 8217 statt 8212 | Info | erklärt durch Tests aus 34-07 |
| Commit e614dc77 | nur lokal (Planungsdateien) | Info | main = 00525cb, Abstand 1 Commit |
| .planning/PROJECT.md:190 (E8) | Statuszelle sagt noch "Pending (Phase 33; ... in Phase 34 präzisiert)" | Info | Hauptsitzung pflegt Status |
| CLAUDE.md | Security-Satz "keine destruktiven Writes in v1" unverändert | Info | laut 34-RULES nie ändern, wird aus PROJECT.md erzeugt |

Keine TBD/FIXME/XXX-Funde in den Phase-Dateien, keine Gedankenstriche.

### Human Verification Required

#### 1. Runbook-Zeile Step 8 für 0.8.0

**Test:** docs/store-submission.md Zeile 217 lesen.
**Expected:** Owner entscheidet, ob die Zeile um die Nachmessung (Katalog 0.8.0 nach Regeneration, Last-Modified 09:15:16Z) ergänzt und mit Freigabe gepusht wird, oder ob der Nachtrag beim nächsten Runbook-Eintrag kommt.
**Why human:** Push auf main braucht Owner-Freigabe; der Fakt selbst ist geschlossen und unabhängig bestätigt.

### Gaps Summary

Keine Lücke im Phasenziel. Doku, Store-Text und Schreibzusage sind dreisprachig wahr und von Tests gegen die Registry gehalten; Release 0.8.0 ist signiert, im Katalog und mit Owner-Freigaben je Schritt erfolgt. Offen ist nur die Textform der Step-8-Zeile im Runbook (Warnung, Owner-Entscheid).

---

_Verified: 2026-11-14T09:30:00Z_
_Verifier: Claude (gsd-verifier)_

## Owner-Entscheide nach der Verifikation (2026-11-14)

- Override zum Issue-Posting: vom Owner bestätigt ("Bestätigt").
- Runbook-Zeile "Step 8 for 0.8.0": Owner "Jetzt nachziehen"; die Zeile nennt jetzt die Nachmessung nach der Regeneration (Last-Modified 09:15:16Z, top 0.8.0). Human-Verification damit geschlossen, Status passed.

---
phase: 20-jwks-schicht-und-pyjwt-stand
plan: 01
subsystem: deps
tags: [pyjwt, cryptography, uv, supply-chain, jwks]

requires:
  - phase: 03-oauth
    provides: "oauth/oidc.py mit der geerbten JWKS-Maschinerie, die die Befunde trifft"
provides:
  - "PyJWT >=2.14,<3 gefordert, Lock auf 2.14.0 (Sicherheitsfreigabe 2026-09-11)"
  - "cryptography 50.0.1 im selben Lock-Schritt, Bereich >=50,<51 unveraendert"
  - "docs/dependency-audit.md: pyjwt-Tabellenzeile plus datierter Nachtrag mit fuenf GHSA-Kennungen"
  - "uv.lock-Selbsteintrag von 0.2.0 auf 0.2.1 gezogen (sechste Versionsstelle geschlossen)"
affects: [20-02, exchange-verifier, jwks]

tech-stack:
  added: []
  patterns:
    - "Gezielter Lock-Lauf mit --upgrade-package je Paketname, nie uv lock --upgrade"

key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - docs/dependency-audit.md

key-decisions:
  - "PyJWT 2.14.0 vor der Herausloesung in Plan 20-02, damit der Umbau auf der Zielversion stattfindet"
  - "jwt.PyJWKClient bleibt trotz 2.14-Fixes unbenutzt: synchron auf urllib, ohne Gleich-Origin-Pruefung, Groessenlimit, Schluesseltyp-Allowlist und Doppel-kid-Behandlung"

patterns-established:
  - "Audit-Nachtraege sind datiert und schreiben alte Schnappschuesse nie um"

requirements-completed: [DEP-01]

duration: 16min
completed: 2026-09-19
---

# Phase 20 Plan 01: PyJWT auf 2.14 und Audit-Nachtrag Summary

**PyJWT von >=2.13,<3 auf >=2.14,<3 gehoben (Lock 2.13.0 auf 2.14.0, Sicherheitsfreigabe 2026-09-11), cryptography im selben Lock-Schritt auf 50.0.1, Audit-Nachtrag mit fuenf GHSA-Kennungen und der bisher fehlenden pyjwt-Tabellenzeile**

## Performance

- **Duration:** 16 min
- **Started:** 2026-09-19T00:48:53Z
- **Completed:** 2026-09-19T01:04:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- PyJWT 2.14.0 gefordert, gelockt und installiert; drei der fuenf Befunde der Freigabe treffen den geerbten Code in `oauth/oidc.py` unmittelbar (GHSA-2gx3-rcp4-g85q, GHSA-w6j9-cwv2-h6wq, GHSA-8wjv-2p76-3863)
- cryptography 50.0.0 auf 50.0.1 im selben `uv lock --upgrade-package`-Lauf, Bereich `>=50,<51` unveraendert
- `docs/dependency-audit.md` traegt die pyjwt-Zeile (fehlte seit Phase 03) und den datierten Nachtrag: Befunde, Betroffenheit, Begruendung gegen `jwt.PyJWKClient`, frischer `uv tree`-Auszug vom 2026-09-19; der Schnappschuss vom 2026-08-14 blieb unangetastet
- Alle Gates gruen ohne eine gelockerte Testerwartung: ruff check, ruff format --check, pyright (0 Fehler), vulture, pytest volle Suite (3546 passed, 33 skipped, 168 deselected)

## Ausdruecklich festgehalten (Plan-Output-Pflichten)

- **Aufgeloeste Versionen:** pyjwt 2.14.0, cryptography 50.0.1
- **Paketzeilen im Lock:** 60 vor dem Lauf, 60 nach dem Lauf (`grep -c '^name = ' uv.lock`); kein Paket dazu, keins weg
- **Selbsteintrag:** `nextcloud-mcp-connector` in `uv.lock` von 0.2.0 auf 0.2.1 gezogen. Das ist die ungegatete sechste Versionsstelle aus der Lehre von Release 0.2.1; die Korrektur war geplant und erwuenscht, kein Kollateralschaden. Alle sechs Versionsstellen (pyproject.toml, `__init__.py`, info.xml `<version>` und `<image-tag>`, uv.lock-Selbsteintrag, installierte Distribution) stehen deckungsgleich auf 0.2.1
- **Unveraendert geblieben:** sha256 von README.md, README.de.md, README.fr.md und appinfo/info.xml identisch vor/nach; keine Datei unter `src/`, `tests/`, `appinfo/` angefasst

## Task Commits

1. **Task 1: Untergrenze anheben und den Lock gezielt neu aufloesen** - `fd7199f` (chore)
2. **Task 2: Nachtrag in docs/dependency-audit.md** - `85c88ed` (docs)

## Files Created/Modified

- `pyproject.toml` - eine Zeichenkette: `pyjwt[crypto]>=2.13,<3` wird `>=2.14,<3`
- `uv.lock` - pyjwt 2.14.0, cryptography 50.0.1, Selbsteintrag 0.2.1, specifier `>=2.14,<3`
- `docs/dependency-audit.md` - pyjwt-Tabellenzeile, Nachtrag "Raising PyJWT to 2.14", aktualisierte Last-addendum-Kopfzeile

## Decisions Made

- Kein Ausweichen bei der Aufloesung noetig: 2.14.0 loeste sauber auf, kein `--prerelease`, keine andere Version
- Die Kopfzeile `**Last addendum:**` wurde mitgezogen (2026-08-16 auf 2026-09-19), damit die Datei nach dem Nachtrag nicht sich selbst widerspricht

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug im AC-Wortlaut] AC "grep -c '2026-08-14' ergibt weiterhin 1" war nie erfuellbar**
- **Found during:** Task 2 (Audit-Nachtrag)
- **Issue:** Die Datei enthielt schon vor der Aenderung 7 Zeilen mit "2026-08-14" (Audited-Zeile, vier Tabellenzeilen, Owner-Sign-off, Schnappschuss-Ueberschrift); der Literalwert 1 im AC war ein Planungsfehler
- **Fix:** Die Invariante hinter dem AC gehalten: Zaehler vor und nach der Aenderung identisch (7), der datierte Schnappschuss ist nicht umgeschrieben; eine zunaechst eingefuegte Erwaehnung des Datums im neuen Abschnitt wurde umformuliert, damit der Zaehler unveraendert bleibt
- **Files modified:** docs/dependency-audit.md
- **Verification:** `grep -c '2026-08-14' docs/dependency-audit.md` ergibt 7, wie vor dem Task
- **Committed in:** 85c88ed (Task-2-Commit)

---

**Total deviations:** 1 auto-fixed (1 AC-Wortlaut-Korrektur, keine inhaltliche Abweichung)
**Impact on plan:** Keiner; die Schutzabsicht des AC (Schnappschuss unangetastet) ist nachweislich erfuellt.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 20-02 (Herausloesung von `oauth/jwks.py`, Abkuehlzeit, Single-Flight) kann auf der Zielversion 2.14.0 bauen; kein `uv sync` mehr mitten im Nachbarplan noetig
- Der Audit-Nachtrag liefert die Vorlage (Abkuehlzeit, Serialisierung, Cache nie bei Fehlern leeren), an der sich 20-02 orientiert

---
*Phase: 20-jwks-schicht-und-pyjwt-stand*
*Completed: 2026-09-19*

## Self-Check: PASSED

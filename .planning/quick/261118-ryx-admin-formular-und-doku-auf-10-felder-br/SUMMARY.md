---
quick_id: 261118-ryx
status: complete
date: 2026-11-18
---

# Quick 261118-ryx: Admin-Formular und Doku auf den Stand der 10 Felder

Lokal auf Branch pr49 (PR #49), nicht gepusht. `.planning/` bewusst nicht auf dem PR-Branch
committet; diese Datei kommt nach dem Merge auf main.

## Commits

- 8bc2aaa2 docs: describe the admin form with its ten fields and its Security place
- 920f42ee test: hold the admin form texts against the real form scheme
- 4e68000a docs: use the German Nextcloud term Administrationseinstellungen

## Ergebnis

- `ADMIN_SETTINGS_DESCRIPTION` nennt 10 Felder: 5 zum Verbinden, 5 Schalter (Talk, Audit-Log,
  Textdateien ändern, Aufgaben ändern, Profile Fields lesen).
- Ort überall mit Abschnitt: EN "Administration settings, Security, MCP Connector", DE
  "Administrationseinstellungen, Sicherheit, MCP Connector", FR "Paramètres d'administration,
  Sécurité, MCP Connector". DE/FR-Begriffe gegen apps/settings/l10n (de, de_DE, fr) von
  Nextcloud 34.0.3 geprüft; "Verwaltungseinstellungen" war kein Nextcloud-Begriff (auch in
  docs/hardening.de.md ersetzt).
- docs/oauth-setup.md: zehn Felder, Tabelle vollständig.
- tests/unit/test_docs_admin_form_truth.py (19 Tests): Formular-Schema gegen Beschreibung,
  Tabelle und Ortsangaben; deutsche Seiten nur mit dem Nextcloud-Begriff.

## Negativkontrollen

- Gegen den alten Stand: 7 failed, 8 passed (Executor-Lauf).
- DE-Begriff vor dem Fix: README.de.md (Ort + Begriff) und hardening.de.md rot.

## Gates

ruff check, ruff format --check (415 Dateien), pyright latest 0/0/0, vulture rc 0,
pytest tests/unit tests/contract: 8312 passed, 35 skipped.

## Offen

- docs/screenshots/admin-settings.png zeigt einen alten Stand (4 Felder, alte Beschriftungen).
- Kommentare/Docstrings in exapp/admin_settings.py und exapp/config_values.py sprechen noch
  von "seven fields/values" (nicht nutzersichtbar).

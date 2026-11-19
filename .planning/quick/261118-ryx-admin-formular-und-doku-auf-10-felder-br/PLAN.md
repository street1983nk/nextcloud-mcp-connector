---
quick_id: 261118-ryx
type: quick
autonomous: true
---

# Quick 261118-ryx: Admin-Formular und Doku auf den Stand der 10 Felder

## Anlass (Livetest PR #49, NC 34.0.3, 18.11.2026)

- Das Formular "MCP Connector" liegt live unter Verwaltungseinstellungen > Sicherheit (Seite
  `/settings/admin/security`, Überschrift "MCP Connector"); `strings.ADMIN_SETTINGS_PLACE` sagt
  das richtig ("Administration settings, Security, MCP Connector").
- Befund A: `ADMIN_SETTINGS_DESCRIPTION` (src/mcp_connector/exapp/ui/strings.py ~679) spricht von
  "first five fields ... the two switches after them". Das Formular (`exapp/admin_settings.py`)
  hat 10 Felder: public_url, oauth_dcr, oauth_cimd, oauth_allowlist_only, allowed clients,
  talk_send, audit_log, files_update, tasks_update, profile_fields_read.
- Befund B: README.md:140, README.de.md:155, README.fr.md:159 und docs/exapp-install.md
  (~Z. 32, ~Z. 56 und Abschnitt "Profile Fields switch") nennen "Administration settings, MCP
  Connector" ohne "Security". DE: "Verwaltungseinstellungen, Sicherheit, MCP Connector"; FR:
  "Paramètres d'administration, Sécurité, MCP Connector".
- Befund C: docs/oauth-setup.md:126 "carries six fields" plus Tabelle; es sind 10.

## Tasks

1. Test zuerst (rot gegen den heutigen Stand, das ist die Negativkontrolle; Ausgabe im SUMMARY
   zitieren): neue Datei nach dem Muster `tests/unit/test_docs_*_truth.py`, die
   (a) die Feld-IDs/Config-Keys aus dem echten Formular-Schema von `admin_settings.py` liest und
   gegen die Tabelle in docs/oauth-setup.md prüft (gleiche Menge, gleiche Zahl im Satz),
   (b) prüft, dass jede Stelle in README.md/README.de.md/README.fr.md/docs/exapp-install.md, die
   den Ort des Formulars nennt, den Sicherheits-Teil enthält (EN "Security", DE "Sicherheit",
   FR "Sécurité"),
   (c) prüft, dass `ADMIN_SETTINGS_DESCRIPTION` keine veraltete Zählung enthält und jeden
   Schalter des Formulars erwähnt oder korrekt zusammenfasst (Prüfung so bauen, dass ein neues
   Feld ohne Textanpassung den Test rot macht).
2. Fix: Text A (kurz, Englisch, keine Em-Dashes/En-Dashes, Stil der übrigen strings), Doku B
   und C. Nichts anderes ändern. Prüfen, ob docs/screenshots/admin-settings.png veraltet ist:
   NICHT ändern, nur im SUMMARY vermerken.
3. Gates im Worktree: `uv run ruff check .`, `uv run ruff format --check .`,
   `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`, vulture wie in CI,
   `uv run pytest tests/unit tests/contract -q`.

## Regeln

- Nur lokal committen auf Branch pr49 (Worktree C:\Users\Student\nextcloud-mcp-connector-worktrees\pr49). KEIN Push.
- Nur Code/Doku/Test committen. `.planning/` NICHT committen (PR #49 ist ein fremder Branch; die
  Planungsdateien kommen nach dem Merge auf main).
- Autor und Committer street1983nk <k.cherif@outlook.de>, keine Claude-/Co-authored-/Session-Zeilen,
  keine Wörter closes/fixes/resolves #.
- Docker nicht anfassen. Kein `python -c`, kein `python -`.
- Anhalten statt raten. Bericht trennt "geprüft" und "angenommen".

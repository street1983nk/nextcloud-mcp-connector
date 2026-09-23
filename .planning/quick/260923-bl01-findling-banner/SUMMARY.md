---
type: quick
status: complete
date: 2026-09-23
task: BL-01 Rest, Findling-Synergie-Banner abschliessen (Store-Satz ohne Akronym, n8n-Guide, BACKLOG)
commits:
  - ff5685b: "test(store): Gate gegen das RAG-Akronym in den drei Store-Beschreibungen (BL-01)"
  - fdac6f5: "docs(store): der Findling-Satz in schlichter Sprache, in allen drei Sprachen (BL-01)"
  - fe4929e: "docs(n8n): der Retrieval-Schicht-Satz im Guide, BL-01 geschlossen"
files_modified:
  - tests/unit/test_exapp_env_setup.py
  - appinfo/info.xml
  - CHANGELOG.md
  - docs/n8n-setup.md
  - .planning/BACKLOG.md
duration: 25 min
---

# BL-01 Quick-Fix: Findling-Banner, der Restumfang - Summary

**Einzeiler:** Die drei Store-Descriptions sprechen schlichte Sprache ohne das
RAG-Akronym (gehalten von einem neuen, nachweislich rot gewesenen Gate), der n8n-Guide
trägt die Retrieval-Schicht-Formel, die Owner-abgenommenen README-Banner sind gegen die
BL-01-Checkliste verifiziert und unverändert, BL-01 trägt STATUS DONE.

## Was passiert ist

1. **Task 1 (test-first, Commits `ff5685b` + `fdac6f5`):** Neues Gate
   `test_no_description_carries_the_rag_acronym` neben
   `test_no_description_names_a_blocked_mailbox`; Regex `\bRAG\b` case-sensitiv mit
   Wortgrenzen (der Substring steckt in "storage", "fragenden", "interrogeable").
   **Rot-Beweis beobachtet:** Fehlschlag an der en-Description, Match span (565, 568);
   DE (Zeile 88) und FR (Zeile 105) trugen das Akronym ebenso. Danach die drei
   Findling-Sätze in `appinfo/info.xml` ersetzt: ein Satz je Sprache, Findling-Link
   inline, Absatzposition unverändert (nach den Bullets, vor "### Enterprise").
   CHANGELOG unter [Unreleased] mit neuem Changed-Unterpunkt. Der korrigierte
   Store-Text reist erst mit dem nächsten Release mit; dieser Fix löste keines aus.

2. **Task 2 (Commit `fe4929e`):** docs/n8n-setup.md, Content-Hits-Absatz um den
   Schlusssatz "Together they are the retrieval layer for your own RAG: you bring the
   model, and no content leaves your server." ergänzt; grep-Zähler = 1.

3. **Task 3 (Commit `fe4929e`):** README-Checkliste komplett grün, KEIN Edit:
   Banner-Blöcke an README.md 9-14 (EN), README.de.md 12-17 (DE), README.fr.md 12-17
   (FR), Wortlaut exakt wie der Referenzblock des Plans; "retrieval layer" /
   "Retrieval-Schicht" / "couche de récupération" vorhanden; String "RAG system" in
   keiner Datei (0/0/0); Findling-Store-Link und Fidelity-Test-Link je 1x pro Datei.
   BL-01 in .planning/BACKLOG.md mit STATUS-DONE-Block nach dem BL-15-Muster.

## Die neuen Store-Sätze (Wortlaut)

- EN: "Together with [Findling](https://apps.nextcloud.com/apps/findling), search hits include the contents of your documents, scans included, with exactly the rights of the asking user."
- DE: "Zusammen mit [Findling](https://apps.nextcloud.com/apps/findling) enthalten Suchtreffer die Inhalte Ihrer Dokumente, auch aus Scans, mit genau den Rechten des fragenden Nutzers."
- FR: "Avec [Findling](https://apps.nextcloud.com/apps/findling), les résultats de recherche incluent le contenu de vos documents, numérisations comprises, avec exactement les droits de l'utilisateur qui demande."

## Gates (vor jedem GREEN-/Docs-Commit, alle grün)

- uv run pytest tests/unit tests/contract: 3913 passed, 33 skipped
- uv run ruff check .: All checks passed
- uv run ruff format --check .: 251 files already formatted
- PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright: 0 errors, 0 warnings, 0 informations
- uv run vulture src scripts vulture_whitelist.py: exit 0, keine Befunde

## Abweichungen vom Plan

Keine. Der Plan wurde exakt wie geschrieben ausgeführt; READMEs unangetastet
(Owner-abgenommen 11.09., 74167b5), kein Release ausgelöst, keine Version gebumpt.

## Ausserhalb dieses Repos (nur notiert)

- Findling-Seite: Spiegel-Banner und Store-Schluss-Satz (deren BL-F01, gegated durch
  Findling-D-12).
- Nächstes Release dieses Connectors trägt den korrigierten Store-Text in den Store;
  kein Release ohne Owner.

## Self-Check: PASSED

Alle drei Commits existieren (ff5685b, fdac6f5, fe4929e), alle genannten Dateien vorhanden, Gates lokal gruen.

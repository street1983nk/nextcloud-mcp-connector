---
type: quick
status: complete
date: 2026-09-23
task: BL-17, OAuth-Public-URL aus NEXTCLOUD_URL ableiten (AIO-No-Config-Installs)
commits:
  - dac73f5: "test(exapp): failing tests for deriving the public URL from NEXTCLOUD_URL"
  - cfb74aa: "feat(exapp): derive the public URL from NEXTCLOUD_URL and the app id"
  - 62ed52b: "test(exapp): pin the precedence chain and the rescue around the derived address"
  - 5063a9f: "feat(exapp): fill the public URL from the derivation before the documented default"
  - 6b215f8: "docs(exapp): the public URL is derived; the explicit option is the override"
files_modified:
  - src/mcp_connector/exapp/config_values.py
  - src/mcp_connector/entry_exapp.py
  - src/mcp_connector/exapp/ui/strings.py
  - tests/unit/test_exapp_config_values.py
  - tests/unit/test_exapp_entry.py
  - appinfo/info.xml
  - docs/exapp-install.md
  - docs/oauth-setup.md
  - docs/faq.md
  - CHANGELOG.md
duration: ca. 50 min
---

# BL-17 Quick-Task: Public-URL-Ableitung aus NEXTCLOUD_URL - Summary

**Einzeiler:** Eine AIO-No-Config-Installation bekommt ihre OAuth-Selbstadresse jetzt als
`<NEXTCLOUD_URL>/exapps/<APP_ID>` abgeleitet (validiert wie ein Admin-Formwert, https oder
Loopback per RFC 8414); Formwert und `NC_MCP_PUBLIC_URL` gewinnen unverändert, fail-closed
bleibt byte-genau, und der IssuerRefused-Rescue fällt vor dem Loopback-Default auf die
Ableitung.

## Was passiert ist

1. **Task 1 (test-first, `dac73f5` -> `cfb74aa`):** Validierungskern aus
   `config_values._public_url` in `_validated_address` extrahiert (eine Regel, zwei
   Log-Texte, `_rejected`-Wortlaut byte-genau erhalten); neue Funktion
   `derived_public_url(env)` in `__all__`. Ableitung nur bei `NEXTCLOUD_URL` + `APP_ID`,
   fail-soft, Ablehnung als eine INFO-Zeile mit Variablenname und Grund, nie dem Wert.
2. **Task 2 (test-first, `62ed52b` -> `5063a9f`):** Helper
   `_fill_public_url_from_derivation(resolved)` als drittes Kettenglied in
   `entry_exapp._resolved_env` nach dem Overlay-Merge; derselbe Helper im
   IssuerRefused-Rescue nach dem Drop der unbrauchbaren Deploy-Variable
   (Exchange-Zweig bleibt SystemExit(2)). A2-Kommentar ersetzt (Sorge benannt, Antwort
   benannt: Validierung statt Vertrauen). Setup-State-Fehlerzeile und Rescue-Text nennen
   jetzt drei Quellen mit der Präzedenzregel; INFO-Zeile sagt, wenn die Ableitung gewonnen
   hat (Variablennamen, nie Werte, T-05-21).
3. **Task 3 (`6b215f8`):** `docs/oauth-setup.md` (Vier-Quellen-Tabelle, drei Muss-Fälle:
   internes/http `NEXTCLOUD_URL`, Split-Domain, eigener Präfix), `docs/exapp-install.md`
   (Z. 25ff Ableitung als Default, `--env` als Override; Z. 639 Store-Pfad-Absatz
   angepasst), `docs/faq.md` ("usually no"), `appinfo/info.xml` ("Required for OAuth"
   ersetzt, Kommentarblock Z. 454 mitgezogen), `strings.ADMIN_FIELD_PUBLIC_URL_DESCRIPTION`
   (leer = abgeleitet, setzen = überschreiben, disable/enable-Preis bleibt genannt),
   CHANGELOG-Unreleased-Eintrag mit Issue-#4-Linie und Fail-closed-Regel.

## Rot-Beweise je RED/GREEN-Paar

- **Paar 1 (`dac73f5` -> `cfb74aa`):** RED = 16 failed / 93 passed in
  `tests/unit/test_exapp_config_values.py`, alle 16 mit
  `AttributeError: module 'mcp_connector.exapp.config_values' has no attribute
  'derived_public_url'`; alle 93 Bestandstests grün. GREEN = 109 passed.
- **Paar 2 (`62ed52b` -> `5063a9f`):** RED = 6 failed / 134 passed in
  `tests/unit/test_exapp_entry.py`. Rot waren genau die sechs Verhaltens-Tests
  (derived-address-served, refused-admin-fallback, Setup-State nennt dritte Quelle,
  Rescue-auf-Ableitung, Drei-Quellen-Rescue-Zeile, Quelle-gewonnen-INFO-Zeile); die drei
  Präzedenz-Pins (Formwert gewinnt, Variable gewinnt, Rescue-Default ohne ableitbare
  Adresse) waren konstruktionsbedingt schon grün, weil sie heutiges Verhalten festnageln.
  GREEN = 249 passed (beide Zieldateien zusammen).

## Gate-Ergebnisse (alle grün, vor dem letzten Code-Commit)

- Volle Suite `uv run pytest tests/unit tests/contract`: **3912 passed, 33 skipped** (133 s)
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 251 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: leer (Exit 0, wie CI)
- Task-3-Verify: `grep -c "Required for OAuth" appinfo/info.xml` = 0

## Gegenproben mit unabhängigem Muster (Plan-Vorgabe)

- `grep -rn "exapps/" src/ | grep -v test`: der Suffix `/exapps/<APP_ID>` wird im Code nur
  an EINER Stelle gebaut (`config_values.py:428`); alle anderen Treffer sind
  Doku/Beispiele/Kommentare.
- `grep -rn "derived" src/mcp_connector`: keine Halbverdrahtung; die neuen Stellen sind
  `config_values.derived_public_url`, der Helper und die drei Textstellen in `entry_exapp`.
- `grep -rn "NC_MCP_PUBLIC_URL" README* docs/ appinfo/ src/`: README/README.de/README.fr
  ohne Treffer (wie im Plan vermutet). `docs/client-setup.md:152/174` (Standalone-Modus
  bzw. Host-Fix), `docs/staging-setup.md`, `docs/conference-demo.md`, `docs/n8n-setup.md`,
  `docs/standalone-oauth.md`, `docs/spike-discovery.md` geprüft und bewusst NICHT
  angefasst: dort ist der Satz weiterhin faktisch richtig (Standalone-Modus hat kein
  `APP_ID`, also keine Ableitung; die übrigen sind Messprotokolle/Troubleshooting).

## Bewusste Abweichungen vom Plan

1. **RED-Commits ohne pyright/vulture-Lauf:** Die RED-Tests referenzieren ein noch nicht
   existierendes Symbol, pyright wäre auf dem RED-Stand zwangsläufig rot. Repo-Konvention
   belegt (z. B. `ccbde94`, test-only RED mit noch nicht existierendem `CLASS_EXCHANGE`).
   Auf beiden RED-Ständen liefen `ruff check` und `ruff format --check` grün; ab jedem
   GREEN-Commit alle fünf Hausgates vollständig grün.
2. **Test-Harness-Erweiterung (im RED-Commit `62ed52b`):** Die autouse-Fixture
   `admin_config` beantwortet den OCS-Admin-Value-Read zusätzlich auf der ableitbaren
   Basis (`DERIVED_READ_URL`), weil der Read der `NEXTCLOUD_URL` folgt und eine
   unbeantwortete respx-Route den Start aus einem testfremden Grund gestoppt hätte. Im
   Plan nicht explizit vorgesehen, für die neuen Tests notwendig.
3. **info.xml-Kommentarblock (Z. 447ff) mit angepasst:** Der Plan nannte nur die
   Description (Z. 489); der Kommentar darüber behauptete dieselbe Pflicht ("has to be set
   on every installation") und fiel unter die Gegenprobe-Anweisung.
4. **Keine Anpassung bestehender Wortlaut-Assertions nötig:** Der Plan erwartete
   "höchstens Assertion-Anpassungen" an Setup-State-/IN-02-Tests. Die neuen Texte behalten
   die gepinnten Fragmente ("no public address is stored in Nextcloud either", "wins
   over", disable/enable-Kommandos), alle Bestandstests blieben unverändert grün.

## Self-Check: PASSED

- Alle 5 Commits in `git log` vorhanden (dac73f5, cfb74aa, 62ed52b, 5063a9f, 6b215f8)
- `derived_public_url` in `config_values.__all__`, Helper in `entry_exapp` verdrahtet
- Volle Suite nach dem letzten Code-Commit grün

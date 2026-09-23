---
quick: 260923-ci-store-mode-hotfix
type: execute
autonomous: true
files_modified:
  - tests/unit/test_oauth_exchange_binding.py
  - tests/unit/test_oauth_exchange_enroll.py
---

# CI-Hotfix: Strict-Opener verweigert die von Tests gesaete Store-Datei (nur POSIX)

## Ziel

Der Unit-Job der CI ist auf main (8a6696c) rot, lokal (Windows) gruen. Zwei Tests
aus Phase 23 saeen die Bindung ueber einen direkten `OAuthStore(path, key)`-Zugriff;
SQLite legt die Datei dabei unter Linux mit dem umask-Default (0644) an. Die gebaute
Anwendung oeffnet denselben Pfad danach strict, und `store._prepare_private_file`
verweigert jede Datei mit Group/Other-Bits, aber nur auf POSIX (`os.name != "nt"`,
store.py ~2028). Ergebnis in der CI: `StoreFileRefused` in exchange_binding.py:65,
Identitaet None, 401 statt 200.

Fehlbilder (CI-Log, Run auf 8a6696c):
- `tests/unit/test_oauth_exchange_binding.py::test_with_a_binding_the_same_token_passes_the_boundary_of_the_built_app`: assert 401 != 401
- `tests/unit/test_oauth_exchange_enroll.py::test_the_same_exchanged_token_is_accepted_before_and_refused_after_revocation`: assert 401 == 200

## Task 1: Die gesaete Store-Datei owner-only anlegen

**Aenderung:** In beiden Testdateien an der Stelle, an der die Bindung vorab in die
Store-Datei der gebauten Anwendung geschrieben wird (binding: Helfer `app_store`,
Zeile ~414ff; enroll: die Messstelle Zeile ~1016, NICHT der Helfer Zeile 59, dessen
Datei nie strict geoeffnet wird, nur anfassen falls doch), die Datei VOR dem ersten
OAuthStore-Zugriff owner-only anlegen, im Repo-Idiom der Nachbarstellen
(`key_file.chmod(0o600)`, binding.py:399 / enroll.py:953):

    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(0o600)

Kein Eingriff in src/. Der Kommentar am Helfer nennt den Grund in einem Satz
(der Strict-Opener der Anwendung verweigert Group/Other-Bits auf POSIX).

**Verifikation:**
1. Beide genannten Tests gruen: `uv run pytest tests/unit/test_oauth_exchange_binding.py tests/unit/test_oauth_exchange_enroll.py`
2. Volle Gates: `uv run pytest tests/unit tests/contract` (0 failed), `uv run ruff check .`, `uv run ruff format --check .`, `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`, `uv run vulture src scripts vulture_whitelist.py`
3. Beweisfuehrung fuer den eigentlichen Fehler (Windows kann den POSIX-Ast nicht
   ausfuehren): per Grep belegen, dass jede Stelle, die dieselbe Store-Datei sowohl
   direkt als auch ueber die gebaute App oeffnet, jetzt vorher chmod 0600 setzt;
   Suchmuster `OAuthStore(tmp_path` ueber beide Dateien, jede Fundstelle einordnen.

**Commit:** `fix(tests): seed the app store file owner-only so the strict opener accepts it on POSIX`

## Task 2: SUMMARY

SUMMARY.md in diesem Verzeichnis (status: complete), STATE.md-Tabelle "Quick Tasks
Completed" ergaenzen, beides als `docs(quick)`-Commit.

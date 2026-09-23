---
type: quick
status: complete
date: 2026-09-23
task: CI-Hotfix, der Strict-Opener verweigert die von zwei Phase-23-Tests gesäte Store-Datei (nur POSIX)
commits:
  - 1bec2d3: "fix(tests): seed the app store file owner-only so the strict opener accepts it on POSIX"
files_modified:
  - tests/unit/test_oauth_exchange_binding.py
  - tests/unit/test_oauth_exchange_enroll.py
duration: 15 min
---

# CI-Hotfix: gesäte Store-Datei owner-only - Summary

**Einzeiler:** Die beiden Phase-23-Tests, die die Bindung vorab in die Store-Datei der
gebauten Anwendung schreiben, legen diese Datei jetzt vor dem ersten OAuthStore-Zugriff
mit `touch()` + `chmod(0o600)` an, damit `_prepare_private_file` sie auf POSIX nicht mehr
mit `StoreFileRefused` verweigert. Kein Eingriff in `src/`.

## Der Fehler

`store._prepare_private_file` (src/mcp_connector/oauth/store.py:2007) verweigert jede
bestehende Store-Datei mit Group- oder Other-Bits, aber nur auf POSIX
(`if os.name != "nt" and status.st_mode & (stat.S_IRWXG | stat.S_IRWXO)`). Beide Tests
säten die Bindung über einen direkten `OAuthStore(...)`-Zugriff; SQLite legt die Datei
dabei unter Linux mit dem umask-Default 0644 an. Die danach gebaute Anwendung öffnet
denselben Pfad strict, bekommt `StoreFileRefused` in exchange_binding.py:65, löst keine
Identität auf und antwortet 401. Unter Windows ist der Check aus, darum lokal grün.

## Was passiert ist (Task 1, Commit `1bec2d3`)

1. **binding, Helfer `app_store`:** Der Pfad wird in eine lokale Variable gehoben,
   `path.parent.mkdir(parents=True, exist_ok=True)` / `path.touch()` / `path.chmod(0o600)`
   laufen vor der Konstruktion, der Docstring nennt den Grund in einem Satz. Idiom wie an
   den Nachbarstellen (`key_file.chmod(0o600)`, binding.py:399).
2. **enroll, Messstelle im Revocation-Test (jetzt Zeile 1019ff):** Dieselben drei Zeilen
   vor `OAuthStore(store_path, ...)`, mit Kommentar. Der Helfer in Zeile 59 wurde
   bewusst NICHT angefasst: seine Datei (`tmp_path / STORE_FILE`, ohne `storage/`) wird
   von keiner gebauten Anwendung strict geöffnet.

SQLite gibt seinen `-wal`- und `-shm`-Dateien die Rechte der Datenbankdatei, die Mode
0600 trägt also die ganze Store-Familie.

## Beweisführung (Windows kann den POSIX-Ast nicht ausführen)

Diskriminator ist nicht das Konstrukt, sondern der Pfad: strict geöffnet wird
ausschliesslich die Datei im konfigurierten Storage-Verzeichnis
(`ENV_OAUTH_STORAGE_DIR` = `tmp_path / "storage"`). Suchmuster `tmp_path / "storage"`
und `OAuthStore(tmp_path` über die Testsuite, jede Fundstelle eingeordnet:

| Fundstelle | Pfad | Einordnung |
|---|---|---|
| binding.py:394 (`standalone_env`) | `tmp_path/"storage"` (Verzeichnis) | Nur das Verzeichnis, bereits `chmod(0o700)`. Unverändert. |
| binding.py:421 (`app_store`) | `tmp_path/"storage"/oauth.sqlite3` | **Die Stelle.** Sät direkt UND die App öffnet strict, jetzt touch + chmod 0600. GEDECKT. |
| binding.py:430 (`app_store_rows`) | derselbe Pfad | Nur lesend (`sqlite3.connect` zum Zählen) und durch `if not path.exists(): return 0` gegen ein Anlegen abgesichert. Erzeugt die Datei nie. |
| binding.py:61 (`open_store`) | `tmp_path/oauth.sqlite3` | Anderer Pfad, ausserhalb des Storage-Verzeichnisses; keine gebaute App öffnet ihn. Nicht betroffen. |
| enroll.py:948 (`measure_env`) | `tmp_path/"storage"` (Verzeichnis) | Nur das Verzeichnis, bereits `chmod(0o700)`. Unverändert. |
| enroll.py:1019 (Revocation-Messung) | `tmp_path/"storage"/oauth.sqlite3` | **Die Stelle.** Sät direkt UND die App öffnet strict, jetzt touch + chmod 0600. GEDECKT. |
| enroll.py:59/64/66/74/76 | `tmp_path/oauth.sqlite3` | Helfer plus zwei Zeilenzähler auf dem Pfad ausserhalb `storage/`; nie strict geöffnet. Nicht betroffen. |
| chain.py:965 (`standalone_env`) | `tmp_path/"storage"` (Verzeichnis) | Legt nur das Verzeichnis an und sät keine Store-Datei; die Datei erzeugt der Strict-Opener selbst per `O_EXCL` mit 0600. Nicht betroffen. |

Damit gilt repoweit: jede Stelle, die dieselbe Store-Datei direkt UND über die gebaute
App öffnet, setzt vorher 0600. Eine dritte solche Stelle existiert nicht.

## Gates (vor dem Commit, alle grün)

- uv run pytest tests/unit/test_oauth_exchange_binding.py tests/unit/test_oauth_exchange_enroll.py: 52 passed
- uv run pytest tests/unit tests/contract: 4162 passed, 33 skipped, 0 failed (127,97 s)
- uv run ruff check .: All checks passed
- uv run ruff format --check .: 263 files already formatted
- PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright: 0 errors, 0 warnings, 0 informations
- uv run vulture src scripts vulture_whitelist.py: exit 0, keine Befunde

## Abweichungen vom Plan

Keine inhaltliche Abweichung. Eine Präzisierung bei der Beweisführung: das vom Plan
genannte Suchmuster `OAuthStore(tmp_path` findet die beiden reparierten Stellen nach der
Änderung nicht mehr, weil beide den Pfad in eine Variable heben. Die Beweisführung läuft
deshalb über den Pfadausdruck `tmp_path / "storage"` (den eigentlichen Diskriminator)
plus das Originalmuster, beide über die ganze Testsuite statt nur über die zwei Dateien.
Das ist strenger, nicht schwächer.

## Self-Check: PASSED

Commit 1bec2d3 existiert, beide genannten Testdateien vorhanden und geändert, keine
weitere Datei berührt (`git show --stat`: 2 files changed, 19 insertions, 3 deletions),
Gates lokal grün.

---
phase: 31-ordner-anlegen
plan: 04b
type: execute
wave: 5
depends_on: ["31-04"]
files_modified:
  - src/mcp_connector/tools/files.py
  - tests/unit/test_files_create_folder.py
  - tests/unit/test_files_create_folder_exclusion.py
  - .planning/phases/31-ordner-anlegen/31-CONTEXT.md
autonomous: true
requirements: [FOLD-02]

must_haves:
  truths:
    - "Bricht das Netz während eines MKCOL von files.create_folder ab (httpx.RequestError, darunter httpx.TimeoutException; genau die beiden Klassen, die @graceful unterscheidet), endet der Aufruf in einem ToolError, der zwei Dinge trennt: das Segment, dessen Zustand unbekannt ist, und die in diesem Aufruf sicher angelegten Ordner"
    - "Die Liste des Angelegten läuft unverändert durch die bestehende Hülle _with_created (Zusatz 'Already created in this call and left in place: <Pfade>.'); ist sie leer, sagt die Meldung ausdrücklich, dass in diesem Aufruf kein anderer Ordner angelegt wurde"
    - "Bricht das Netz während des ersten MKCOL ab (Kette oder Aufruf ohne parents), nennt die Antwort dieses Segment als unbekannt und nichts als angelegt"
    - "Bricht das Netz bei einem Lesezugriff zwischen zwei Segmenten ab (PROPFIND nach 405), ist nichts unbekannt: die Meldung nennt nur das Angelegte; ist dabei noch nichts angelegt, bleibt das bisherige Verhalten (die httpx-Ausnahme läuft zu @graceful)"
    - "Ein Netzfehler vor jedem Schreiben (Zählung, Lesen der Sandbox-Wurzel) läuft unverändert als httpx-Ausnahme zu @graceful"
    - "Der Hinweis nennt den erneuten Aufruf als gefahrlos: in der Kette mit demselben Pfad und parents=true, ohne parents mit demselben Pfad"
    - "reason bleibt timeout bzw. unreachable, die Audit-Klasse des Aufrufs ändert sich also nicht"
    - "Ein Netzfehler beim Nachlesen der Id nach erfolgreichem Anlegen bleibt ein Erfolg ohne id (31-02)"
    - "Ein getaggter oder ausgeschlossener Pfad wird vor jedem Request abgelehnt; ein Netzfehler an der MKCOL-Route ändert daran nichts (MKCOL 0, exakt parent_missing bzw. unavailable_error)"
    - "Docstring des Werkzeugs, Server-Instruktion, dav.py und die MKCOL-Nadel bleiben unverändert; das Budget bleibt 16222 Bytes bei 24 Werkzeugen"
  artifacts:
    - path: "src/mcp_connector/tools/files.py"
      provides: "Netzzweig in create_folder, Fabrik _cut_off"
      contains: "def _cut_off"
    - path: "tests/unit/test_files_create_folder.py"
      provides: "Netzfälle der Kette und des einzelnen Ordners"
      contains: "is unknown"
    - path: "tests/unit/test_files_create_folder_exclusion.py"
      provides: "Ausschluss bleibt im Netzfall fail-closed"
      contains: "ConnectError"
  key_links:
    - from: "src/mcp_connector/tools/files.py create_folder"
      to: "src/mcp_connector/tools/files.py _with_created"
      via: "der Netzfall wird zu einem ToolError und läuft durch dieselbe Hülle"
      pattern: "_with_created\\(_cut_off"
---

<objective>
Netzfehler mitten in der Ordnerkette von `files_create_folder` nennen das bereits Angelegte und trennen es vom Segment, dessen Zustand unbekannt ist (Owner-Entscheid vom 2026-11-12, offener Punkt aus 31-02-SUMMARY.md).

Purpose: Ein Assistent, der nach einem Timeout nur "Nextcloud did not respond in time" liest, weiß nicht, dass schon Ordner stehen und dass der abgebrochene MKCOL den Server erreicht haben kann. Mit der neuen Meldung kann er gefahrlos wiederholen.
Output: geänderte `files.py`, erweiterte Unit-Tests, ein Satz in 31-CONTEXT.md.
</objective>

<context>
@.planning/phases/31-ordner-anlegen/31-CONTEXT.md
@.planning/phases/31-ordner-anlegen/31-02-PLAN.md
@.planning/phases/31-ordner-anlegen/31-02-SUMMARY.md

Rahmen wie in 31-01-PLAN.md, Abschnitt "Rahmen für alle Pläne der Phase 31" (Worktree, uv run --no-sync, PYTHONPATH=src, PYTHONUTF8=1, Commit-Regeln, keine Dashes, Diff-Prüfungen gegen 31-BASE.txt mit Positivkontrolle). Dieser Plan startet kein Docker und fasst STATE.md, ROADMAP.md, 31-05-PLAN.md und 31-06-PLAN.md nicht an.

Am Code geprüft (2026-11-12):
- `dav.make_folder` und `dav.probe_folder` rufen `client.request` ohne eigene Fehlerbehandlung; eine httpx-Ausnahme steigt unverändert auf.
- `@graceful` (server/__init__.py) fängt `httpx.TimeoutException` (reason timeout, "Nextcloud did not respond in time.") und danach `httpx.RequestError` (reason unreachable, "Could not reach Nextcloud."). `TimeoutException` und `TransportError` sind Unterklassen von `RequestError`; diese eine Klasse deckt also alles, was der Client hier wirft.
- Die Hülle `_with_created(err, created)` gibt bei leerer Liste das Objekt unverändert zurück und hängt sonst den Zusatz an; hint und reason bleiben.
- `_writable` in der Schleife nutzt die gecachte Antwort des Aufrufs und fängt httpx-Fehler selbst (unavailable_error).

Wortlaut (Englisch, Code):
- MKCOL unterwegs, Timeout: "Nextcloud did not respond in time while creating {segment}; whether that folder exists now is unknown."
- MKCOL unterwegs, sonstiger Netzfehler: "Could not reach Nextcloud while creating {segment}; whether that folder exists now is unknown."
- dazu bei leerer Liste: " No other folder was created in this call."; sonst der Zusatz der Hülle
- kein MKCOL unterwegs, etwas angelegt: "Nextcloud did not respond in time." bzw. "Could not reach Nextcloud." plus Zusatz der Hülle
- hint Kette: "Call again with the same path and parents=true; that is safe: folders that exist are kept and only the missing ones are created."
- hint ohne parents: "Call again with the same path; that is safe: a folder that exists is kept."
- reason: REASON_TIMEOUT bzw. REASON_UNREACHABLE
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Netzzweig in create_folder, testgetrieben</name>
  <files>src/mcp_connector/tools/files.py, tests/unit/test_files_create_folder.py, tests/unit/test_files_create_folder_exclusion.py</files>
  <behavior>
    - Kette, ReadTimeout am zweiten MKCOL: message "Nextcloud did not respond in time while creating /A/b/c; whether that folder exists now is unknown. Already created in this call and left in place: /A/b.", reason timeout, hint der Kette, kein dritter MKCOL
    - Kette, Verbindungsabbruch (ReadError) am dritten MKCOL: "Could not reach Nextcloud while creating /A/b/c/d; ... unknown. Already created in this call and left in place: /A/b, /A/b/c.", reason unreachable
    - Kette, Abbruch am ersten MKCOL (Timeout und ConnectError): "... while creating /A/b; whether that folder exists now is unknown. No other folder was created in this call."; "Already created" kommt nicht vor
    - Ohne parents, Abbruch am MKCOL: dasselbe mit dem Ziel und dem Hinweis ohne parents
    - Kette, 405 am zweiten Segment und Netzfehler beim folgenden PROPFIND: "Could not reach Nextcloud. Already created in this call and left in place: /A/b."; das Wort "unknown" kommt nicht vor
    - Kette, 405 am ersten Segment und Netzfehler beim folgenden PROPFIND: die httpx-Ausnahme steigt unverändert auf
    - Netzfehler in der Zählung und beim Lesen der Sandbox-Wurzel: die httpx-Ausnahme steigt unverändert auf, kein MKCOL
    - Ohne parents, 405 und Netzfehler beim PROPFIND: die httpx-Ausnahme steigt unverändert auf
    - Kette, letztes 201 ohne oc-fileid und Netzfehler beim Nachlesen der Id: Erfolg ohne id mit vollständiger Liste
    - Ausschluss: getaggtes Ziel mit einer MKCOL-Route, die ConnectError wirft, ergibt exakt parent_missing(Ziel) bei MKCOL 0 und PROPFIND 0 (ohne und mit parents); nicht beantwortbare Prüfung ergibt unavailable_error bei MKCOL 0; Positivkontrolle: derselbe Aufruf ohne Tag erreicht die Route (MKCOL 1) und endet im Netzzweig
  </behavior>
  <action>
Tests zuerst schreiben und rot sehen (Ausgabe für den Bericht festhalten), dann in tools/files.py:
- `create_folder`: um den MKCOL des Zweigs ohne parents ein `except httpx.RequestError`, das `_cut_off(exc, target, [], chain=False)` wirft. In der Schleife der Kette merkt sich eine Variable, ob gerade ein MKCOL unterwegs ist; `except httpx.RequestError`: ist keiner unterwegs und nichts angelegt, die Ausnahme unverändert weiterreichen, sonst `_with_created(_cut_off(...), created)`. Die bestehenden Zweige (`except ToolError`) bleiben Zeile für Zeile, wie sie sind. Immer `from None` (T-01-07: ein httpx-Traceback kann die URL tragen).
- `_cut_off(exc, unknown, created, *, chain) -> ToolError` baut Meldung, Hinweis und reason nach dem Wortlaut im Kontextabschnitt.
- Docstring von create_folder: ein Absatz zum Netzfall. dav.py bleibt unberührt.
Mutationsprobe: beide neuen `except`-Zweige entfernen, neue Tests rot sehen, mit `git checkout -- src/mcp_connector/tools/files.py` nach dem Commit wiederherstellen (oder die Änderung von Hand zurücknehmen und den Diff auf leer prüfen).
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_files_create_folder.py tests/unit/test_files_create_folder_exclusion.py tests/unit/test_dav_make_folder.py tests/unit/test_pair_equality_files.py tests/contract/test_no_destructive_calls.py -q</automated>
  </verify>
  <acceptance_criteria>
    - Die neuen Tests sind vor der Umsetzung rot und danach grün; kein bestehender Test wurde geändert
    - `git diff HEAD~1 -- src/mcp_connector/nextcloud/clients/dav.py tests/contract/test_no_destructive_calls.py` ist leer
    - Mutationsprobe rot gesehen, Stand danach wieder grün
  </acceptance_criteria>
  <done>Jeder Netzabbruch nach oder während eines Schreibens nennt das Angelegte und das Unbekannte getrennt; alles davor verhält sich wie bisher.</done>
</task>

<task type="auto">
  <name>Task 2: Voller Lauf R1 und Diff-Prüfung mit Positivkontrolle</name>
  <files>(keine)</files>
  <action>
`pytest tests/unit tests/contract` (Zahl mit überschriebenem addopts), `scripts/check_tool_budget.py`, ruff check, ruff format --check, pyright, vulture. Diff gegen `B=$(cat .planning/phases/31-ordner-anlegen/31-BASE.txt)` nach Positivkontrolle der Basis: Server-Instruktion und Docstring von `files_create_folder` in `server/reg_files.py` gegenüber dem Stand nach 31-03 (Commit 620ab4e) unverändert; Gegentreffer im selben Diff gegen die Basis (`+async def files_create_folder`, `+def _cut_off`).
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit tests/contract -q && uv run --no-sync python scripts/check_tool_budget.py && uv run --no-sync ruff check . && uv run --no-sync ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright && uv run --no-sync vulture src scripts vulture_whitelist.py</automated>
  </verify>
  <acceptance_criteria>
    - Alle Gates Exit 0; Budget 16222 Bytes, 24 Werkzeuge
    - `git diff 620ab4e HEAD -- src/mcp_connector/server/reg_files.py src/mcp_connector/server/__init__.py` ist leer
  </acceptance_criteria>
  <done>Der Stand ist vollständig grün, die Oberfläche auf dem Draht unverändert.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-31-09 | Repudiation | halbe Kette nach Netzabbruch bleibt unbemerkt | mitigate | Netzfall läuft durch _with_created; Segment mit unbekanntem Zustand benannt |
| T-31-02 | Information Disclosure | Netzzweig als Orakel für ausgeschlossene Pfade | mitigate | _writable vor jedem Request bleibt; Test mit werfender MKCOL-Route und Zähler 0 |
| T-31-12 | Information Disclosure | URL oder httpx-Text in der Meldung | mitigate | eigene Sätze, nur Pfade, die die bestehenden Abbruchmeldungen schon nennen; from None |
</threat_model>

<verification>
- Neue Netzfälle grün, bestehende Tests unverändert grün
- Voller Lauf nach R1 grün, Budget unverändert
</verification>

<success_criteria>
- FOLD-02 gilt auch für Netzfehler: die Antwort nennt das Angelegte und trennt es vom Unbekannten
</success_criteria>

<output>
Create `.planning/phases/31-ordner-anlegen/31-04b-SUMMARY.md` when done
</output>

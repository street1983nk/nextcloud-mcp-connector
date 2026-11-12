---
phase: 31-ordner-anlegen
plan: 05b
type: execute
wave: 6
depends_on: ["31-05"]
files_modified:
  - src/mcp_connector/tools/files.py
  - tests/unit/test_files_create_folder.py
  - tests/unit/test_files_create_folder_exclusion.py
  - tests/unit/test_pair_equality_files.py
  - tests/integration/test_files_create_folder_live.py
  - scripts/acceptance_all_tools.py
  - docs/folder-evidence.md
  - .planning/phases/31-ordner-anlegen/raw/nc35-nacharbeit.txt
  - .planning/phases/31-ordner-anlegen/raw/nc32-nacharbeit.txt
  - .planning/phases/31-ordner-anlegen/31-CONTEXT.md
autonomous: true
requirements: [FOLD-01, FOLD-05]

must_haves:
  truths:
    - "files_create_folder lehnt einen Zielpfad VORAB ab, in dem ein Segment am Anfang oder Ende Leerraum trägt (genau das, was str.strip() entfernt, also dieselbe Menge, die safe_path am Pfadende kürzt): eigene Meldung, kein einziger Request, nichts angelegt, mit und ohne parents, für jedes Segment (D-31-08)"
    - "Die Ablehnung läuft nach den bestehenden Syntaxprüfungen (safe_path, Wurzel) und vor dem Ausschluss-Wächter; sie hängt nur an der Eingabe, ein getaggter und ein erfundener Elternordner antworten deshalb gleich, und ein nicht beantwortbarer Wächter ändert nichts daran, dass nichts geschrieben wird"
    - "safe_path ist unverändert (dav.py ohne Diff); alle anderen Werkzeuge kürzen wie bisher; Leerraum im Inneren eines Namens und ein Punkt am Ende bleiben erlaubt, weil safe_path sie nicht verändert"
    - "Ein Nicht-Ordner am Pfad OHNE gültige Datei-Id (Antwortbild von x.part: MKCOL 405, PROPFIND 207 ohne Ordnertyp, Id -1 auf 35, keine Id auf 32) bekommt einen Satz, der keine Datei behauptet; ein Nicht-Ordner MIT gültiger Datei-Id bleibt wörtlich 'A file, not a folder, already exists at <Pfad>.' (D-31-09)"
    - "scripts/acceptance_all_tools.py ruft alle 24 Werkzeuge, nimmt für fetch die Id der hochgeladenen Datei statt des ersten Treffers und endet auf einer vollständigen Testinstanz mit Exit 0; eine fehlende Voraussetzung der Instanz beim Mailabruf steht als eigene, benannte Zeile da und wird weder als Werkzeugfehler noch still als Erfolg gezählt"
    - "Auf Nextcloud 35 und 32 live nachgemessen: (a) und (b) am echten Werkzeug mit Dateisystemprobe, der Live-Test komplett, Kanarie und Live-Paar mit NC_MCP_REQUIRE_LIVE=1, das Abnahmeskript auf 32; am Ende läuft keine eigene Instanz"
    - "Docstring des Werkzeugs auf dem Draht, Server-Instruktion, dav.py und die MKCOL-Nadel bleiben unverändert; Budget 16222 Bytes bei 24 Werkzeugen"
  artifacts:
    - path: "src/mcp_connector/tools/files.py"
      provides: "Vorabprüfung _padded_name, Fabriken _name_padded und _in_the_way"
      contains: "def _padded_name"
    - path: "tests/unit/test_files_create_folder.py"
      provides: "Fälle zu Leerraum am Rand und zum Knoten ohne Datei-Id"
      contains: "starts or ends with whitespace"
    - path: "docs/folder-evidence.md"
      provides: "Abschnitt der Nachmessung, Befunde als behoben gekennzeichnet"
      contains: "## Follow-up run"
  key_links:
    - from: "src/mcp_connector/tools/files.py create_folder"
      to: "src/mcp_connector/tools/files.py _writable"
      via: "die Namensprüfung steht vor dem ersten _writable und vor jedem Request"
      pattern: "_padded_name\\(path\\)"
---

<objective>
Drei Nacharbeiten aus dem Live-Beweis 31-05 (Owner-Entscheid vom 2026-11-12, wörtlich "Ok"): (a) Ordnernamen mit Leerraum am Rand vorab ablehnen statt still kürzen (Befund 2), (b) den Satz für Namen wie `x.part` richtigstellen (Befund 5), (c) das Abnahmeskript auf Exit 0 bringen (Befund 3).

Purpose: Die Meldung des Werkzeugs soll nie einen Ordner nennen, den es unter diesem Namen nicht gibt, und nie eine Datei, die es nicht gibt. Das Abnahmeskript ist das einzige, das jedes Werkzeug über stdio ruft; ein Skript, das immer rot endet, prüft nichts.
Output: geänderte `files.py`, Unit-Tests, angepasster Live-Test, korrigiertes Skript, zwei neue Rohprotokolle, ergänzte Evidenzseite.
</objective>

<context>
@.planning/phases/31-ordner-anlegen/31-CONTEXT.md
@.planning/phases/31-ordner-anlegen/31-05-PLAN.md
@.planning/phases/31-ordner-anlegen/31-05-SUMMARY.md
@docs/folder-evidence.md

Rahmen wie in 31-01-PLAN.md, Abschnitt "Rahmen für alle Pläne der Phase 31" (Worktree, uv run --no-sync, PYTHONPATH=src, PYTHONUTF8=1, Commit-Regeln, RAM-Gate 4 GB, nur EINE Instanz, nie down, Diff-Prüfungen gegen 31-BASE.txt mit Positivkontrolle). Form der Live-Läufe wie in 31-05 (Start nc35 per docker start, Strecke 32 per `docker compose -f compose.exapp.yml start` plus lokalem Prozess auf 127.0.0.1:23001, kein Bootstrap). Ausgaben der Live-Läufe gehen zuerst in eine Zwischendatei außerhalb des Repos, werden gegen die Werte der Env-Dateien geprüft und erst dann angehängt. STATE.md, ROADMAP.md und 31-06-PLAN.md bleiben unberührt.

Am Code und an den Rohprotokollen geprüft (2026-11-12):
- `dav.safe_path` kürzt den GANZEN Pfad mit `str.strip()` (Leerzeichen, Tab, Zeilenumbruch und jeder Unicode-Leerraum an beiden Enden), nie einzelne Segmente, und nie einen Punkt. Steuerzeichen prüft es erst nach dem Kürzen. Abweichen kann der angelegte Name deshalb nur am Pfadende, und in der Kette an jedem Glied, weil das Werkzeug dort jedes Glied als eigenen Pfad baut.
- Nextcloud 35 und 32 legen einen Namen mit Leerzeichen am Ende selbst an (raw/nc35-ordner.txt Zeile 82 bis 85, raw/nc32-ordner.txt Zeile 138 bis 141: MKCOL 201, im Dateisystem `mitte-leer ` mit Leerzeichen). Die Ablehnung ist also eine Regel des Werkzeugs, nicht des Servers; der Satz darf deshalb nicht "Nextcloud does not accept" lauten.
- `x.part`: MKCOL 405 `MethodNotAllowed` "The resource you tried to create already exists"; PROPFIND 207 mit leerem `resourcetype`, auf 35 mit `fileid=-1`, auf 32 ohne Id; im Dateisystem nichts (raw/nc35-ordner.txt Zeile 72 bis 81, raw/nc32-ordner.txt Zeile 128 bis 137). Eine echte Datei trägt eine positive Id.

Auslegungen (konservative Lesart):
- (a) Abgelehnt wird jedes Segment des übergebenen Pfads mit `segment != segment.strip()`, auch ein Segment nur aus Leerraum und auch Leerraum vor dem ersten Schrägstrich. Weitere Namensregeln gibt es nicht.
- (b) Kein Umdeuten in "Name abgelehnt": das Antwortbild ist auf 33 und 34 nicht gemessen und "Nextcloud lehnt den Namen ab" wäre wieder eine Behauptung. Stattdessen sagt der Satz nur, was die zwei Antworten belegen. Fehlt einer echten Datei die Id, trifft sie derselbe Satz; er bleibt dann wahr.

Wortlaut (Englisch, Code):
- (a) message: "The folder name {segment!r} in {path!r} starts or ends with whitespace."; hint: "Remove the whitespace at the start and the end of every folder name and call again; nothing was created."; ToolError, reason unverändert Standard
- (b) message: "{path} cannot be created as a folder: Nextcloud reports an entry there that is not a folder."; hint: "Choose another name, for example one that does not end in .part; this tool never replaces anything."; ConflictError
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Leerraum am Rand eines Ordnernamens vorab ablehnen (a), testgetrieben</name>
  <files>src/mcp_connector/tools/files.py, tests/unit/test_files_create_folder.py, tests/unit/test_files_create_folder_exclusion.py, tests/unit/test_pair_equality_files.py</files>
  <behavior>
    - Ziel mit Leerzeichen am Ende, am Anfang, mit Tab, Zeilenumbruch, geschütztem Leerzeichen und U+3000 am Rand: die neue Meldung mit dem Segment und dem Pfad, kein Request (ohne und mit parents)
    - Mittleres und erstes Segment mit Leerraum am Rand, Segment nur aus Leerraum, Leerraum vor dem ersten Schrägstrich: dieselbe Meldung, kein Request
    - Sandbox gesetzt: dieselbe Meldung, kein Request
    - Bestehende Sätze behalten den Vorrang: leerer Pfad, Wurzel ("/ "), Traversal, Backslash, Steuerzeichen im Inneren
    - Positivkontrollen: Leerzeichen im Inneren eines Namens und ein Punkt am Ende gehen unverändert als MKCOL hinaus; ein Schrägstrich am Ende bleibt erlaubt; `dav.safe_path("/A/b ")` ist weiter "/A/b"
    - Ausschluss: getaggter Elternordner und Name mit Leerzeichen ergibt dieselbe Meldung wie ohne Tag, bei null Requests insgesamt; ein nicht beantwortbarer Wächter ebenso; Paarfall getaggt gegen erfunden gleich, MKCOL je 0
  </behavior>
  <action>
Tests zuerst, rot sehen und Ausgabe festhalten. Dann in tools/files.py: `_padded_name(path) -> str | None` (erstes Segment mit `segment != segment.strip()`, leere Segmente und "." übersprungen wie in safe_path) und `_name_padded(path, segment) -> ToolError`; Aufruf in `create_folder` nach der Wurzelprüfung und vor dem ersten `_writable`. Docstring von create_folder: ein Absatz. dav.py bleibt unberührt. Mutationsprobe: den Aufruf entfernen, neue Tests rot sehen, wiederherstellen (Diff leer).
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_files_create_folder.py tests/unit/test_files_create_folder_exclusion.py tests/unit/test_dav_make_folder.py tests/unit/test_pair_equality_files.py tests/contract/test_no_destructive_calls.py -q</automated>
  </verify>
  <acceptance_criteria>
    - Neue Tests vor der Umsetzung rot, danach grün; kein bestehender Test geändert (sonst einzeln genannt und begründet)
    - `git diff HEAD -- src/mcp_connector/nextcloud/clients/dav.py` ist leer
    - Mutationsprobe rot gesehen, Stand danach wieder grün
  </acceptance_criteria>
  <done>Kein Aufruf legt mehr einen Ordner unter einem anderen Namen an als verlangt.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Satz für den Nicht-Ordner ohne Datei-Id (b), testgetrieben</name>
  <files>src/mcp_connector/tools/files.py, tests/unit/test_files_create_folder.py</files>
  <behavior>
    - Ohne parents, 405 und PROPFIND 207 ohne Ordnertyp mit Id "-1", mit leerer Id und ohne Id-Element: der neue Satz, ConflictError, kein weiterer Request
    - Kette: so ein Knoten als Ziel und als Vorfahr in der Zählung: der neue Satz für diesen Knoten, kein MKCOL; nach einem 405 mitten in der Kette: der neue Satz plus Zusatz "Already created"
    - Sandbox-Wurzel als so ein Knoten: der neue Satz für die Wurzel
    - Ein Nicht-Ordner mit positiver Id: wörtlich der bisherige Satz (bestehende Tests unverändert)
  </behavior>
  <action>
Tests zuerst, rot sehen. Dann `_in_the_way(node) -> ConflictError`: gültige Id (`[1-9][0-9]*`) ergibt `_file_in_the_way(path)`, sonst der neue Satz; die drei Aufrufer von `_file_in_the_way` rufen `_in_the_way` mit dem gelesenen Knoten. Mutationsprobe: `_in_the_way` gibt immer `_file_in_the_way` zurück, neue Tests rot, wiederherstellen. Commit nach Task 1 und 2 je einzeln.
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_files_create_folder.py tests/unit/test_dav_make_folder.py -q</automated>
  </verify>
  <acceptance_criteria>
    - Neue Tests vor der Umsetzung rot, danach grün; die bestehenden Sätze "A file, not a folder" in den Tests unverändert
    - Mutationsprobe rot gesehen
  </acceptance_criteria>
  <done>Das Werkzeug nennt keine Datei mehr, wo keine belegt ist.</done>
</task>

<task type="auto">
  <name>Task 3: Abnahmeskript (c) und Live-Test anpassen</name>
  <files>scripts/acceptance_all_tools.py, tests/integration/test_files_create_folder_live.py</files>
  <action>
Skript: (1) die Id für `fetch` ist die des Treffers, dessen Pfad der hochgeladenen Datei gleicht; fehlt er, FAIL bei files_search. (2) `files_download` und `files_read_as_markdown` auf die hochgeladene Datei rufen (Argumente nach reg_files.py). (3) Mailabruf: Ursache in Task 4 an der Instanz untersuchen (GreenMail läuft? Postfach nach Neustart leer? Liste aus dem Cache der Mail-App?). Fehler des Skripts beheben; ist es die Instanz, meldet das Skript eine eigene Zeile PREREQ mit dem Grund und endet mit einem eigenen Exit-Code ungleich 0 und ungleich 1, ohne FAIL und ohne stilles Überspringen.
Live-Test: `namen` erwartet für `ende-leer ` und ` anfang-leer` die neue Meldung bei null Requests und nichts im Dateisystem (auch nicht unter dem gekürzten Namen), für `x.part` den neuen Satz; der Zusatzfall wird zur geprüften Messung (Kette und ohne parents, null Requests, Ordner danach leer, `befund=nein`); der Fall kein-ki vergleicht zusätzlich getaggt gegen erfunden mit Leerzeichen am Namensende. Jede geänderte Erwartung trägt ihren Grund als Kommentar (D-31-08, D-31-09).
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/integration/test_files_create_folder_live.py --collect-only -m integration -q && uv run --no-sync ruff check scripts tests && uv run --no-sync ruff format --check scripts tests && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright</automated>
  </verify>
  <acceptance_criteria>
    - Das Skript nennt jedes der 24 Werkzeuge der Registry in einem Aufruf; `fetch` der Datei hängt nicht mehr an der Reihenfolge der Treffer
    - Der Live-Test ist sammelbar, 18 Testfunktionen
  </acceptance_criteria>
  <done>Skript und Live-Test stehen für die Nachmessung bereit.</done>
</task>

<task type="auto">
  <name>Task 4: Nachmessung auf Nextcloud 35 und 32, Rohprotokolle, Evidenzseite</name>
  <files>.planning/phases/31-ordner-anlegen/raw/nc35-nacharbeit.txt, .planning/phases/31-ordner-anlegen/raw/nc32-nacharbeit.txt, docs/folder-evidence.md</files>
  <action>
Streng nacheinander, RAM-Gate vor jedem Docker-Schritt und nach jedem Start. Je Instanz: VERSION OF RECORD, Live-Test komplett, Kanarie und Live-Paar mit NC_MCP_REQUIRE_LIVE=1; die zwei Protokolle der Phase 28 danach per `git checkout -- <Datei>` zurücksetzen. Auf 32 zusätzlich: lokaler Prozess aus dem Worktree, tools/list (24 Werkzeuge, files_create_folder vorhanden), Ursache des Mailabrufs, Abnahmeskript mit Exit-Code. Danach stop (nie down), lokalen Prozess beenden, Geheimnisprüfung der neuen Dateien. Ein Messwert gegen den Entscheid: messen, belegen, anhalten, melden.
docs/folder-evidence.md: neuer Abschnitt "## Follow-up run" am Ende mit den Rohzeilen (wörtlich aus den neuen Protokollen); in "What the run found" die Punkte 3 und 4 und im Abschnitt Nextcloud 32 der Absatz zum Abnahmeskript als behoben mit Verweis kennzeichnen, keine Zeile löschen, kein Anker umbenannt; Statuszeile im Kopf ergänzen.
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && for R in nc35 nc32; do F=.planning/phases/31-ordner-anlegen/raw/$R-nacharbeit.txt; grep -q "VERSION OF RECORD" $F && grep -q "ZUSATZ name-mit-leerzeichen-in-kette" $F && ! grep -q "ergebnis=befund\|befund=ja" $F && ! grep -qi "unexpected status" $F || { echo "FEHLT in $R"; exit 1; }; done && test "$(docker ps --format '{{.Names}}' | grep -c 'nc35-\|nc-mcp-exapp\|nc_app_mcp_connector')" = "0" && grep -qF "## Follow-up run" docs/folder-evidence.md && grep -qF "## Folder next to a tagged folder" docs/folder-evidence.md && ! grep -qE "$(printf '\xe2\x80\x93|\xe2\x80\x94')" docs/folder-evidence.md</automated>
  </verify>
  <acceptance_criteria>
    - Beide Protokolle: alle Fallzeilen ergebnis=ok, Zusatz befund=nein, BASELINE gleich=ja, Kanarie und Live-Paar passed
    - Abnahmeskript auf 32: Exit 0, oder der eigene Exit-Code der fehlenden Voraussetzung mit benanntem Grund
    - Keine eigene Instanz läuft, Geheimnisprüfung ohne Fund
  </acceptance_criteria>
  <done>Der Entscheid ist an beiden Enden des Store-Fensters am echten Werkzeug belegt.</done>
</task>

<task type="auto">
  <name>Task 5: Gates und Diff-Prüfung mit Positivkontrolle</name>
  <files>(keine)</files>
  <action>
`pytest tests/unit tests/contract` (Zahl mit überschriebenem addopts), `scripts/check_tool_budget.py` (16222 Bytes, 24 Werkzeuge; andere Zahl: anhalten und melden), ruff check, ruff format --check, pyright, vulture. Diff gegen `B=$(cat .planning/phases/31-ordner-anlegen/31-BASE.txt)` nach Positivkontrolle der Basis: `dav.py` gegenüber eff0bf8 unverändert, `server/reg_files.py` und `server/__init__.py` gegenüber 620ab4e unverändert, `test_no_destructive_calls.py` gegenüber eff0bf8 unverändert; Gegentreffer im Diff gegen die Basis (`+def _padded_name`, `+def _in_the_way`).
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit tests/contract -q && uv run --no-sync python scripts/check_tool_budget.py && uv run --no-sync ruff check . && uv run --no-sync ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright && uv run --no-sync vulture src scripts vulture_whitelist.py</automated>
  </verify>
  <acceptance_criteria>
    - Alle Gates Exit 0; Budget 16222 Bytes, 24 Werkzeuge; EXPECTED_MKCOL_CALLS = 2 unverändert grün
  </acceptance_criteria>
  <done>Der Stand ist vollständig grün, die Oberfläche auf dem Draht unverändert.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-31-02 | Information Disclosure | Namensablehnung als Orakel für getaggte Pfade | mitigate | Prüfung hängt nur an der Eingabe und läuft vor dem Wächter; Paarfall und Ausschlusstest mit Zähler 0 |
| T-31-09 | Repudiation | Meldung nennt einen Ordner, den es so nicht gibt | mitigate | Ablehnung vor jedem Schreiben; Live-Fall mit Dateisystemprobe |
| T-31-05-01 | Information Disclosure | neue Rohprotokolle | mitigate | Zwischendatei, Prüfung gegen die Env-Werte vor jedem Anhängen und vor jedem Commit |
| T-31-05-03 | Denial of Service | Host-RAM | mitigate | RAM-Gate, eine Instanz, am Ende alles gestoppt |
| T-31-SC | Tampering | Paketinstallationen | accept | keine Installation |
</threat_model>

<verification>
- Unit-Tests zu (a) und (b) rot vor und grün nach der Umsetzung, Mutationsproben rot
- Live-Test, Kanarie und Live-Paar auf 35 und 32 grün; Abnahmeskript auf 32 mit Exit-Code im Protokoll
- Gates grün, Budget unverändert, keine eigene Instanz läuft
</verification>

<success_criteria>
- Befund 2, 3 und 5 aus 31-05 sind behoben und belegt, oder der offene Rest ist mit Messwert benannt
</success_criteria>

<output>
Create `.planning/phases/31-ordner-anlegen/31-05b-SUMMARY.md` when done
</output>

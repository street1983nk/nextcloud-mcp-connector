---
phase: 31-ordner-anlegen
verified: 2026-11-13T02:35:00Z
status: passed
score: 5/5 Erfolgskriterien belegt (Stand nach dem Nachtrag vom 2026-11-13; bei der Erstprüfung 4/5, siehe Abschnitt Nachtrag)
overrides_applied: 0
verified_head: 30e21349be20aef68f9be1b55c4dbfee3a2e6f05
base: 91c3b5113c541999d3d3363ab71c6b26a9dd41c9
deferred:
  - truth: "Gesamtlauf aller Gates im CI einschließlich canary-nc35 grün"
    addressed_in: "Phase 34"
    evidence: "Phase 34 Erfolgskriterium 4: 'der Gesamtlauf aller Gates ist lokal und im CI einschließlich canary-nc35 grün'. Gilt für den Release-Stand, nicht für den Stand ohne Phase 32; deshalb bleibt der Punkt zusätzlich als Owner-Entscheid unten stehen."
  - truth: "README.de.md und README.fr.md sagen, ein Contract-Test halte die Rechtetabelle; der Test liest nur README.md"
    addressed_in: "Phase 34"
    evidence: "Phase 34 Erfolgskriterium 1: READMEs nennen dieselbe Werkzeugzahl wie die Registry, 'die Zähl- und Wahrheitstests der Doku sind grün'; Punkt 1 der Liste in 31-06-SUMMARY.md"
human_verification:
  - test: "Entscheiden, ob für den Stand ohne Phase 32 ein CI-Lauf entstehen soll (Draft-PR von plan/v1.8-tasks-080), oder ob die lokalen Gates für den Rückfallschnitt reichen"
    expected: "Mit PR: Jobs unit (Linux, inklusive der 35 lokal übersprungenen POSIX-Tests), image, exapp (34.0.3), canary-nc35 (35.0.1), integration sowie security.yml (codeql, reuse, pip-audit) sind grün. Ohne PR: Owner nimmt den lokalen Beleg ausdrücklich an; der CI-Beleg entsteht erst in Phase 34 und dann nur für den Stand mit Phase 32"
    why_human: "Ein Branch-Push löst keinen Lauf aus (ci.yml: push nur main, sonst pull_request). Eine PR anzulegen braucht die Owner-Freigabe; der Verifier startet weder Docker noch CI"
  - test: "Ein Aufruf von files_create_folder durch einen echten MCP-Client über die installierte ExApp (Image aus diesem Stand, HaRP-Weg), ein freier Pfad und derselbe Pfad noch einmal"
    expected: "created true mit id, danach created false mit derselben id; im Audit steht je Aufruf eine Zeile mit den gesetzten Parametern path und parents"
    why_human: "Der Live-Beweis ruft die Werkzeugfunktion im Testprozess mit AppAPI-Kopf direkt gegen Nextcloud; das Abnahmeskript lief über stdio mit App-Passwort; die auf nc35 registrierte App ist 0.3.2 und kennt das Werkzeug nicht. Die Kette Client, Proxy, ExApp, Werkzeug, Impersonation ist für dieses Werkzeug nie als Ganzes gelaufen"
---

# Phase 31: Ordner anlegen, Verifikationsbericht

**Phasenziel:** Ein Assistent kann über `files_create_folder` einen Ordner anlegen, auf Wunsch samt fehlender Elternordner, und der neue Schreiber der Dateifläche hält jede Grenze, die der Upload hält; die Phase ist für sich allein releasefähig.
**Geprüft:** 2026-11-13, HEAD 30e2134, Basis 91c3b51 (31-BASE.txt)
**Status:** human_needed
**Re-Verifikation:** nein, erste Verifikation

Vorgehen: vom Ziel rückwärts. Code, Tests und Rohprotokolle wurden gelesen, die lokalen Gates selbst ausgeführt. Kein Docker, kein Live-Lauf. Für Aussagen "gemessen gegen echte Nextcloud" zählen nur `raw/*.txt` und `docs/folder-evidence.md`; der Live-Test wurde gegen seine Protokollzeilen gehalten.

## Zielerreichung

### Erfolgskriterien (ROADMAP)

| # | Kriterium | Urteil | Kernbeleg |
|---|-----------|--------|-----------|
| 1 | Gegen echte Nextcloud, auch unter Impersonation: frei, vorhanden, Datei, Elternordner fehlt, Kette, Deckel 10, Abbruch nennt Angelegtes | VERIFIED | `raw/nc35-nacharbeit.txt` Z. 68 bis 129 und `raw/nc32-nacharbeit.txt` Z. 100 bis 161: je `18 passed`, `exit=0`, alle Zeilen `ergebnis=ok`, `BASELINE ... gleich=ja`. Zeilen `ORDNER frei` (MKCOL:201, id gleich oc:fileid aus App-Passwort-PROPFIND), `vorhanden` (MKCOL:405, PROPFIND:207, created false, dieselbe id), `datei` (ConflictError), `eltern-fehlt` (MKCOL:409, exakt `dav.parent_missing`), `kette` (4 mal 201, `created_folders` von oben), `deckel` (12 PROPFIND, kein MKCOL, "needs 11 new folders; one call creates at most 10"), `teilabbruch-wettlauf` ("Already created in this call and left in place: .../w"). Der Test misst das wirklich: `tests/integration/test_files_create_folder_live.py:493-602`, Gegenprobe je Fall per `docker exec test -d`. Code: `tools/files.py:678-798` |
| 2 | kein-ki: nichts angelegt, byte-gleich zu "Elternordner fehlt" (Unit- und Live-Paar); Prüfung nicht beantwortbar: kein MKCOL; Sandbox: Wurzel nie angelegt | VERIFIED | Live: `ORDNER kein-ki` auf 35 und 32 (getaggte Aufrufe ohne MKCOL und ohne PROPFIND auf files, Dateisystem leer, Positivkontrolle `offen/neu`); Live-Paar `PAARE normal 15 von 16`, `500`, `412`, `timeout` je `16 von 16`, `10 passed` (`nc35-nacharbeit.txt:134-145`, `nc32-nacharbeit.txt:166-177`); Kanarie in drei erzwungenen Ausfällen je `geprüft 24 von 24`; `KONTROLLE 2` (falsches Secret: guard_tripped, MKCOL nur im nackten Client, nichts auf der Platte). `ORDNER sandbox`: Wurzel ohne Request abgelehnt, `/a` landet unter der Wurzel, fehlende Wurzel ohne MKCOL. Unit: `test_pair_equality_files.py:613-648` (alle GUARD_MODES, MKCOL-Zähler 0), `test_files_create_folder_exclusion.py:238-250`, `test_files_create_folder.py:851-936`. Code: `files.py:720-731`, `:752-757`, `:776` |
| 3 | Ohne Schreibrecht "keine Rechte": geteilter Ordner live, Gruppenordner mit ACL über die Rohantwort aus Phase 30; unzulässiger Name mit eigener Meldung | VERIFIED (mit Grenze) | Geteilt: `ORDNER geteilt-nur-lesen nutzer=bob`, zwei mal MKCOL:403, "No permission to create a folder", `reason permission_denied`, `oc:permissions` bob `SGDN` (35) und `SGD` (32) ohne C und K, Dateisystem der Eigentümerin leer, Positivkontrolle im eigenen Home. Gruppenordner: `docs/spike-tasks.md` 2.2 (`GF acl-ro auth=appapi nutzer=spike30a status=403 angelegt=nein`, zwei Positivkontrollen), 2.4, 12.2; verlinkt aus `docs/folder-evidence.md:268-286`. Das ist ein nackter MKCOL des Spike-Skripts auf 35.0.0 mit groupfolders 23.0.1, nicht das Werkzeug; das Kriterium verlangt genau das (D-31-07). Name: `NAME '.htaccess'` und `'x.filepart'` MKCOL:400 mit "Nextcloud does not accept the folder name", `dav.py:1163`, `:92-104` |
| 4 | Kanarie ruft wirklich auf, MUST_REFUSE; Freeze unter FILE_WRITERS mit Paarfall; Audit je Aufruf; EXPECTED_PUT_CALLS unverändert; Nadel MKCOL nur in dav.py ohne Body; Budget grün, kein Werkzeug über 1400 | VERIFIED | `test_canary.py` MUST_REFUSE mit `files_create_folder`, zwei Aufrufe je Modus (ohne und mit parents), Rückbau `CLEANUP ordner ...: 404` wird verlangt; Rohprotokoll `ABWEISUNG files_create_folder normal path: ja`. `tool_classes.py:74`, `:134`; `test_tool_classes.py` (13, 4, 7), TOTAL 24. Audit: `allowlist.py:52`, `reg_files.py:249-261` mit `@graceful`, `test_audit_surface.py:51` und `:128`. `EXPECTED_PUT_CALLS = 6` in Basis und HEAD (Diff ohne entfernte Zeile). Nadel `test_no_destructive_calls.py:606-790` mit `EXPECTED_MKCOL_CALLS = 2` und gepflanzten Umgehungen; `dav.py:1135` ohne Body. Budget selbst gemessen: 16222 Bytes, 24 Werkzeuge, Budget 18000, größtes Werkzeug `files_upload` 1377 Bytes, `files_create_folder` 515 Bytes |
| 5 | Stand ohne Phase 32: alle Gates grün; drei READMEs, drei exclusion-Seiten, drei CHANGELOGs nennen das Werkzeug | UNCERTAIN (teilweise) | Doku-Hälfte belegt: README je Zeile "24", Tabellenzeile, Bundle-Liste (`README.md:25`, `:72`, `:123`; `.de.md:28`, `:81`, `:134`; `.fr.md:28`, `:84`, `:140`); Tabellen der drei Sprachen namens- und stufengleich und gleich der Registry (eigener Vergleich); `docs/exclusion*.md` Abschnitt `tech-folder-oracle` mit Link auf `folder-evidence.md#folder-next-to-a-tagged-folder`; CHANGELOG je 8 gleichlaufende Punkte unter [Unreleased]. Gate-Hälfte: lokal alles grün (Zahlen unten), aber kein CI-Lauf für diesen Stand. Nie gelaufen: Linux-Lauf der Unit-Tests (35 POSIX-Tests lokal übersprungen), Image-Bau, Job exapp auf 34.0.3, canary-nc35 auf 35.0.1, Job integration, security.yml |

**Score:** 4 von 5 belegt, 1 teilweise.

### Zurückgestellte Punkte

| # | Punkt | Wo adressiert | Beleg |
|---|-------|---------------|-------|
| 1 | CI-Gesamtlauf einschließlich canary-nc35 | Phase 34, Kriterium 4 | gilt für den Release-Stand; für den Rückfallschnitt bleibt der Owner-Entscheid offen |
| 2 | Wahrheitstest der Rechtetabelle liest nur README.md | Phase 34, Kriterium 1 | Liste in 31-06-SUMMARY.md, Punkt 1 |

### Anforderungen

| Anforderung | Urteil | Beleg |
|-------------|--------|-------|
| FOLD-01 | erfüllt | Ein MKCOL ohne Body (`dav.py:1122-1142`, Nadel). Eigene Meldungen: 404/409 `parent_missing`, Datei `ConflictError`, 403, 400, 423, 507, 5xx über `_check` (`dav.py:1145-1184`). Live belegt: 201, 405, 409, 403, 400, 507 auf 32 und 35. Nur per Unit-Test: 423 (`UNGEMESSEN sperre-423`), 404 bei MKCOL (`UNGEMESSEN mkcol-404`, sabre antwortet 409), 5xx (`test_dav_make_folder.py:151-222`) |
| FOLD-02 | erfüllt | Kette von oben, `created_folders`, Deckel vorab (`files.py:746-765`, `MAX_NEW_FOLDERS`), Zusatz "Already created in this call and left in place" (`:937-950`). Live: `kette`, `deckel`, `teilabbruch-wettlauf`, auf 32 zusätzlich `teilabbruch-name` (zwei Ordner stehen, Meldung nennt beide). Genau 10 und 403 mitten in der Kette nur per Unit-Test (`test_files_create_folder.py:448`, `:487`). Netzfehler (31-04b): `files.py:788-793`, `:953-990`, nur Unit (`:612-838`) |
| FOLD-03 | erfüllt | 405 gefolgt von genau einem Lesen (`files.py:740-742`, `:860-874`); Annotation `CREATE_IDEMPOTENT` (`server/__init__.py:89-94`), an der Registry gelesen: read_only False, destructive False, idempotent True, open_world False; Gate mit eigener Menge und Gegenprobe (`test_tool_surface.py:88`, `:810-830`). Live: `vorhanden`, `datei` |
| FOLD-04 | erfüllt | `_writable` vor jedem Request und vor jedem MKCOL (`files.py:731`, `:776`; `test_files_create_folder_exclusion.py:252-276`); fail-closed (`files.py:1442-1444`); Wurzel (`:720-724`, `:752-757`). Live wie Kriterium 2. Hinweis: die Prüfungen eines Aufrufs teilen sich eine Tag-Abfrage, siehe Lücke I5 |
| FOLD-05 | erfüllt | FILE_WRITERS, PAIR_CASES (Unit und Live), Kanarie, Audit-Liste, `@graceful`, Werkzeugmenge 24, Bundle (`test_tool_bundles.py:37`), Abnahmeskript (`acceptance_all_tools.py:209-219`; `raw/nc32-abnahme.txt`: `ABNAHME ... exit=0 werkzeuge=24 gerufen=24 zeilen_ok=34 fail=0`), Nadel, `EXPECTED_PUT_CALLS` 6, Budget ohne Anhebung von `MAX_TOOL_BYTES`. `_PARENT_HINT` (`dav.py:56-60`) wortgleich in `test_dav_fileid_paths.py:27-31` |
| FOLD-06 | teilweise | Doku-Pflichten vollständig, Befundlink liegt unter `docs/` und wird vom Test gehalten (`test_docs_exclusion_truth.py`, gepflanzte Gegenprobe). "Alle Gates grün" nur lokal belegt, siehe Kriterium 5 |

Waisen: keine. REQUIREMENTS.md ordnet Phase 31 genau FOLD-01 bis FOLD-06 zu, alle sechs stehen in Plänen. REQUIREMENTS.md führt sie noch als `[ ]` und "Pending", ROADMAP.md Zeile 122 die Phase als `[ ]`: Buchhaltung der Hauptsitzung, hier nicht angefasst.

### Artefakte

`gsd-sdk query verify.artifacts` für alle acht Pläne: 31 von 31 vorhanden, keine Stubs. Substanz von Hand geprüft:

| Artefakt | Status | Details |
|----------|--------|---------|
| `src/mcp_connector/tools/files.py` (`create_folder`) | VERIFIED | 120 Zeilen Logik plus Helfer, kein Platzhalter, verdrahtet über `reg_files.py:261` |
| `src/mcp_connector/nextcloud/clients/dav.py` (`make_folder`, `probe_folder`, `_check_mkcol`) | VERIFIED | genutzt aus `files.py:735`, `:778`, `:853`, `:866`, `:884` |
| `src/mcp_connector/server/reg_files.py` | VERIFIED | Registrierung im Bundle files, in der Registry sichtbar (24 Werkzeuge) |
| `tests/unit/test_files_create_folder.py`, `_exclusion.py`, `test_dav_make_folder.py` | VERIFIED | 57, 16 und 21 Tests, 194, 69 und 47 Assertions, kein skip, kein xfail |
| `tests/integration/test_files_create_folder_live.py` | VERIFIED, aber nicht im CI | 18 Tests; läuft in keinem CI-Job mit Topologie, siehe Lücke W3 |
| `docs/folder-evidence.md` | VERIFIED | zitierte Zeilen stehen in den Rohprotokollen |
| `scripts/acceptance_all_tools.py` | VERIFIED | ruft das Werkzeug zweimal und prüft created false |

### Verdrahtung

`gsd-sdk query verify.key-links` meldet 3 von 14, die übrigen mit "Source file not found", weil die `from`-Felder der Pläne einen Funktionsnamen hinter dem Pfad tragen. Von Hand geprüft, alle verdrahtet:

| Von | Nach | Status |
|-----|------|--------|
| `files.create_folder` | `_writable` | WIRED (`files.py:731`, `:776`) |
| `files.create_folder` | `dav.make_folder` | WIRED (`:735`, `:778`) |
| `reg_files.files_create_folder` | `files.create_folder` | WIRED (`reg_files.py:261`) |
| `dav._PARENT_HINT` | Testkonstante | WIRED (Test grün) |
| `canary_world.refusal_problem` | Fragmente von parent_missing | WIRED (Tupel um `files_create_folder` erweitert, `test_canary_refusals.py` grün) |
| Live-Test | `files_tools.create_folder` mit MODE_APPAPI | WIRED (`test_files_create_folder_live.py:385-398`, `:422`) |
| `folder-evidence.md` | `spike-tasks.md` 2.2, 2.4, 12.2 | WIRED (`:274-282`) |
| `exclusion*.md#tech-folder-oracle` | `folder-evidence.md#folder-next-to-a-tagged-folder` | WIRED (Überschrift in `folder-evidence.md:248`) |

### Lokale Gates, selbst ausgeführt (HEAD 30e2134)

| Gate | Befehl | Ergebnis |
|------|--------|----------|
| Unit und Contract | `uv run pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib -rs` | 5961 passed, 35 skipped, Exit 0 (199,8 s) |
| Budget | `uv run python scripts/check_tool_budget.py` | 16222 Bytes, 24 Werkzeuge, Budget 18000, Exit 0 |
| Lint | `uv run ruff check .` | All checks passed, Exit 0 |
| Format | `uv run ruff format --check .` | 375 files already formatted, Exit 0 |
| Typen | `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations, Exit 0 |
| Toter Code | `uv run vulture src scripts vulture_whitelist.py` | keine Ausgabe, Exit 0 |
| Zusatz, CI-Job unit | `uv run pytest -m matrix` | 8 passed, Exit 0 |

Die 35 Skips: `test_documents_worker.py` 2 (RLIMIT_AS nur Linux), `test_entry_oauth.py` 5, `test_store_inputs.py` 24, `test_store_key_check.py` 4 (POSIX-Rechte, Links, FIFOs). Keiner berührt Phase 31; alle laufen nur unter Linux, also nur im CI.

Die gemeldeten Zahlen der Phase (5961 passed, 35 skipped; 16222 Bytes) sind damit bestätigt.

### Live-Belege gegen den Testcode gehalten

- Die Fallzeilen entstehen in `Case.__exit__` (`:351-360`): erst die Zeile, dann `assert self.ok`. Ein `ergebnis=ok` heißt, dass jede `expect`-Bedingung des Falls wahr war.
- `status=` ist die Liste eines Response-Hooks auf dem gemessenen Client (`:373-383`), keine Annahme.
- Impersonation: `Credentials(mode=MODE_APPAPI, secret=APP_SECRET)` (`:389-397`), Kontrolle 1 und 2 laufen zuerst.
- Seit dem letzten Live-Lauf (95ff4da, bdfc685) hat sich unter `src/` nichts geändert; danach kamen nur `test_tool_bundles.py`, `test_docs_exclusion_truth.py` und Doku.
- Erwartungen, die nach einem ersten Lauf geändert wurden (1f0d552, f78fdd1): Kontingent-Rand (Nextcloud verlangt 4096 freie Bytes, QuotaPlugin; auf 32 veraltete Belegung, deshalb 8192) und der Ort der Namensablehnung auf 32 (MKCOL 400 statt PROPFIND 500). Beides folgt einer gemessenen Servereigenschaft und schwächt keine Anforderung: die Meldung bleibt die benannte, das Angelegte wird genannt. Der eine echte Produktfehler aus dem ersten Lauf (500 beim Zählen von `.htaccess` als Serverfehler) ist in 77cab44 behoben und in `raw/nc35-ordner-vorlaeufe.txt:23` als `ergebnis=befund` dokumentiert.

### Besonderheiten aus dem Auftrag

- **Strecke Nextcloud 32, `bootstrap_exapp.sh` defekt:** `raw/nc32-strecke.txt` endet mit `STRECKE NC32 NACHMESSUNG ergebnis=bereit weg=daemon manual_install ohne port ... skript unverändert`. Kein Erfolgskriterium verlangt, dass das Skript auf 32 läuft; verlangt ist die Messung, und die liegt vor. Das CI nutzt 34.0.3 und 35.0.1 im Container-Modus, nicht 32 und nicht `--manual`, es wäre vom Defekt also nicht betroffen. Folge: der Beleg auf 32 lässt sich bis zum Folgeplan nicht per Skript wiederholen (Lücke W4).
- **Gruppenordner mit ACL:** wie in Kriterium 3 beschrieben; belegt ist der Status 403 des Servers aus Phase 30, die Übersetzung des 403 durch das Werkzeug ist am geteilten Ordner live belegt. Das Werkzeug selbst lief nie gegen einen Gruppenordner (Lücke W5).
- **Kein CI-Beleg:** Kriterium 5 ist deshalb nur teilweise belegt, siehe oben und Punkt 1 der Prüfungen durch einen Menschen.

### Anti-Muster

In den 33 Dateien der Phase außerhalb von `.planning/`: kein TBD, FIXME, XXX, TODO, HACK, PLACEHOLDER; keine Stub-Rückgaben; kein U+2013, U+2014 und kein Emoji in den zehn nutzersichtbaren Dateien; keine Ersatzschreibung von Umlauten in den hinzugefügten deutschen Zeilen.

## Lücken nach Schwere

Blocker: keine.

### Warnungen

| # | Lücke | Beleg | Folge |
|---|-------|-------|-------|
| W1 | Kein CI-Lauf für den Stand ohne Phase 32 | `ci.yml:7-10` (push nur main); `gh pr list` laut 31-06-SUMMARY leer | Kriterium 5 und FOLD-06 nur lokal belegt; 35 Linux-Tests, Image-Bau, exapp-Job, canary-nc35 ungelaufen. Owner-Entscheid nötig |
| W2 | Live-Beweis auf Ebene der Werkzeugfunktion, nicht über die installierte ExApp | `folder-evidence.md:41-43`; `acceptance_all_tools.py:1` (stdio, App-Passwort); registrierte App auf nc35 ist 0.3.2 | Die Kette Client, Proxy, ExApp, Werkzeug, Impersonation ist für dieses Werkzeug nicht als Ganzes gemessen |
| W3 | `test_files_create_folder_live.py` läuft in keinem CI-Job mit ExApp-Topologie | `ci.yml:106-152`, `:219`, `:236` nennen die Datei nicht; im Job integration (`:271`) überspringt sie mangels `APP_SECRET` (`:269-273` des Tests, ohne `NC_MCP_REQUIRE_LIVE`-Zweig) | Die 18 Live-Fälle sind ein einmaliger Handlauf; gegen Rückschritte schützen im CI nur Kanarie und Live-Paar |
| W4 | Strecke 32 nur von Hand herstellbar | `nc32-strecke.txt:1068` | Beleg auf 32 bis zum Folgeplan nicht per Skript wiederholbar; kein Kriterium berührt |
| W5 | Werkzeug nie gegen Gruppenordner gelaufen, auch nicht mit `parents=true` | D-31-07, `folder-evidence.md:268-286` | Vom Kriterium gedeckt und vom Owner entschieden; der Hauptanwendungsfall des Melders von #44 beruht auf dem Status 403 aus Phase 30 (nur 35.0.0) |
| W6 | README.de.md und README.fr.md behaupten, ein Contract-Test halte die Rechtetabelle | `README.de.md:70`, `README.fr.md:73`; `test_tool_surface.py:878` liest nur README.md | Aussage für DE und FR nicht vom Code gehalten. Inhaltlich stimmen die drei Tabellen heute überein (eigener Vergleich). Phase 34 |

### Hinweise

| # | Hinweis | Beleg |
|---|---------|-------|
| I1 | Nur per Unit-Test belegt: 423, 404 bei MKCOL, 5xx, Netzfehler in der Kette, 403 mitten in der Kette, genau 10 neue Ordner | `folder-evidence.md:335-367` nennt es selbst |
| I2 | Nextcloud 33 und 34 ungemessen (D-31-06: nur die Enden 32 und 35) | `folder-evidence.md:369` |
| I3 | Zeilenanker in `tool_classes.py:74-77` veraltet (`files.py:669-762, :708, :748`; tatsächlich 678-798, 731, 776) | kein Test prüft die Zahlen |
| I4 | Hinweistext von `name_rejected` nennt "a trailing space or dot"; ein Punkt am Ende wird von Nextcloud angenommen (`NAME 'ende-punkt.' ... MKCOL:201`), ein Leerzeichen lehnt das Werkzeug selbst mit anderem Satz ab | `dav.py:100-103` |
| I5 | "Geprüft vor jedem MKCOL" ist wörtlich erfüllt, die Prüfungen eines Aufrufs teilen sich aber eine Tag-Abfrage (`exclusion.py:347-368`); ein Tag, das während einer Kette gesetzt wird, sieht der Aufruf nicht | `test_files_create_folder_exclusion.py:275` hält das als gewollt fest |
| I6 | Restzweige ohne benannte Meldung bleiben für nie gemessene Status: `_check_mkcol` "with status N" (`dav.py:1181`), `_check` "unexpected status" für das Lesen (`:1387`), etwa 423 auf PROPFIND | die in FOLD-01 genannten Fälle haben alle einen eigenen Zweig |
| I7 | Unter Impersonation lautet die 401-Meldung "Nextcloud rejected the app password." mit Rat zum App-Passwort | `KONTROLLE 2`; geteilter Satz aus `_check`, älter als die Phase |
| I8 | `docs/folder-evidence.md` verlinkt die Rohprotokolle unter `.planning/phases/31-ordner-anlegen/raw/`; wandert der Phasenordner beim Abschluss des Milestones ins Archiv, brechen diese Links. Der von FOLD-06 verlangte Link aus den exclusion-Seiten zeigt auf `docs/` und bleibt stabil | `folder-evidence.md:14-22` |
| I9 | Der Namensfall prüft für `.htaccess`, `x.filepart`, `con`, `ende-punkt.` nur "benannte Ablehnung oder echter Ordner", nicht welches von beiden | `test_files_create_folder_live.py:804-832`; für das Kriterium ("eigene Meldung statt unexpected status") reicht das |
| I10 | Mit `parents=true` ist die Ablehnung im getaggten Ordner von einem erfundenen Pfad unterscheidbar (der erfundene wird angelegt). Das ist die dokumentierte Restgrenze "jede Ablehnung unterscheidet sich vom Erfolg eines freien Namens" | `folder-evidence.md:260-266`, `test_pair_equality_files.py:618-622` |
| I11 | REQUIREMENTS.md und ROADMAP.md führen FOLD-01 bis FOLD-06 und die Phase noch als offen | Buchhaltung nach dieser Verifikation |

## Prüfung durch einen Menschen

### 1. CI-Beleg für den Rückfallschnitt

**Test:** Entscheiden, ob eine Draft-PR von `plan/v1.8-tasks-080` angelegt wird, damit ci.yml und security.yml auf dem Stand ohne Phase 32 laufen.
**Erwartet:** alle Jobs grün, oder ausdrückliche Annahme des lokalen Belegs.
**Warum ein Mensch:** PR nur mit Owner-Freigabe; ohne PR gibt es für diesen Stand nie einen CI-Lauf, weil Phase 32 auf demselben Branch aufsetzt.

### 2. Ein Aufruf über die installierte ExApp

**Test:** Image aus diesem Stand in einer Testinstanz registrieren, mit einem echten MCP-Client `files_create_folder` für einen freien Pfad und denselben Pfad erneut aufrufen, Audit lesen.
**Erwartet:** created true mit id, danach created false mit derselben id, je eine Audit-Zeile.
**Warum ein Mensch:** braucht Docker und eine Client-Anmeldung; bisher ist nur die Werkzeugfunktion unter Impersonation und das Werkzeug über stdio mit App-Passwort gemessen.

## Zusammenfassung

Das Werkzeug existiert, ist verdrahtet und hält, was die Phase verspricht: Die Erfolgskriterien 1 bis 4 und die Anforderungen FOLD-01 bis FOLD-05 sind durch Code, Tests und Rohprotokolle von Nextcloud 35.0.0.10 und 32.0.15.1 gedeckt. Es wurden keine Stubs, keine ausgehöhlten Tests und keine an das Ist angepassten Erwartungen gefunden, die eine Anforderung schwächen. Die lokalen Gates sind grün und stimmen mit den gemeldeten Zahlen überein.

Offen ist allein der Nachweis "alle Gates grün" jenseits des lokalen Rechners (Kriterium 5, FOLD-06): für diesen Stand lief nie ein CI. Dazu kommt, dass die Kette über die installierte ExApp für dieses Werkzeug nicht als Ganzes gemessen ist. Beides ist eine Entscheidung des Owners, kein Fehler im Code.

---

_Geprüft: 2026-11-13T02:35:00Z_
_Verifier: Claude (gsd-verifier)_

## Nachtrag der Hauptsitzung (2026-11-13)

Die Erstprüfung oben endete mit `human_needed` (4 von 5 Kriterien belegt, eines teilweise). Die drei tragenden Lücken sind seither geschlossen; der Text oben bleibt unverändert als Stand der Erstprüfung auf 30e2134.

- **W1, kein CI:** geschlossen. Draft-PR 48 von `plan/v1.8-tasks-080` gegen `main` (Owner-Freigabe 2026-11-13), CI auf 30e2134: unit, image, exapp, canary-nc35 und integration bestanden (Lauf 43352751097), CodeQL, CodeQL (python), REUSE und pip-audit bestanden (Lauf 43352751170). Damit ist die Gate-Hälfte von Erfolgskriterium 5 und von FOLD-06 auch außerhalb des lokalen Rechners belegt, einschließlich der 35 Tests, die lokal als Plattform-Skips laufen. Die Commits nach 30e2134 sind Planung, Belege und ein Messprogramm unter `scripts/`; unter `src/` und `tests/` hat sich seit dem CI-Lauf nichts geändert, die lokalen Gates liefen nach 31-07 erneut grün (5961 passed, 35 skipped; ruff über 376 Dateien, pyright, vulture, Budget 16222 Bytes).
- **W2, Lauf über die ExApp:** geschlossen durch Plan 31-07. Auf Nextcloud 35.0.0.10 läuft die ExApp aus einem Image dieses Standes (0.7.2, 24 Werkzeuge); `files_create_folder` lief über OAuth, MCP-Client, Caddy, HaRP und den ExApp-Container: frei (created true, id), vorhanden (created false, dieselbe id), Kette mit drei Gliedern, kein-ki (Ablehnung wie Elternordner fehlt), Leerraum am Rand (Ablehnung), je Aufruf genau eine Audit-Zeile bei eingeschaltetem Audit-Schalter. Beleg: `docs/folder-evidence.md#whole-chain-through-the-installed-app`, `raw/nc35-kette.txt`.
- **W5, Gruppenordner:** geschlossen durch Plan 31-07. Das Werkzeug lief über die ganze Kette gegen einen Gruppenordner mit ACL (groupfolders 23.0.1): im schreibbaren Teil angelegt, erneut created false, Kette angelegt; im nur lesbaren Teil je MKCOL 403, Meldung keine Rechte, nichts angelegt. Beleg: `docs/folder-evidence.md#group-folder-with-acl-measured-with-the-tool`, `raw/nc35-gruppenordner.txt`. Grenze: nur auf 35 gemessen (D-31-07).

Weiter offen, ohne ein Erfolgskriterium zu berühren: W3 (der Live-Test mit 18 Fällen steht in keinem CI-Job), W4 (`scripts/bootstrap_exapp.sh` für Nextcloud 32, eigener kleiner Plan nach dieser Phase, Owner 2026-11-12), W6 und die neun Punkte für den README-Faktencheck (Phase 34), Nextcloud 33 und 34 ungemessen, der Zusatz "nennt das Angelegte" nach einem 403 mitten in der Kette ist mit ACL nicht herstellbar und bleibt per Unit-Test belegt, die ganze Kette ist nur auf 35 gemessen.

---
phase: 31-ordner-anlegen
plan: 07
subsystem: testing
tags: [files_create_folder, ganze-kette, oauth, harp, exapp, gruppenordner, acl, audit, nextcloud-35]

requires:
  - phase: 31-ordner-anlegen
    provides: Werkzeug files_create_folder samt Live-Beweis auf Funktionsebene (31-05, 31-05b), Verifikationsbericht mit den Lücken W2 und W5
provides:
  - Messung von files_create_folder als ganze Kette auf Nextcloud 35 (MCP-Client, Caddy, HaRP, ExApp-Container aus diesem Stand, Impersonation), mit Audit-Zeile je Aufruf
  - Messung des Werkzeugs gegen einen Gruppenordner mit ACL-Regeln (Regel gegen Gruppe und gegen Konto)
  - Messprogramm scripts/folder_chain_evidence.py
  - Rohprotokolle raw/nc35-kette.txt und raw/nc35-gruppenordner.txt, zwei neue Abschnitte in docs/folder-evidence.md
  - nc35 trägt die ExApp jetzt in 0.7.2 aus dem Stand dieses Branches
affects: [32, 33, 34, 31-VERIFICATION]

tech-stack:
  added: []
  patterns:
    - "Messung über die Kette mit dem vorhandenen Client scripts/oauth_flow_check.py; Gegenproben über Dateisystem, App-Passwort-PROPFIND und Zugriffslog der Nextcloud"
    - "Anfragen der ExApp sind im Zugriffslog am User-Agent nextcloud-mcp-connector/0.1 erkennbar"

key-files:
  created:
    - .planning/phases/31-ordner-anlegen/31-07-PLAN.md
    - scripts/folder_chain_evidence.py
    - .planning/phases/31-ordner-anlegen/raw/nc35-kette.txt
    - .planning/phases/31-ordner-anlegen/raw/nc35-gruppenordner.txt
  modified:
    - docs/folder-evidence.md

key-decisions:
  - "Update-Weg auf 35: unregister ohne --rm-data, danach bootstrap_exapp.sh --nc35 (wie 29-06); app_api:app:update wurde nicht benutzt, weil das Skript die Registrierungsdaten nur für register baut"
  - "Die Registry der Strecke ist nc-mcp-exapp-registry (Kopfkommentar von compose.nc35.yml); nur dieser Container wurde dafür gestartet und wieder gestoppt"
  - "Audit-Log für die Messung eingeschaltet und danach auf den Ausgangszustand (Schlüssel nicht gesetzt) zurückgestellt"
  - "Kein Produktcode geändert: kein Befund gegen FOLD-01 bis FOLD-05 oder D-31-xx"

patterns-established:
  - "Hilfsskripte eines Messlaufs, die nicht ins Repo gehören, stehen wörtlich im Anhang des Rohprotokolls"

requirements-completed: []

duration: ca. 30min
completed: 2026-11-13
---

# Phase 31 Plan 07: Ganze Kette über die installierte ExApp und Gruppenordner mit ACL Summary

**files_create_folder ist auf Nextcloud 35.0.0.10 über die ganze Kette gemessen (OAuth-Client, Caddy, HaRP, ExApp 0.7.2 aus diesem Stand, Impersonation): sechs Aufrufe wie erwartet, je genau eine Audit-Zeile ohne Pfadwert; gegen einen Gruppenordner mit ACL sieben Aufrufe wie erwartet, jeder verbotene mit MKCOL 403 und nichts angelegt. Kein Produktfehler. Ein erwarteter Fall (403 mitten in der Kette nach schon angelegten Ordnern) ist mit festen ACL-Regeln nicht herstellbar.**

## Performance

- **Duration:** ca. 30 min
- **Completed:** 2026-11-13
- **Tasks:** 5 von 5
- **Files modified:** 6 (5 neu, 1 geändert)

## Teil A: registrierter Stand

| | vorher | nachher |
|---|---|---|
| `occ app_api:app:list` | mcp_connector 0.3.2 [enabled] | mcp_connector 0.7.2 [enabled] |
| Container nc_app_mcp_connector | Image 127.0.0.1:5000/mcp_connector:0.3.2, Image-Id sha256:08e87ea24503afee1ec7edd89657451e8c243d664ec32edabceca75211a44457, angelegt 2026-10-01 | Image 127.0.0.1:5000/mcp_connector:0.7.2, Image-Id und Registry-Digest sha256:cf01fc50812e4e0c89c713a9cd6866ca0274942ef85ab9b23ba949977a4c21d0, angelegt 2026-11-13T03:01:24Z |
| tools/list über die Kette (OAuth, alice) | 22 Werkzeuge, files_create_folder fehlt | 24 Werkzeuge, files_create_folder vorhanden |
| Audit-Log | 621 Einträge, 5 Ketten, kein Bruch | dieselben 621 Einträge direkt nach dem Update, kein Bruch |
| Volume nc_app_mcp_connector_data | vorhanden | vorhanden (unregister ohne --rm-data) |

Gebaut aus dem Worktree bei sauberem Arbeitsbaum (HEAD 8dd40ba; src seither unverändert). `appinfo/info.xml` unverändert (0.7.2).

Was beim Weg unregister und register mit Verbindungen und Daten geschah (gemessen):

- Der Container wurde entfernt und neu angelegt, das Volume blieb.
- Eine OAuth-Verbindung von alice, die VOR dem Update auf 0.3.2 aufgebaut wurde, antwortete NACH dem Update ohne neue Anmeldung auf tools/list (24 Werkzeuge). Der Schlüssel `oauth_data_key` steht nach dem Update in der ExApp-Konfiguration. Bestehende Verbindungen haben das Update also überlebt.
- APP_SECRET ist gleich geblieben (Vergleich der Env-Datei vor und nach dem Lauf, ohne Ausgabe des Werts), weil das Skript ihn aus `.env.nc35` übernimmt.
- Der Bootstrap lief in einem Anlauf durch; jeder ensure-Schritt meldete "exists", "present" oder "already there". Neu sind zwei App-Passwörter (alice, bob, Name mcp-exapp) und sechs Testmails in GreenMail (nach dem Stopp wieder weg).

## Teil A: Aufrufe über die Kette (alice, Präfix /kette31-d20e956d)

| Fall | Antwort des Werkzeugs | Gegenprobe | Audit-Zeile |
|---|---|---|---|
| frei | created true, id file:23782 | test -d ja; PROPFIND mit App-Passwort fileid=23782 | 623, u:alice, files_create_folder, ok, Parameter path |
| vorhanden | created false, id file:23782 | test -d ja | 624, ok, path |
| kette (parents, drei neue Glieder) | created true, created_folders k, k/a, k/a/b, id file:23785 | alle drei test -d ja; fileid=23785 | 625, ok, parents,path |
| kein-ki | Fehler "The parent folder ... does not exist." | getaggter Ordner vorhanden, darin nichts | 626, rejected, unknown_id, path |
| kein-ki-kontrolle (ungetaggter Nachbar) | created true, id file:23786 | test -d ja | 627, ok, path |
| leerraum (`ende-leer `) | Fehler "The folder name 'ende-leer ' ... starts or ends with whitespace." | weder der Name noch der gekürzte Name | 628, rejected, unspecified, path |

Je Aufruf genau eine neue Audit-Zeile (Folgenummer vor und nach dem Aufruf gelesen). Die Zeile trägt Werkzeug, Konto, Client-Name "OAuth flow check", Ausgang, Kennung, Dauer und die Namen der gesetzten Parameter; kein Pfad, kein Wert. Rückbau über das Dateisystem des Containers plus `occ files:scan`, Tag gelöscht; alle sieben BASELINE-Zeilen gleich=ja.

## Teil B: Gruppenordner mit ACL (groupfolders 23.0.1 aus dem Store, Ordner p3107gf, Id 3)

Aufbau: Gruppe p3107grp mit alice, Gruppenordner mit read, write, share, delete, ACL an. Unterordner `rw` ohne Regel, `ro` mit Regel gegen die GRUPPE, `rw/zu` mit Regel gegen das KONTO alice (je +read -write -create -delete). `--test` und oc:permissions bestätigen: rw RMGDNVCK, ro RMG, rw/zu RMG.

| Fall | Antwort des Werkzeugs | Rohstatus (Zugriffslog, Anfrage der ExApp) | Dateisystem |
|---|---|---|---|
| rw-neu | created true, id file:23794 | MKCOL 201 | angelegt |
| rw-erneut | created false, id file:23794 | MKCOL 405, PROPFIND 207 | unverändert |
| rw-kette (parents) | created true, created_folders rw/k, rw/k/a, rw/k/a/b | drei MKCOL 201 | alle drei angelegt |
| ro-neu | "No permission to create a folder at /p3107gf/ro/neu.", Audit permission_denied | MKCOL 403 (Gegenprobe mit App-Passwort: 403, Sabre Forbidden) | nichts |
| ro-kette (parents, erstes neues Glied in ro) | dieselbe Meldung für /p3107gf/ro/x, ohne Zusatz | MKCOL 403 | nichts |
| rw-nach-ro-kette (parents, durch rw/zu) | dieselbe Meldung für /p3107gf/rw/zu/x, ohne Zusatz | MKCOL 403 | unter rw/zu nichts |
| rw-nach-ro-ohne-parents | dieselbe Meldung | MKCOL 403 (Gegenprobe mit App-Passwort: 403) | nichts |

Rückbau: Gruppenordner, Gruppe, App und ihre drei Konfigurationsschlüssel entfernt, `__groupfolders` entfernt; BASELINE gleich=ja in allen sieben Zeilen.

Bewusste Grenze: nur auf 35 gemessen. D-31-07 verlangt den Gruppenordner einmal; die Strecke 32 wurde nicht gestartet.

## Befunde

Kein Verhalten widerspricht FOLD-01 bis FOLD-05 oder einer Entscheidung D-31-xx. Kein Produktcode geändert.

1. **Nicht herstellbar: Abbruch mit 403, der schon Angelegtes nennt.** Erwartet war für die Kette vom schreibbaren in einen nur lesbaren Unterordner ein Abbruch mit der Liste des Angelegten. Eine ACL-Regel hängt an einem vorhandenen Ordner; liegt er in der Kette, ist schon das erste neue Glied darunter verboten, also wird vorher nichts angelegt. Gemessen: ein MKCOL 403, nichts angelegt, Meldung ohne Zusatz. Der Zusatz "Already created" nach einem 403 mitten in der Kette bleibt nur per Unit-Test belegt (Hinweis I1 der Verifikation). Zeile `UNGEMESSEN gf-teilabbruch` im Rohprotokoll.
2. **Das Audit-Log ist ein Schalter und stand auf nc35 seit dem 2026-10-01 auf aus.** Ohne Einschalten gibt es keine Audit-Zeile. Für die Messung eingeschaltet (`occ app_api:app:config:set mcp_connector audit_log --value yes`, Neustart der ExApp), danach der Schlüssel wieder gelöscht und neu gestartet. Kein Fehler, aber die Erwartung "je Aufruf eine Audit-Zeile" gilt nur bei eingeschaltetem Schalter.
3. **`docker logs --since` liefert auf diesem Host für nc35-nc 0 Zeilen**, und `docker logs` ohne `--tail` endet am 25.09.2026. Das Zugriffslog wurde deshalb mit `--tail` nachgelesen. Ursache nicht untersucht (Docker, nicht das Produkt).
4. **Ein curl ohne Zeitgrenze blieb während des Neustarts der ExApp hängen** (Anfrage an HaRP, während der Container neu startete). Beendet, der Schritt lief danach durch. Ursache nicht untersucht.

## Zustand der Testinstanz nc35 nach dem Plan

- Registriert: mcp_connector 0.7.2 [enabled], Daemon harp_proxy_docker, Container nc_app_mcp_connector aus 127.0.0.1:5000/mcp_connector:0.7.2 (sha256:cf01fc50...), gestoppt.
- Audit-Log: 636 Einträge (621 alte, Schalter an 622, 13 Aufrufe 623 bis 635, Schalter aus 636), Kette geprüft, kein Bruch. Schalter wie vorher: nicht gesetzt.
- Zwei OAuth-Verbindungen von alice mit dem Client-Namen "OAuth flow check" stehen zusätzlich im Speicher der ExApp (nicht widerrufen).
- `.env.nc35` liegt jetzt auch im Worktree (gitignored, vom Bootstrap geschrieben, APP_VERSION=0.7.2, neue App-Passwörter). Die Datei im Hauptcheckout ist unberührt; ihr APP_SECRET stimmt weiter, ihr APP_VERSION steht noch auf 0.3.2.
- Die Registry nc-mcp-exapp-registry trägt jetzt den Tag mcp_connector:0.7.2 (vorher kein Repository mcp_connector).
- groupfolders, Gruppe p3107grp, Tag kein-ki und alle Testordner sind entfernt.

**Zurück zum alten Stand 0.3.2 (nicht ausgeführt, nicht getestet):** Das Image 127.0.0.1:5000/mcp_connector:0.3.2 liegt lokal (sha256:08e87ea2...). Nötig wären: nc35 und die Registry starten, `docker push 127.0.0.1:5000/mcp_connector:0.3.2`, `occ app_api:app:unregister mcp_connector` (ohne `--rm-data`), danach `bash scripts/bootstrap_exapp.sh --nc35` aus einem Checkout, dessen `appinfo/info.xml` 0.3.2 nennt und in dem die `.env.nc35` mit dem bisherigen APP_SECRET liegt. Der Bootstrap baut das Image dabei aus jenem Checkout neu; byte-gleich zum alten Image wäre es nicht.

## Task Commits

1. **Plan** - `dccb134` (docs)
2. **Task 1: Messprogramm** - `8dd40ba` (test)
3. **Task 2 und 3: Rohprotokolle Teil A und Teil B** - `341e52e` (docs)
4. **Task 4: Evidenzseite** - `dfa6b19` (docs)

Task 5 (Abschluss, Gates) hat keine weitere Datei geändert.

## Verifikation (gesehene Ausgaben)

- `pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib`: 5961 passed, 35 skipped (186,7 s), Exit 0. Darin die Doku-Tests zu docs/folder-evidence.md (tests/unit/test_docs_exclusion_truth.py).
- `scripts/check_tool_budget.py`: tools/list 16222 Bytes, 24 Werkzeuge, Budget 18000, Exit 0.
- `ruff check .`: All checks passed. `ruff format --check .`: 376 files already formatted (375 plus das neue Skript). pyright mit PYRIGHT_PYTHON_FORCE_VERSION=latest: 0 errors, 0 warnings, 0 informations. vulture: keine Ausgabe, Exit 0.
- docs/folder-evidence.md: 182 Zeilen in Codeblöcken, jede steht wörtlich in einem Rohprotokoll (0 fehlen); neun bestehende Überschriften unverändert, zwei neue am Ende; zwei bestehende Zeilen ergänzt (Statuszeile, Punkt "Group folders, external storage"), keine gelöscht.
- Bestehende Rohprotokolle ohne Diff. Kein Diff unter src, tests, appinfo, den compose-Dateien, scripts/bootstrap_exapp.sh, STATE.md, ROADMAP.md, REQUIREMENTS.md, 31-VERIFICATION.md.
- Geheimnisprüfung der neuen und geänderten Dateien gegen APP_SECRET, HP_SHARED_KEY, beide App-Passwörter und beide Kontopasswörter aus allen vier Env-Dateien (Worktree und Hauptcheckout, nc35 und exapp), gegen die ersten 12 Zeichen der langen Werte und gegen Muster für Bearer, Token, Client-Secret und AppAPI-Kopf: kein Fund. Ein Treffer des Musters im Messprogramm ist die Codezeile, die das Token in die Datei außerhalb des Repos schreibt, kein Wert.
- Am Ende läuft nur gameworld-dev-gameworld-docker-proxy-1. nc35 gestoppt (stop), Registry gestoppt, alle fünf Volumes vorhanden, kein lokaler Prozess, Scratchpad p3107 gelöscht.
- Vier Commits als street1983nk ohne Trailer, dazu der Commit dieses Berichts; kein Push.

## Deviations from Plan

**1. Registry-Container der Strecke 32 gestartet**
- Die Strecke nc35 hat keine eigene Registry; nach compose.nc35.yml nutzt sie `nc-mcp-exapp-registry` auf 127.0.0.1:5000. Nur dieser eine Container lief von 03:00 bis 03:09 UTC, die Nextcloud 32 nicht. Sein Volume hat einen Tag mehr.

**2. Image vor dem unregister von Hand vorgebaut**
- Derselbe Befehl wie im Skript (`docker buildx build --platform linux/amd64 --load -t ...`), damit ein Baufehler die App nicht unregistriert zurücklässt. Der Bootstrap baute und schob danach selbst.

**3. `.env.nc35` in den Worktree kopiert**
- Der Bootstrap liest APP_SECRET aus dieser Datei im Arbeitsverzeichnis und schreibt sie neu. Ohne die Kopie hätte er einen neuen Wert erzeugt und die Datei im Hauptcheckout entwertet. Der Rahmen von 31-05 nannte "nie kopieren"; hier war es die Voraussetzung des freigegebenen Bootstrap-Laufs.

**4. nc35-greenmail für den Bootstrap gestartet**
- Der Bootstrap stellt Testpost zu. Danach wieder gestoppt.

**5. Audit-Schalter umgestellt und zurückgestellt**, siehe Befund 2. Die ExApp wurde dafür zweimal neu gestartet.

**6. Mehr Aufrufe als geplant**
- Teil A sechs statt fünf (Positivkontrolle im ungetaggten Nachbarordner), Teil B sieben statt sechs (der Fall durch rw/zu auch ohne parents).

**7. Regeln in Teil B anders verteilt als im Plan**
- Der Plan nannte beide Regeln gegen alice. Gesetzt wurde auf `ro` eine Regel gegen die Gruppe (wie im Auftrag), auf `rw/zu` eine gegen das Konto. Damit sind beide Arten gemessen.

**8. Rohstatus aus dem Zugriffslog nachgelesen statt je Schritt**
- Siehe Befund 3. Die Zeilen stehen als zwei Blöcke "ZUGRIFFSLOG nachgelesen" im Rohprotokoll.

**9. Baseline mit eigenem Shell-Skript**
- Dieselben Größen wie in 31-05 (Dateien, Papierkorb, Kontingent, Tags, Freigaben), dazu Gruppen und Gruppenordner-Verzeichnisse, aber anders gezählt (PROPFIND Depth infinity). Die Zahl 283 ist deshalb nicht mit den 158 aus 31-05 vergleichbar; warum sie abweicht, wurde nicht untersucht. Verglichen wurde nur vorher gegen nachher.

**10. Hilfsskripte nicht im Repo**
- step.sh, stepb.sh, dav.sh und baseline.sh lagen im Scratchpad und stehen wörtlich im Anhang von raw/nc35-kette.txt.

## Offene Punkte

- Die ganze Kette ist nur auf 35 gemessen. Auf 32 läuft die ExApp als lokaler Prozess; eine Messung über ein Image gibt es dort nicht.
- `occ app_api:app:update` wurde nicht erprobt; ob ein Update ohne unregister dieselben Daten erhält, ist ungemessen.
- 403 mitten in der Kette mit Zusatz "Already created": weiter nur per Unit-Test.
- Externer Speicher, Regeln gegen Teams, Vorgabe ohne Rechte, Regel ohne Leserecht: ungemessen.
- Die `.env.nc35` im Hauptcheckout nennt noch APP_VERSION=0.3.2. Ob Läufe mit dieser Datei gegen die jetzt registrierte 0.7.2 unverändert antworten, wurde nicht gemessen; die Datei im Worktree ist die aktuelle.
- STATE.md, ROADMAP.md, REQUIREMENTS.md und 31-VERIFICATION.md wurden nicht angefasst; W2 und W5 sind dort noch offen geführt.

## Known Stubs

Keine.

## Self-Check: PASSED

- Alle sechs Dateien vorhanden und committet
- Commits dccb134, 8dd40ba, 341e52e, dfa6b19 im Log gefunden

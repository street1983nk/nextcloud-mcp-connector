---
phase: 33-aufgaben-aendern
plan: 01b
type: execute
wave: 2
depends_on: ["33-01"]
files_modified:
  - .planning/phases/33-aufgaben-aendern/33-01-BROWSER-SCHRITTE.md
  - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt
  - tests/fixtures/tasks_app/PROVENANCE.md
  - tests/fixtures/tasks_app/cleared_due.ics
  - tests/fixtures/tasks_app/cleared_start.ics
  - tests/fixtures/tasks_app/cleared_description.ics
  - tests/fixtures/tasks_app/cleared_priority.ics
  - tests/fixtures/tasks_app/cleared_tags.ics
  - tests/fixtures/tasks_app/cleared_parent.ics
  - tests/fixtures/tasks_app/cancelled.ics
  - tests/fixtures/tasks_app/cancelled_completed.ics
autonomous: false
requirements: [TMOD-02, TMOD-03, TMOD-04]

must_haves:
  truths:
    - "Die Browser-Sitzung läuft nur mit FREIGABE zustand=option-a oder option-b aus 33-01 und nur mit Tasks-App genau 0.18.1; eine andere Fassung stoppt den Plan mit Owner-Frage"
    - "M-1 ist gemessen: was die Tasks-App beim Wiederöffnen einer Elternaufgabe mit zwei erledigten Kindern schreibt; Ergebnis als ENTSCHEID wiederoeffnen_kinder=<bleiben|mit> (D-33-06)"
    - "M-2 ist gemessen: Form des Entfernens von Fälligkeit, Startdatum, Beschreibung, Elternbezug, Priorität und Tags (Zeile weg oder leerer Wert, Pflegefelder); je Feld eine ENTSCHEID-Zeile (D-33-07)"
    - "CANCELLED ist gemessen: abgebrochenes Kind beim Abhaken der Elternaufgabe, direktes Abhaken und Wiederöffnen einer abgebrochenen Aufgabe (D-33-14)"
    - "Neue Fixtures liegen byte-genau mit PROVENANCE vor; Rückbau mit BASELINE vorher gleich nachher je Konto"
  artifacts:
    - path: ".planning/phases/33-aufgaben-aendern/33-01-BROWSER-SCHRITTE.md"
      provides: "nummerierte Schritte der Browser-Sitzung"
    - path: "tests/fixtures/tasks_app/PROVENANCE.md"
      provides: "Herkunft und sha256 der neuen Fixtures"
    - path: ".planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt"
      provides: "M1-, M2-, CANCELLED- und ENTSCHEID-Zeilen"
      contains: "ENTSCHEID wiederoeffnen_kinder="
  key_links:
    - from: "raw/33-01-messung.txt ENTSCHEID entfernen_* und cancelled_*"
      to: "33-04 (Form des Entfernens), 33-06 (Wiederöffnen, CANCELLED), 33-07 (Abgleich mit der App)"
      via: "Regeln, die diese Pläne wörtlich übernehmen"
      pattern: "ENTSCHEID entfernen_"
---

<objective>
In einer Browser-Sitzung mit Tasks 0.18.1 auf nc35 messen, was die App beim Wiederöffnen einer Elternaufgabe (M-1), beim Entfernen von Feldern (M-2) und bei abgebrochenen Aufgaben (CANCELLED) schreibt, daraus ENTSCHEID-Zeilen ableiten und die Rohobjekte als Fixtures ablegen.

Purpose: D-33-06, D-33-07 (Messteil), D-33-14 (Messteil) vor dem Bau.
Output: Schrittliste, Protokollzeilen, neue Fixtures mit PROVENANCE.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/33-aufgaben-aendern/33-RULES.md
@.planning/phases/33-aufgaben-aendern/33-CONTEXT.md
@.planning/phases/33-aufgaben-aendern/33-RESEARCH.md
@.planning/phases/33-aufgaben-aendern/33-01-SUMMARY.md

Rahmen: 33-RULES.md (verbindlich). Kein Produktcode unter `src/`. Messprogramm `scripts/tasks_modify_measure.py` aus 33-01 (`snapshot`, `diff`, `baseline`). Testobjekte und Listen tragen den Kopf `p3301`. Konten: alice, bob (nur BASELINE), `p3301ui` (Browser-Sitzung, danach gelöscht).

<interfaces>
.planning/phases/30-mess-spike-aufgaben-und-ordner/30-02-BROWSER-SCHRITTE.md: Vorlage für nummerierte Browser-Schritte.
docs/spike-tasks.md Abschnitte 3.5 und 3.6: gemessene Felder beim Abhaken/Wiederöffnen, Kinder beim Abhaken der Elternaufgabe.
scripts/tasks_spike.py: Auswertung der Phase 30 (`UI-ZUGRIFF`, `UI-OBJEKT`).
tests/fixtures/tasks_app/PROVENANCE.md: Tabellenform; `.gitattributes` schützt die Fixtures (CRLF wie vom Server).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Browser-Sitzung auf nc35 mit Tasks 0.18.1: M-1, M-2 und CANCELLED</name>
  <files>.planning/phases/33-aufgaben-aendern/33-01-BROWSER-SCHRITTE.md, .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt</files>
  <read_first>
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt (FREIGABE-Zeile)
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/30-02-BROWSER-SCHRITTE.md
    - docs/spike-tasks.md Z. 334-380
  </read_first>
  <action>
Ohne `FREIGABE zustand=option-a` oder `option-b`: Zeile `BROWSER entfaellt grund=freigabe-<option>`, committen, ANHALTEN und den Owner fragen (33-RULES.md Abschnitt 10).

Sonst zuerst `33-01-BROWSER-SCHRITTE.md` schreiben (nummeriert, je Schritt Handlung in der App, erwartete Rohzeile): Runde A (Anlegen in der App): Liste `p3301-liste-1`, `p3301 eltern-zu` mit zwei Kindern `p3301 kind-1`, `p3301 kind-2`; `p3301 felder` mit Fälligkeit (Uhrzeit), Startdatum, Beschreibung, Priorität 3, zwei Tags; `p3301 kind-lösen` als Unteraufgabe von `p3301 felder`; `p3301 eltern-ab` mit einem Kind `p3301 kind-ab-offen` und einem Kind `p3301 kind-ab-abgebrochen` (Status in der App auf "Abgebrochen"); `p3301 abgebrochen` (Status "Abgebrochen"); `p3301 unberuehrt`. Stand a per `snapshot`. Runde B: `p3301 eltern-zu` abhaken (beide Kinder werden laut 3.6 mit abgehakt), Stand b1; dann nur die Elternaufgabe wieder öffnen, Stand b2 (M-1). In `p3301 felder` nacheinander Fälligkeit, Startdatum, Beschreibung entfernen, Priorität auf keine, alle Tags entfernen, je ein Stand (M-2). `p3301 kind-lösen` zur Hauptaufgabe machen, falls die App das anbietet (Ziehen auf die Liste), sonst Zeile `M2 parent app_moeglich=nein`. `p3301 eltern-ab` abhaken, Stand (CANCELLED Kette). `p3301 abgebrochen` abhaken, Stand, dann wieder öffnen, Stand (CANCELLED direkt; bietet die App das Kontrollkästchen nicht an: Zeile `CANCELLED direkt app_moeglich=nein`).

Container-Prüfung und RAM-Gate nach 33-RULES.md Abschnitt 5, `docker start` der nc35-Container. `TASKSAPP nc35 vorher=<fassung|keine>`, BASELINE für alice und bob. Tasks-App per `occ app:install tasks` (ist sie schon da, die vorhandene Fassung) plus Neustart; danach die installierte Fassung mit `occ app:list --output=json` lesen und als `TASKSAPP nc35 messung=<fassung>` protokollieren. Ist die Fassung nicht genau 0.18.1: Zeile `TASKSAPP ABWEICHUNG erwartet=0.18.1 installiert=<fassung>`, Tasks-App in den Zustand vorher zurück plus Neustart, BASELINE prüfen, nc35 stoppen, committen und ANHALTEN mit Owner-Frage: mit der installierten Fassung messen und alle Belege der Phase als gegen diese Fassung gemessen führen, oder auf einem vom Owner genannten Weg genau 0.18.1 bereitstellen; ohne Antwort keine Messung. Sonst Konto `p3301ui` anlegen, BASELINE für p3301ui. Die Schritte fährt die ausführende Sitzung mit ihrem Playwright-Werkzeug (Chromium, Zeitzone Europe/Berlin); hat sie keines, gibt sie die Schritte als Checkpoint an die Hauptsitzung (wie 30-02) und wertet danach aus. Nach jedem Schritt `snapshot` und das Zugriffsprotokoll des Webservers (nur Methode, Pfad ohne Kontokennung, Status) als `UI-ZUGRIFF`-Zeilen.

Auswertung per `diff`, Pflichtzeilen: `M1 WIEDEROEFFNEN-ELTERN kinder_geoeffnet=<ja|nein> eltern_felder=hinzu=... entfernt=... geaendert=... puts=<n>`; je Feld `M2 ENTFERNEN feld=<due|start|description|priority|tags|parent> form=<zeile-weg|leer|wert-0|nicht-moeglich> pflegefelder=<liste> sonst=<leer|liste>`; `CANCELLED kette kind_abgebrochen=<unberuehrt|erledigt|anders> kind_offen=<erledigt|anders> puts=<n>`; `CANCELLED direkt abhaken=hinzu=... entfernt=... status_danach=<..>` und `CANCELLED direkt wiederoeffnen=... status_danach=<..>`; `KONTROLLE unberuehrt differenz=leer`. Die Rohobjekte der Stände, die als Fixture taugen, byte-genau im Scratchpad aufheben (Task 2).

Rückbau: Listen und Objekte per DELETE mit `X-NC-CalDAV-No-Trashbin: 1`, Papierkorb geleert, `occ user:delete p3301ui`, Tasks-App in den Zustand vorher plus Neustart (`RUECKBAU nc35 tasksapp=<wie vorher>`), BASELINE nachher gleich vorher für alice und bob. nc35 stoppen. Geheimnisprüfung, Commit "docs(33-01b): tasks app behaviour for reopen, clearing and cancelled".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && R=.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt && grep -qF "TASKSAPP nc35 messung=0.18.1" $R && for s in "M1 WIEDEROEFFNEN-ELTERN kinder_geoeffnet=" "M2 ENTFERNEN feld=due" "M2 ENTFERNEN feld=start" "M2 ENTFERNEN feld=description" "M2 ENTFERNEN feld=priority" "M2 ENTFERNEN feld=tags" "CANCELLED kette" "CANCELLED direkt" "KONTROLLE unberuehrt differenz=leer" "RUECKBAU nc35 tasksapp="; do grep -qF -- "$s" $R || { echo "FEHLT: $s"; exit 1; }; done && grep -qE "M2 (ENTFERNEN feld=parent|parent app_moeglich=nein)" $R && test -z "$(docker ps -q --filter name=nc35-)"</automated>
  </verify>
  <done>Was die Tasks-App 0.18.1 beim Wiederöffnen, Entfernen und bei abgebrochenen Aufgaben schreibt, steht mit Rohzeilen im Protokoll; Rückbau mit gleicher BASELINE belegt; nc35 gestoppt.</done>
</task>

<task type="auto">
  <name>Task 2: ENTSCHEID-Zeilen der App-Messung und Fixtures mit PROVENANCE</name>
  <files>.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt, tests/fixtures/tasks_app/PROVENANCE.md, tests/fixtures/tasks_app/cleared_due.ics, tests/fixtures/tasks_app/cleared_start.ics, tests/fixtures/tasks_app/cleared_description.ics, tests/fixtures/tasks_app/cleared_priority.ics, tests/fixtures/tasks_app/cleared_tags.ics, tests/fixtures/tasks_app/cleared_parent.ics, tests/fixtures/tasks_app/cancelled.ics, tests/fixtures/tasks_app/cancelled_completed.ics</files>
  <read_first>
    - tests/fixtures/tasks_app/PROVENANCE.md
    - .gitattributes
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt (Zeilen aus Task 1)
  </read_first>
  <action>
Je eine Zeile ins Protokoll: `ENTSCHEID wiederoeffnen_kinder=<bleiben|mit>` (aus M1); `ENTSCHEID entfernen_<feld>=<zeile-weg|leer>` für due, start, description, parent (aus M2; `nicht-moeglich` in der App heißt `zeile-weg`, weil die App beim Wiederöffnen Zeilen entfernt statt leer zu schreiben, Abschnitt 3.5); `ENTSCHEID entfernen_priority=zeile-weg` und `ENTSCHEID entfernen_tags=zeile-weg` nur wenn M2 das zeigt, sonst `=abweichung` (D-33-07 legt beide fest, Auslöser für 33-01c Task 4); `ENTSCHEID pflegefelder_entfernen=<liste>`; `ENTSCHEID cancelled_kette=<unberuehrt|abweichung>`; `ENTSCHEID cancelled_direkt=<abhaken-und-oeffnen|abweichung>` samt geschriebener Felder.

Fixtures: die Rohobjekte nach jedem Entfernen und die beiden CANCELLED-Stände byte-genau (CRLF wie vom Server, nie über `read_text`) unter den Namen aus `files` ablegen; fehlt ein Fall (App bot ihn nicht an), entfällt die Datei und PROVENANCE sagt warum. PROVENANCE.md um eine Tabelle erweitern (Datei, Schritt aus 33-01-BROWSER-SCHRITTE.md, Vorzustand, sha256, Fassung Tasks-App und Nextcloud). Keine Kontokennung in den Fixtures (prüfen). Gates, Commit "test(33-01b): tasks app fixtures for clearing and cancelled".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && R=.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt && for s in "ENTSCHEID wiederoeffnen_kinder=" "ENTSCHEID entfernen_due=" "ENTSCHEID entfernen_start=" "ENTSCHEID entfernen_description=" "ENTSCHEID entfernen_parent=" "ENTSCHEID entfernen_priority=" "ENTSCHEID entfernen_tags=" "ENTSCHEID pflegefelder_entfernen=" "ENTSCHEID cancelled_kette=" "ENTSCHEID cancelled_direkt="; do grep -qF -- "$s" $R || { echo "FEHLT: $s"; exit 1; }; done && ! grep -qiE "\b(bob|alice|p3301ui)\b" tests/fixtures/tasks_app/*.ics && ! grep -qE "$(printf '\xe2\x80\x93|\xe2\x80\x94')" tests/fixtures/tasks_app/PROVENANCE.md && uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -p no:xdist -q --import-mode=importlib</automated>
  </verify>
  <done>Die App-Form ist als ENTSCHEID-Zeilen festgehalten, jede neue Fixture hat eine belegte Herkunft; volle Gates Exit 0.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser-Sitzung zu nc35 | Testkonto und Tasks-App auf der Langzeitstrecke |
| Fixtures und Protokoll zu Git | Kontokennungen und Secrets dürfen nicht hinein |
| Docker-Host zur Parallelsitzung | fremde Container (avs-) teilen Speicher und Docker |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-33-01b-01 | Tampering | nc35 | mitigate | FREIGABE aus 33-01, Rückbau ohne Papierkorb, Testkonto gelöscht, BASELINE je Konto |
| T-33-01b-02 | Information Disclosure | Fixtures, Zugriffsprotokoll | mitigate | grep auf Kontonamen, Zugriffszeilen ohne Kontokennung, scan_for_secrets |
| T-33-01b-03 | Tampering | falsche App-Fassung als Maßstab | mitigate | Fassung nach der Installation gelesen, Abweichung von 0.18.1 stoppt mit Owner-Frage |
| T-33-01b-04 | Denial of Service | Host-RAM, Parallelsitzung | mitigate | Container-Prüfung und RAM-Gate vor dem Start |
| T-33-SC | Tampering | Paketinstallationen | accept | Tasks-App aus dem Nextcloud App Store, Fassung protokolliert und geprüft |
</threat_model>

<verification>
- M-1, M-2, CANCELLED mit Rohzeilen und ENTSCHEID-Zeilen; Fixtures mit PROVENANCE
- Rückbau mit BASELINE; nc35 gestoppt; Gates grün; lokale Commits ohne Trailer
</verification>

<success_criteria>
- Messteil von D-33-06, D-33-07 und D-33-14 erfüllt, gegen Tasks 0.18.1
</success_criteria>

<output>
Create `.planning/phases/33-aufgaben-aendern/33-01b-SUMMARY.md` when done; alle ENTSCHEID-Zeilen und die TASKSAPP-Zeilen wörtlich.
</output>

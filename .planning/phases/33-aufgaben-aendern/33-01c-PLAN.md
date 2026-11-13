---
phase: 33-aufgaben-aendern
plan: 01c
type: execute
wave: 3
depends_on: ["33-01b"]
files_modified:
  - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt
  - docs/tasks-evidence.md
autonomous: false
requirements: [TMOD-01, TMOD-03, TMOD-08]

must_haves:
  truths:
    - "M-3 ist auf nc35 und, bei FREIGABE option-a, auf Nextcloud 32 unter Impersonation gemessen: Gesamtlaufzeit einer Kette mit 50 Nachfahren (Tiefe 1 und 3) für PUT mit If-Match und für MOVE mit Overwrite F und If-Match, min/median/max (D-33-10)"
    - "Die Regel für chain_cap stand vor der Messung fest (33-01 Task 1, chain_cap()): 50 bleibt, wenn derive_budget(max_gesamt_s) höchstens 30 s ergibt"
    - "M-4 ist gemessen: trägt die Antwort auf einen PUT eine ETag, wenn der Server den Text beim Speichern verändert hat"
    - "MESSWERT chain_cap und ENTSCHEID etag_nach_veraendertem_text stehen im Protokoll; docs/tasks-evidence.md hat den Abschnitt '## Measurements before the modifying tools' mit allen Werten aus 33-01b und 33-01c"
    - "Weicht ein Messwert von D-33-05, D-33-07, D-33-10 oder D-33-14 ab, ist der Owner gefragt und die Antwort steht als OWNERFRAGE-Zeile im Protokoll, bevor 33-02 beginnt"
    - "BASELINE vor und nach jedem Lauf je Konto gleich; am Ende läuft keine eigene Instanz"
  artifacts:
    - path: ".planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt"
      provides: "KETTE-, ETAGFORM-, MESSWERT- und OWNERFRAGE-Zeilen"
      contains: "MESSWERT chain_cap="
    - path: "docs/tasks-evidence.md"
      provides: "Abschnitt '## Measurements before the modifying tools'"
      contains: "## Measurements before the modifying tools"
  key_links:
    - from: "raw/33-01-messung.txt MESSWERT chain_cap, OWNERFRAGE"
      to: "33-05 (CHAIN_CAP), 33-04 und 33-06 (Antworten des Owners)"
      via: "Werte, die diese Pläne wörtlich übernehmen"
      pattern: "MESSWERT chain_cap="
---

<objective>
Die Kosten einer Kette mit 50 Nachfahren für PUT und MOVE auf Nextcloud 35 und 32 messen (M-3), die ETag-Form nach vom Server verändertem Text prüfen (M-4), alle Werte der Messpläne ableiten und belegen und den Owner bei jeder Abweichung von einer Owner-Entscheidung fragen, bevor gebaut wird.

Purpose: D-33-10 (Messteil), M-4 (Pitfall 10), Owner-Frage nach D-33-06, D-33-07, D-33-10, D-33-14.
Output: Protokollzeilen, Abschnitt im Beleg, OWNERFRAGE-Zeilen.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/33-aufgaben-aendern/33-RULES.md
@.planning/phases/33-aufgaben-aendern/33-CONTEXT.md
@.planning/phases/33-aufgaben-aendern/33-01-SUMMARY.md
@.planning/phases/33-aufgaben-aendern/33-01b-SUMMARY.md

Rahmen: 33-RULES.md (verbindlich). Kein Produktcode unter `src/`. Messungen auf Funktionsebene unter Impersonation (`Credentials(mode=MODE_APPAPI, ...)` aus `src`, nur importiert); die registrierte ExApp bleibt unverändert. Testobjekte tragen den Kopf `p3301`. Messprogramm `scripts/tasks_modify_measure.py` (`chain`, `etag-altered`, `baseline`).

<interfaces>
docs/spike-tasks.md Abschnitte 3.1, 4.1 und 6 (PUT und MOVE unter Impersonation, Kosten des REPORT bei 2000 Aufgaben).
docs/tasks-evidence.md: Gliederung, Abschnitt "## Measurements before the build" als Form, "## Not measured".
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: M-3 und M-4 auf nc35 unter Impersonation</name>
  <files>.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt</files>
  <read_first>
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt (FREIGABE-Zeile)
    - docs/spike-tasks.md Abschnitte 3.1, 4.1, 6
  </read_first>
  <action>Diese Messung läuft nur mit `FREIGABE zustand=option-a` oder `option-b` (bei option-c hat 33-01b schon angehalten). Container-Prüfung und RAM-Gate nach 33-RULES.md Abschnitt 5; `docker start` der nc35-Container. BASELINE alice. Listen `p3301-kette-a` und `p3301-kette-b` (VTODO) für alice. Regel aus 33-01 Task 1 (vor der Messung festgelegt, wird nicht geändert): Zielwert für eine ganze Kette ist, dass `derive_budget(max_gesamt_s)` höchstens 30 s ergibt (die Hälfte einer üblichen Wartezeit von 60 s eines MCP-Clients); dann bleibt `chain_cap=50`, sonst gilt `chain_cap()` und die Owner-Frage in Task 4. `chain --instance nc35 --mode put --depth 1 --runs 5`, dasselbe mit `--depth 3`, dann `--mode move` je Tiefe, Zeilen `KETTE nc35 ...`. Dazu `etag-altered` (M-4), Zeilen `ETAGFORM nc35 ...`. Alle Ketten werden nach jedem Lauf zurückgebaut (`X-NC-CalDAV-No-Trashbin: 1`), am Ende Listen entfernt, Papierkorb geleert, BASELINE gleich. nc35 stoppen. Geheimnisprüfung, Commit "docs(33-01c): chain cost and etag form on Nextcloud 35".</action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && R=.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt && for s in "KETTE nc35 modus=put tiefe=1 min_ms" "KETTE nc35 modus=put tiefe=3 min_ms" "KETTE nc35 modus=move tiefe=1 min_ms" "KETTE nc35 modus=move tiefe=3 min_ms" "ETAGFORM nc35 fall="; do grep -qF -- "$s" $R || { echo "FEHLT: $s"; exit 1; }; done && test -z "$(docker ps -q --filter name=nc35-)"</automated>
  </verify>
  <done>Kosten einer Kette mit 50 Nachfahren und die ETag-Form nach verändertem Text sind auf 35 gemessen; nc35 gestoppt.</done>
</task>

<task type="auto">
  <name>Task 2: M-3 auf Nextcloud 32 unter Impersonation (nur bei option-a)</name>
  <files>.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt</files>
  <read_first>
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-01-SUMMARY.md (Start der 32er Strecke)
  </read_first>
  <action>Bei option-b: Zeile `NC32 entfaellt grund=freigabe-option-b`, committen. Sonst Container-Prüfung, RAM-Gate, nc35 gestoppt, Topologie nc-mcp-exapp starten (nur `start`). BASELINE alice. Dieselben vier Reihen wie Task 1 mit `--instance nc32` (Zeilen `KETTE nc32 ...`), Rückbau, BASELINE gleich, stoppen. Geheimnisprüfung, Commit "docs(33-01c): chain cost on Nextcloud 32".</action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && R=.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt && { grep -qF "NC32 entfaellt grund=freigabe-option-b" $R || for s in "KETTE nc32 modus=put tiefe=1 min_ms" "KETTE nc32 modus=put tiefe=3 min_ms" "KETTE nc32 modus=move tiefe=1 min_ms" "KETTE nc32 modus=move tiefe=3 min_ms"; do grep -qF -- "$s" $R || { echo "FEHLT: $s"; exit 1; }; done; } && test -z "$(docker ps -q --filter name=nc-mcp-exapp)"</automated>
  </verify>
  <done>Die Kettenkosten sind auch auf 32 gemessen oder ehrlich als nicht gemessen markiert.</done>
</task>

<task type="auto">
  <name>Task 3: Werte ableiten und Abschnitt im Beleg</name>
  <files>.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt, docs/tasks-evidence.md</files>
  <read_first>
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt
    - docs/tasks-evidence.md (Gliederung)
  </read_first>
  <action>
Zeilen ins Protokoll: `ENTSCHEID etag_nach_veraendertem_text=<fehlt|vorhanden|nicht-beobachtet>`, `MESSWERT kette_max_gesamt_s=<max über 35 und 32, alle Modi und Tiefen>`, `MESSWERT chain_cap=<n>` nach der Regel aus Task 1 (ohne Messung auf 32: Zusatz `quelle=nc35 annahme=32-ungemessen`), `MESSWERT kette_antwort_ids=<n>` (größte Zahl von Ids in einer Antwort, gleich chain_cap).

docs/tasks-evidence.md: neuer Abschnitt `## Measurements before the modifying tools` (englisch) mit jedem Wert aus 33-01b und 33-01c und der wörtlich zitierten Rohzeile; `## Not measured` um das ergänzen, was durch die Freigabe entfiel. Kein Besitzername, keine Kontokennung im neuen Abschnitt (der Altbestand aus Phase 32 enthält absichtlich Fallnamen wie `zustand=an-bob-ro` und wird nicht geprüft). Gates, Commit "docs(33-01c): values derived for the modifying tools".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && R=.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt && for s in "ENTSCHEID etag_nach_veraendertem_text=" "MESSWERT chain_cap=" "MESSWERT kette_max_gesamt_s=" "MESSWERT kette_antwort_ids="; do grep -qF -- "$s" $R || { echo "FEHLT: $s"; exit 1; }; done && SEC=$(awk '/^## Measurements before the modifying tools/{f=1;print;next} /^## /{f=0} f' docs/tasks-evidence.md) && test -n "$SEC" && ! printf '%s' "$SEC" | grep -qiE "\b(bob|alice|p3301ui)\b" && ! grep -qE "$(printf '\xe2\x80\x93|\xe2\x80\x94')" docs/tasks-evidence.md $R && uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -p no:xdist -q --import-mode=importlib</automated>
  </verify>
  <done>Die Folgepläne haben ihre Werte; der Beleg nennt die Herkunft jedes Wertes; volle Gates Exit 0.</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 4: Owner-Fragen bei Abweichung von D-33-05, D-33-07, D-33-10 oder D-33-14</name>
  <files>.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt</files>
  <read_first>
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt (ENTSCHEID- und MESSWERT-Zeilen)
    - .planning/phases/33-aufgaben-aendern/33-CONTEXT.md (D-33-05 bis D-33-14)
  </read_first>
  <action>Auslöser, je unabhängig geprüft: (1) `ENTSCHEID wiederoeffnen_kinder=mit` (D-33-06: die App öffnet Kinder mit; D-33-05 sagt nur die genannte Aufgabe); (2) `ENTSCHEID entfernen_priority=abweichung` oder `entfernen_tags=abweichung` (D-33-07 legt Zeile weg fest, die App schreibt anders); (3) `ENTSCHEID cancelled_kette=abweichung` oder `cancelled_direkt=abweichung` (D-33-14); (4) `MESSWERT chain_cap` ungleich 50 (D-33-10). Ohne Auslöser: Zeile `OWNERFRAGE entfaellt grund=keine-abweichung`, committen, 33-02 darf beginnen. Mit Auslöser: dem Owner je Auslöser die Rohzeilen und die zwei Optionen vorlegen; Antwort je Auslöser als `OWNERFRAGE <ausloeser> antwort=<option> datum=<YYYY-MM-DD>` protokollieren und committen ("docs(33-01c): owner answers on measured deviations"). Die Antwort wird in 33-06 (Wiederöffnen, CANCELLED), 33-04 (Form des Entfernens) und 33-05 (chain_cap) wörtlich übernommen. Kein Bau, bevor jede Frage beantwortet ist.</action>
  <decision>Je Auslöser: folgt der Connector der Owner-Entscheidung aus 33-CONTEXT.md oder dem gemessenen Verhalten der Tasks-App bzw. dem Messwert?</decision>
  <context>D-33-06, D-33-10 und D-33-14 verlangen ausdrücklich die Rückfrage bei Abweichung. Für D-33-07 betrifft die Frage nur Priorität und Tags; die Form für Fälligkeit, Startdatum, Beschreibung und Elternbezug übernimmt die Planung ohne Rückfrage aus der Messung.</context>
  <options>
    <option id="option-a">
      <name>Owner-Entscheidung bleibt (D-33-05/07/10/14 wie beschlossen)</name>
      <pros>Kein Massen-Schreibzugriff beim Wiederöffnen; Schema wie entschieden; Obergrenze 50</pros>
      <cons>Weicht an dieser Stelle bewusst von der Tasks-App bzw. vom Messwert ab</cons>
    </option>
    <option id="option-b">
      <name>Dem Gemessenen folgen</name>
      <pros>Verhalten wie die Tasks-App; Obergrenze aus dem Messwert</pros>
      <cons>Mehr Schreibzugriffe oder andere Form; Pläne 33-04 bis 33-06 übernehmen die Änderung</cons>
    </option>
  </options>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && grep -qE "OWNERFRAGE (entfaellt grund=keine-abweichung|[a-z_]+ antwort=option-[ab] datum=)" .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt</automated>
  </verify>
  <resume-signal>Je Auslöser option-a oder option-b eingeben</resume-signal>
  <done>Jede Abweichung ist vom Owner entschieden oder es gab keine; 33-02 kann beginnen.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Messprogramm zu Nextcloud | Impersonation-Kopf und App-Passwörter queren die Grenze |
| Messung zu Langzeitstrecken nc35 und 32 | viele Testobjekte auf Instanzen des Owners |
| Docker-Host zur Parallelsitzung | fremde Container (avs-) teilen Speicher und Docker |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-33-01c-01 | Tampering | nc35 und 32 | mitigate | FREIGABE aus 33-01, Rückbau je Lauf ohne Papierkorb, BASELINE vorher und nachher |
| T-33-01c-02 | Denial of Service | SQLite-Sperre, Host-RAM | mitigate | Schreibaufrufe streng nacheinander, RAM-Gate, Container-Prüfung, eine Instanz |
| T-33-01c-03 | Tampering | Entscheidungsgrundlage | mitigate | Regel für chain_cap vor der Messung festgelegt, Owner-Frage bei jeder Abweichung |
| T-33-01c-04 | Information Disclosure | Protokoll, Beleg | mitigate | scan_for_secrets, Namensprüfung im neuen Abschnitt |
| T-33-SC | Tampering | Paketinstallationen | accept | keine Paketinstallation |
</threat_model>

<verification>
- KETTE-, ETAGFORM-, MESSWERT- und OWNERFRAGE-Zeilen im Protokoll; Abschnitt im Beleg
- Rückbau mit BASELINE belegt; keine eigene Instanz läuft; Gates grün; lokale Commits ohne Trailer
</verification>

<success_criteria>
- D-33-10 (Messteil) erfüllt; jede Abweichung von D-33-05, D-33-07, D-33-10, D-33-14 vom Owner entschieden, bevor 33-02 beginnt
</success_criteria>

<output>
Create `.planning/phases/33-aufgaben-aendern/33-01c-SUMMARY.md` when done; oben ein Block "Werte für die Folgepläne" mit allen MESSWERT-, ENTSCHEID-, FREIGABE- und OWNERFRAGE-Zeilen aus raw/33-01-messung.txt wörtlich (auch die aus 33-01b).
</output>

# Phase 25: Mess-Spike Tag-Abfrage - Context

**Gathered:** 2026-09-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Die unbelegten Annahmen der v1.7-Recherche werden gemessen und protokolliert, bevor der Guard-Kern (Phase 26) designt wird: App-aus-Verhalten auf NC 32-34, REPORT oc:filter-files unter AppAPI-Impersonation, Kosten bei 1/100/5000 getaggten Knoten, der Weg Notiz-Id zu fileid, dazu die Einzelbefunde 412 (unbekannte/veraltete Tag-Id), unsichtbares Tag, gleichnamige Tag-Varianten, Zielpfad des REPORT und die Freigabe-Grenze. Die Phase baut kein Produkt-Feature; sie liefert Messvorbedingungen fuer EXCL-02, EXCL-04 und EXCL-05.

</domain>

<decisions>
## Implementation Decisions

### NC-Versions-Matrix
- **D-25-01:** NC 32, 33 und 34 werden SEQUENZIELL live gemessen: je eine Wegwerf-Instanz nacheinander (nextcloud-docker-dev), gleiches Messskript je Version. Nie mehr als eine Zusatzinstanz neben der nc35-Strecke (RAM-Merker der Box, 16 GB).
- **D-25-02:** Auf 32-34 laufen NUR die versionsabhaengigen Messungen: App-aus-Verhalten, 412-Verhalten, REPORT-Grundform. Alles andere (Impersonation, Latenz, Notes, Freigabe-Grenze, Varianten, unsichtbares Tag) laeuft ausschliesslich auf der bestehenden nc35-Strecke.

### Latenz-Messaufbau
- **D-25-03:** Datenbestand synthetisch per Skript: ein Baum mit ~10.000 Dateien, davon 1/100/5000 getaggt; ZUSAETZLICH der Extremfall aus nextcloud/server PR #64298 (10.000 Dateien in EINEM Ordner, dort wurden 6,4 s fuer nc:system-tags gemessen). Testdaten werden nach der Messung entfernt (Muster des Stack-Researchers vom 26.09.).
- **D-25-04:** Harte Schwelle: braucht der REPORT bei 5000 getaggten Knoten laenger als 1 s, stoppt die Ableitung und der Owner entscheidet am Checkpoint (Alternativen waeren Cache-Strategie oder engerer Zielpfad). Unter 1 s gilt das Design "ein REPORT je Antwort" als bestaetigt.

### Checkpoint-Regime
- **D-25-05:** EIN Owner-Checkpoint, nachdem die kritischen Messungen vorliegen (Notes-Befund, App-aus, Latenz), BEVOR Ableitungen in Phase 26/27 einfliessen. Muster der Checkpoints 22-07/24-09. Der Notes-Befund entscheidet dort ueber EXCL-05 (bauen oder dokumentiert vertagen).

### Beleg-Ablage
- **D-25-06:** Messbericht und Rohdaten INTERN in .planning/phases/25-mess-spike-tag-abfrage/ (Muster: Messbericht als eigene MD-Datei mit Kommando+Ergebnis je Zeile). Nichts davon nach docs/: was Nutzer betrifft, wandert erst mit Phase 29 kuratiert dorthin.

### Claude's Discretion
- Aufbau- und Aufraeum-Mechanik der Wegwerf-Instanzen (nextcloud-docker-dev vs. offizielle Images), solange sequenziell und rueckstandsfrei.
- Skript-Zuschnitt fuer den Datenbestand und die Zeitmessung (Median aus mehreren Laeufen o.ae.), solange die Zahlen je Messung mit Kommando und Rohwert protokolliert sind.
- Reihenfolge der Messungen innerhalb der Phase, solange die kritischen drei (Notes, App-aus, Latenz) vor dem Checkpoint liegen.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research (Grundlage aller Messfragen)
- `.planning/research/SUMMARY.md` , Synthese, Widersprueche und die deduplizierte Messliste
- `.planning/research/STACK.md` , REPORT-/PROPFIND-Formen, gemessene NC-35-Basiswerte, offene Messfragen (Impersonation, Latenz)
- `.planning/research/PITFALLS.md` , 412-Falle, unsichtbares Tag, App-aus-Fehldeutung, PR-#64298-Latenzbefund
- `.planning/research/ARCHITECTURE.md` , wohin die Ergebnisse fliessen (ExclusionGuard, NcClients), Notiz-Id-Frage

### Projekt
- `.planning/REQUIREMENTS.md` , EXCL-02/04/05 (die Requirements, deren Messvorbedingungen diese Phase liefert), D-v1.7-01..03
- `.planning/ROADMAP.md` , Phase-25-Erfolgskriterien (Messliste)

### Extern
- nextcloud/server PR #64298 , Latenz-Referenzfall nc:system-tags (10k Dateien, 6,4 s), nur als Referenz, nicht abrufpflichtig

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mcp_connector/nextcloud/clients/dav.py` , bestehende PROPFIND/REPORT-Mechanik (httpx+lxml), `_home_path_of` (Zeile ~493) und Segmentregel `in_files_root` (~490) als Muster fuer Pfadnormalisierung
- `scripts/exchange_evidence.py` , Muster fuer ein Messskript gegen die nc35-Strecke (Aufbau, Messung, Rueckbau, Protokollzeilen)
- `compose.nc35.yml` , die bestehende Teststrecke; NC-32-34-Instanzen kommen daneben, sequenziell

### Established Patterns
- Messbericht-Stil: jede Behauptung mit Kommando und Rohwert (docs/exchange-evidence.md als Formatvorbild, Ablage hier aber intern)
- Testdaten-Hygiene: Sonden nach der Messung entfernen (Stack-Research 26.09. hat es vorgemacht: Tag, Share, Dateien, App-Passwoerter entfernt)

### Integration Points
- Ergebnisse fliessen in Phase 26 (Guard-Kern-Design) und in den EXCL-05-Entscheid (Notes) am Checkpoint

</code_context>

<specifics>
## Specific Ideas

- Die Messungen muessen die vier Widersprueche/Unsicherheiten der Research-Synthese schliessen: App-aus (STACK hat NC 35 gemessen, 32-34 offen), REPORT-Zielpfad, Notiz-Id=fileid, AppAPI-Impersonation.
- Owner-Checkpoint-Format wie gewohnt: kompakte Befundliste mit Empfehlung, Antwort in einem Satz moeglich.

</specifics>

<deferred>
## Deferred Ideas

- Keine neuen. Die vier offenen Designfragen (Ordner-Tag als Ausschlussliste, Admin-Schalter: Phase 26; Upload-Orakel, Zaehlen-vs-Schweigen: Phase 27) stehen bereits an ihren Phasen und werden hier nicht entschieden.

</deferred>

---

*Phase: 25-Mess-Spike Tag-Abfrage*
*Context gathered: 2026-09-26*

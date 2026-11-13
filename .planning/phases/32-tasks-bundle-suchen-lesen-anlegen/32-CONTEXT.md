# Phase 32: Tasks-Bundle suchen, lesen, anlegen - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Ein Assistent kann Nextcloud-Aufgaben suchen, lesen und anlegen: drei Werkzeuge `tasks_search`, `tasks_read` und `tasks_create` als zehnte Familie `tasks`, über CalDAV `VTODO`. Das Bundle schreibt nie still in eine geteilte Liste, zeigt nie Deck-Karten und ändert das Verhalten des Kalender-Bundles nicht. Die Phase ist ohne Phase 33 releasefähig.

Nicht in dieser Phase: Abhaken, Wiederöffnen, Ändern und Verschieben einer Aufgabe (Phase 33); Löschen (gestrichen, E13); Aufgabenlisten anlegen, umbenennen oder teilen; Store-Text und Release (Phase 34); der Tag-Alias `no-ai` (eigene Phase nach 0.8.0).

Die Anforderungen TASK-01 bis TASK-09 und die fünf Erfolgskriterien in ROADMAP.md sind fest. Diese Datei hält nur die Entscheidungen fest, die dort offen waren.

</domain>

<decisions>
## Implementation Decisions

### Unteraufgaben
- **D-32-01:** `tasks_read` liefert zu einer Aufgabe die Liste ihrer direkten Unteraufgaben, je mit `task:`-Id, Titel und Status. So beantwortet der Assistent "Was ist bei Projekt X noch offen?" mit einem Aufruf. (Owner, 13.11.2026, Auswahl "Liste der Unteraufgaben")
- **D-32-02:** Die Liste geht genau eine Ebene tief. Enkel sieht der Assistent, wenn er eine Unteraufgabe selbst liest. (Owner, 13.11.2026, Auswahl "Nur direkte Kinder")
- **D-32-03:** Die zusätzliche Abfrage für die Kinder (`REPORT` mit `text-match` an `RELATED-TO`, docs/spike-tasks.md 5.3 und 9.4 Punkt 2) wird vor dem Bau gemessen, auch bei 2000 Aufgaben in einer Liste; die Kostenreihen des Spikes kennen sie nicht. Sie bekommt ein eigenes Zeitbudget. Wird es überschritten oder scheitert die Abfrage, kommt die Aufgabe trotzdem zurück, ohne Kinderliste und mit einem ehrlichen Hinweis, dass die Unteraufgaben nicht gelesen werden konnten. Eine leere Liste heißt nur dann "keine Unteraufgaben", wenn die Abfrage geantwortet hat. (Bedingung der gewählten Option, Owner 13.11.2026)
- **D-32-04:** In `tasks_search` ist jede Unteraufgabe ein eigener, normaler Treffer und nennt Id und Titel ihrer Elternaufgabe. Keine Gruppierung unter dem Elterntreffer: Sortierung, Fälligkeitsfilter und Blättern gelten für jede Aufgabe einzeln. (Owner, 13.11.2026, Auswahl "Eigene Treffer mit Elternverweis")

### Geteilte Listen
- **D-32-05:** Nennt der Assistent keine Liste, sucht `tasks_search` in eigenen und in hineingeteilten Aufgabenlisten. Der Parameter `list` schränkt auf eine Liste ein und wird, wie beim Schreiben, nur gegen die Discovery aufgelöst. (Owner, 13.11.2026, Auswahl "Eigene und geteilte")
- **D-32-06:** Jeder Treffer und jede gelesene Aufgabe nennt ihre Liste mit drei Angaben: Name der Liste, wie Nextcloud ihn anzeigt, geteilt ja oder nein, beschreibbar ja oder nein. Der Name oder die Kennung der Person, die geteilt hat, kommt in keine Antwort des Bundles. "Beschreibbar" stammt aus der Discovery (`{http://owncloud.org/ns}read-only`, docs/spike-tasks.md 5.2), nicht aus einem Schreibversuch. (Owner, 13.11.2026, Auswahl "Listenname, geteilt, beschreibbar")

### Geteilte Listen, Nachtrag nach der Recherche (Owner, 13.11.2026, "Ok machen wir so")
Anlass: 32-RESEARCH.md, Befund K1. Nextcloud schreibt die teilende Person selbst in jede geteilte Liste: der `displayname` lautet `<Name> (<Anzeigename des Besitzers>)`, die URI `<uri>_shared_by_<Kontokennung>`. "Name wie Nextcloud ihn anzeigt" und "keine Kennung in irgendeiner Antwort" aus D-32-06 gehen deshalb nicht wörtlich zusammen. Entschieden ist die strenge Lesart:
- **D-32-14:** Der Listenname einer geteilten Liste wird ohne den Klammerzusatz mit dem Besitzer ausgegeben (aus `Team-Aufgaben (bob)` wird `Team-Aufgaben`). Der Zusatz wird über einen Abgleich erkannt, der selbst nie ausgegeben wird (Vorschlag der Recherche: `{http://nextcloud.com/ns}owner-displayname`). In der `task:`-Id und in jeder anderen Antwort steht für eine geteilte Liste statt der URI ein neutraler Schlüssel, der aus der URI berechnet wird (Vorschlag der Recherche: `s` plus 16 Hex-Zeichen von sha256 der URI). Vor dem Bau wird auf Nextcloud 32 und 35 gemessen, ob sich der Zusatz verlässlich erkennen und entfernen lässt (Annahme A2 der Recherche). Trägt die Messung das nicht sauber, wird NICHT der Name samt Zusatz mitgegeben, sondern die Hauptsitzung fragt den Owner. Tragen zwei geteilte Listen denselben Namen, unterscheidet sie der Schlüssel; ein Fehler beim Schreiben nennt dann beide Schlüssel.
- **D-32-15:** Für eine Aufgabe in einer geteilten Liste verlinkt `fetch` nur auf die Startseite der Tasks-App, weil der direkte Link `_shared_by_<Kontokennung>` enthält. Für eigene Listen bleibt der direkte Link.
- **D-32-16:** Nennt `tasks_create` nur `parent` und liegt die Elternaufgabe in einer geteilten Liste, gilt das NICHT als ausdrückliche Nennung der Liste nach E4. Ohne `list` kommt ein Fehler mit dem Hinweis, die Liste ausdrücklich zu nennen; geschrieben wird nichts.

### Nachtrag nach der Verifikation (Owner, 13.11.2026, per Abfrage, beide wie empfohlen)
Anlass: 32-VERIFICATION.md, Warnungen W1 und W5. Umgesetzt in 32-09 (Lücken schließen).
- **D-32-17 (W1):** In `search` (Feld `text`) und `unified_search` (Feld `subline`) wird bei Treffern des Providers `tasks` aus geteilten Listen der Besitzerzusatz aus dem Listennamen entfernt, nach derselben Regel wie D-32-14 (`owner-displayname`). Damit passt die Zeile zum gekürzten Link (D-32-15). Der Besitzer wird nie ausgegeben: lässt sich der Zusatz nicht sicher erkennen und entfernen, entfällt die Zeile für diesen Treffer, statt sie ungeprüft weiterzureichen. Das betrifft die Bundles `search` und `chatgpt`, nicht nur `tasks`; die Beschränkung von D-32-06 auf das Bundle `tasks` ist für diesen Fall aufgehoben.
- **D-32-18 (W5), strenge Variante:** Eine EIGENE Liste, die der Nutzer selbst an andere geteilt hat, gilt für die Zielwahl in `tasks_create` als fremdsichtbar. Ohne ausdrückliches `list` wird nicht hineingeschrieben. Die Discovery erkennt Freigaben eigener Listen; wie das auf Nextcloud 32 und 35 zuverlässig geht (zum Beispiel über `invite` oder `share-access`), wird vor dem Bau gemessen. Trägt die Messung keine verlässliche Erkennung, wird nicht geraten, sondern die Hauptsitzung fragt den Owner (Linie wie D-32-14). Der Fehler nennt den Ausweg `list`.
  - Festlegung der Planung (32-09), vom Owner an die Planung übertragen ("Das genaue Verhalten legst du fest"): (1) Es bleibt bei der Regel aus E4, dass ohne `list` nur bei genau einer eigenen beschreibbaren Liste geschrieben wird; ist genau diese eine Liste hinausgeteilt, kommt ein Fehler mit dem Ausweg `list=<Name>` und der Liste der beschreibbaren Listen, wie im Fall "nur geteilte beschreibbare Listen". Grund: Die Liste zählt dann nicht mehr als "die eine eigene Liste", und es bleibt keine Liste übrig, die ohne Nennung in Frage käme. (2) Gibt es mehrere eigene beschreibbare Listen, bleibt es beim bisherigen Fehler "more than one"; eine nicht geteilte Liste wird NICHT still gewählt, nur weil die anderen hinausgeteilt sind. Grund: Das wäre eine neue Auswahlregel, die vom Freigabestand anderer Listen abhängt; ein Assistent könnte nicht vorhersagen, wohin geschrieben wird, und E4 kennt nur "genau eine". (3) Gibt es keine beschreibbare Liste, gilt unverändert der bisherige Fehler, ohne jede Liste unverändert E6. (4) Liegt die Elternaufgabe (`parent`) in einer eigenen, hinausgeteilten Liste und fehlt `list`, gilt das wie D-32-16 nicht als Nennung: Fehler mit Ausweg `list`, nichts geschrieben. (5) Eine Liste mit öffentlichem Link (veröffentlicht) gilt ebenfalls als hinausgeteilt, falls die Messung sie erkennt. (6) Ist der Freigabestand einer eigenen Liste aus der Discovery nicht lesbar, gilt sie als hinausgeteilt (im Zweifel nicht schreiben), sofern die Messung belegt, dass eine nicht geteilte eigene Liste die Eigenschaft auf 32 und 35 lesbar meldet. (7) Antworten der Werkzeuge behalten die drei Listenangaben aus D-32-06 (`name`, `shared`, `writable`); `shared` meint weiter "hineingeteilt", ein neues Feld kommt nicht hinzu, und keine Meldung nennt, an wen geteilt wurde.
  - **Owner-bestätigt (13.11.2026, per Abfrage über die Hauptsitzung):** Punkt 5 gilt so: Eine eigene Liste, die nur per öffentlichem Link veröffentlicht ist, gilt als fremdsichtbar; ohne ausdrückliches `list` wird dort nicht geschrieben. Dazu freigegeben für Messung und Live-Test von 32-09 auf nc35 und der 32er Strecke: eine eigene Liste von alice an bob teilen (ro und rw), ein öffentlicher Link auf eine Testliste, ein zusätzliches Testkonto, je mit Rückbau, BASELINE vorher gleich nachher und geleertem Papierkorb (`FREIGABE zustand-32-09=ja inkl-oeffentlicher-link datum=2026-11-13`).

### Nachtrag 32-10 (Owner, 13.11.2026, übermittelt durch die Hauptsitzung)
Anlass: 32-VERIFICATION.md (Re-Verifikation e05c57c), Human Verification 1 und 2 sowie die Info zum Messkommentar in `scripts/check_tool_budget.py`. Owner-Vorgabe wörtlich: "Prio ist das beste Tool für die User und testen ist ein Muss". Umgesetzt in 32-10 (gap closure).
- **Freigabe für 32-10** auf nc35 und der 32er Strecke: eine Testgruppe, bob als Mitglied, Listen, die an diese Gruppe geteilt werden, jeweils mit Rückbau; die Gruppe wird danach gelöscht; die BASELINE ist vorher und nachher gleich, der Papierkorb wird geleert (`FREIGABE zustand-32-10=ja testgruppe datum=2026-11-13`). Für Punkt 2 des Auftrags ("eine Liste, die bob an eine Gruppe mit alice geteilt hat") ist auch alice Mitglied der Testgruppe; diese Lesart stammt aus dem Auftrag der Hauptsitzung, nicht wörtlich aus der Owner-Freigabe.
- **D-32-18 gilt auch für Gruppen:** Eine eigene Liste, die an eine Gruppe geteilt ist (nur lesend oder mit Schreibrecht), ist für `tasks_create` ohne ausdrückliches `list` kein Schreibziel, wie eine Freigabe an eine Person oder ein öffentlicher Link.
- **D-32-14, D-32-15, D-32-17, E4 und D-32-16 gelten auch für eine per Gruppe hineingeteilte Liste:** Name, Link und subline nennen den Besitzer nie, `writable` folgt dem Schreibrecht der Freigabe, geschrieben wird nur mit ausdrücklichem `list`, eine `parent`-Aufgabe dort ist keine Nennung.
- Wiederkehrende Aufgabe und Deckel 500 werden live gemessen; das Zeitbudget je Liste wird aus dieser Messung nach der Regel aus 32-02 bestätigt oder angepasst (Claude's Discretion).
- Ein Anzeigename von bob ungleich seiner Kennung wird nur gesetzt, wenn das ohne Eingriff in andere Tests geht, und danach zurückgesetzt; sonst wird die Grenze genannt.

### Suchtreffer
- **D-32-07:** Ein Treffer von `tasks_search` trägt: `task:`-Id, Titel, Status, Fälligkeit, Startdatum, Priorität, Tags, die Liste nach D-32-06, den Elternverweis nach D-32-04 und das Kennzeichen `recurring`. Die Beschreibung kommt nur über `tasks_read`, auch nicht als Anriss. (Owner, 13.11.2026, Auswahl "Mittel: ohne Beschreibung")
- **D-32-08:** Seitengröße 25 Treffer. Weitere Treffer über das Blättern aus TASK-02 (Cursor-Handles, harter Deckel, ehrliche Notiz). (Owner, 13.11.2026, Auswahl "25 je Seite")
- **D-32-09:** Der Statusfilter kennt drei Werte: offen (Standard, ohne erledigte und abgebrochene), erledigt, alle. "Alle" zeigt auch abgebrochene; jeder Treffer trägt seinen Status. Das erweitert den Wortlaut von TASK-02 ("optional alle") um "erledigt". (Owner, 13.11.2026, Auswahl "Offen, erledigt oder alle")

### Tasks-App fehlt oder ist aus
- **D-32-10:** Ohne installierte oder eingeschaltete Tasks-App arbeiten alle drei Werkzeuge normal. `tasks_create` und der Fall "keine Aufgabenliste" (E6) nennen einmal, dass Aufgaben in der Nextcloud-Oberfläche nur mit der Tasks-App sichtbar sind. Lässt sich der Zustand der App nicht verlässlich erkennen, entfällt der Hinweis; geraten wird nicht. (Owner, 13.11.2026, Auswahl "Arbeitet, mit Hinweis")
- **D-32-11:** Testinstanz und CI messen beides: einen Lauf mit installierter Tasks-App (Suchtreffer-Link für TASK-09, Sicht der App auf angelegte Aufgaben) und einen Lauf ohne (Suchen, Lesen, Anlegen gehen; die allgemeine Suche antwortet leer statt falsch, docs/spike-tasks.md 5.4). Die Fassung der Tasks-App wird im Beleg festgehalten. (Owner, 13.11.2026, Auswahl "Beides messen")

### Live-Beweis
- **D-32-12:** Das Bundle wird live auf Nextcloud 35 und 32 belegt, unter AppAPI-Impersonation, wie Phase 31 (D-31-06). (Owner, 13.11.2026, Auswahl "35 und 32, Reparatur als erster Plan")
- **D-32-13:** Der erste Plan der Phase repariert `scripts/bootstrap_exapp.sh` für Nextcloud 32, damit die 32er Messung per Skript wiederholbar ist statt von Hand: Daemon `manual_install` mit Host ohne Port (Zeile 1288 bis 1290) und `occ user:auth-tokens:add` ohne `--name` auf 32 (Zeile 991). Vorher messen, ob AppAPI 34 und 35 dieselbe Form vertragen; kein Verhalten für 34 und 35 ändern, das heute funktioniert. Das ersetzt den am 12.11.2026 vorgemerkten eigenen kleinen Plan. (Owner, 13.11.2026, selbe Auswahl; Befund in 31-01-SUMMARY.md und raw/nc32-strecke.txt ab Zeile 706)

### Bereits entschieden, hier nur zur Erinnerung
- E2: eigenes Bundle `tasks`, zehnte Familie, einzeln abschaltbar über `NC_MCP_DISABLED_TOOLS`.
- E3: `task:`-Id über `fetch` und Provider `tasks` auflösbar, eigener Plan (TASK-09). Der Owner will alles in 0.8.0, kein 0.8.1; TASK-09 wird in dieser Phase gebaut, nicht verschoben.
- E4: Schreibziel ohne `list` nur bei genau einer eigenen Liste, sonst Fehler mit den Listennamen; nie still in geteilte Listen; in einen Deck-Kalender nie.
- E6: keine Aufgabenliste: `tasks_search` leer mit Hinweis, `tasks_create` Fehler mit Ausweg.
- E7: Felder von `tasks_create`: `summary`, `list`, `description`, `due`, `start`, `priority`, `tags`, `timezone`, `parent`.
- E9: Deck-Kalender (`app-generated--`) ausgeschlossen, lesend und schreibend.
- E1: Budget der Werkzeugliste nach der Hausregel neu verankern (Messung plus 15 Prozent, auf 500 gerundet), Decke je Werkzeug 1400 Bytes.
- Wiederkehrende Aufgaben erscheinen als Masteraufgabe mit `recurring: true`, ohne Expansion (TASK-02).
- Linie aus Phase 31, die hier weiter gilt: ablehnen statt still verändern (D-31-08), Meldungen sagen nur, was sicher ist (D-31-09), bei einem Abbruch wird genannt, was schon geschehen ist (D-31-02).

### Claude's Discretion
Der Owner hat am 13.11.2026 mit "Festschreiben" bestätigt, dass kleinere technische Punkte nach den bisherigen Linien entschieden und als Entscheidung der Planung gekennzeichnet werden:
- Feldnamen der Antworten und Parameter (englisch, im Stil der vorhandenen Werkzeuge; der Parameter der Elternaufgabe heißt nicht `uid`, `user` oder `owner`, TASK-05).
- Wortlaut der Hinweise und Fehlermeldungen (englisch, kurz, mit Ausweg).
- Höhe des harten Deckels beim Blättern, Zeitbudget je Liste (Vorschlag des Spikes: 1 s als Untergrenze, docs/spike-tasks.md Abschnitt 6) und Zeitbudget der Kinderabfrage (D-32-03), jeweils aus einer Messung abgeleitet.
- Deckel der Kinderliste in `tasks_read` und die Notiz, wenn er greift.
- Woran der Zustand der Tasks-App erkannt wird (D-32-10); trägt kein Weg verlässlich, entfällt der Hinweis.
- Ob die zwei Läufe aus D-32-11 zwei CI-Beine oder zwei Abschnitte eines Beins sind.
- Kappungslänge der Beschreibung in `tasks_read` (TASK-04 verlangt gekappt, ohne Marker, mit Kürzungsvermerk).
- Zuschnitt der Pläne und Wellen; fest ist nur D-32-13 (Bootstrap zuerst) und TASK-09 als eigener Plan.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Anforderungen und Entscheidungen
- `.planning/ROADMAP.md`, Abschnitt "### Phase 32: Tasks-Bundle suchen, lesen, anlegen": Goal, fünf Erfolgskriterien, Abtrennbarkeit von TASK-09
- `.planning/REQUIREMENTS.md`: TASK-01 bis TASK-09 im Wortlaut, Entscheidungstabelle E1 bis E15, Abschnitt "Offene Fragen für die discuss-phase"
- `.planning/PROJECT.md`: Kernversprechen (der Assistent sieht nie mehr als der Nutzer), Constraints
- `.planning/STATE.md`: Stand nach Phase 31

### Messungen (Phase 30)
- `docs/spike-tasks.md` Abschnitt 5 (Discovery und Objekte, MESS-03): 5.1 frisches Konto ohne Aufgabenliste, 5.2 Sammlungsarten und Schreibrecht vorab, 5.3 Abfrageverhalten auf 32 bis 35, 5.4 Link des Suchproviders `tasks`, 5.5 create-only `PUT` unter Impersonation, 5.6 Objekte der Tasks-App
- `docs/spike-tasks.md` Abschnitt 6 (Kosten der Aufgabensuche, MESS-04) samt "Grenzen der Messung"
- `docs/spike-tasks.md` Abschnitt 7 (Inventar der Gates und Zusagen), Abschnitt 8 (Annahmen A1 bis A21), Abschnitt 9.2 (was Phase 32 übernimmt), Abschnitt 9.4 Punkte 2 und 3 (die zwei offenen Fragen dieser Runde)
- `tests/fixtures/caldav_home_fresh_account.xml`, `tests/fixtures/caldav_home_task_lists.xml`, `tests/fixtures/tasks_app/` samt `PROVENANCE.md`

### Vorbild und Lehren aus Phase 31
- `.planning/phases/31-ordner-anlegen/31-CONTEXT.md`: D-31-02, D-31-06, D-31-08, D-31-09
- `.planning/phases/31-ordner-anlegen/31-VERIFICATION.md` samt Nachtrag: welche Lücken ein Live-Beweis im Testprozess lässt (ganze Kette über die installierte ExApp, W2; Live-Test in keinem CI-Job, W3)
- `.planning/phases/31-ordner-anlegen/31-01-SUMMARY.md` und `.planning/phases/31-ordner-anlegen/raw/nc32-strecke.txt` ab Zeile 706: die zwei Stellen in `scripts/bootstrap_exapp.sh` (D-32-13)
- `.planning/phases/31-ordner-anlegen/31-07-SUMMARY.md` und `scripts/folder_chain_evidence.py`: so lief die ganze Kette auf Nextcloud 35
- `.planning/phases/31-ordner-anlegen/31-06-SUMMARY.md`: neun Punkte für den README-Faktencheck in Phase 34 (beim Nachziehen der READMEs nicht verschlimmern)
- `docs/folder-evidence.md`: Form eines Belegs unter `docs/`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mcp_connector/nextcloud/clients/caldav.py`: `discover_calendars` und die CalDAV-Abfragen des Kalender-Bundles; TASK-01 verlangt, dass dessen Verhalten byte-gleich bleibt (der Terminfilter verlangt heute den resourcetype `calendar` nicht, docs/spike-tasks.md 9.2 letzter Punkt)
- `src/mcp_connector/tools/calendar.py`: Zeitbehandlung der Termine; `_all_day_window` wird für `DUE` ausdrücklich NICHT übernommen (TASK-05)
- `src/mcp_connector/nextcloud/clients/xml.py`, `icalendar` und `recurring-ical-events` aus dem Stack
- `src/mcp_connector/server/__init__.py`: `graceful`, Laden der Registrierungen je Bundle (`_load_registrations`)
- `scripts/tasks_spike.py`: Messprogramm des Spikes (Discovery, Abfragen, Kosten), Vorlage für Mess- und Belegläufe

### Established Patterns
- Je Familie ein Client unter `nextcloud/clients/`, eine Werkzeugdatei unter `tools/`, eine Registrierung `server/reg_<familie>.py`
- Gate-Kette der v1.7: `tests/contract/test_tool_bundles.py` (`BUNDLE_TOOLS`), `tests/contract/test_tool_surface.py` (`CREATE_TOOLS`, Annotationsklassen), `tests/contract/tool_classes.py` (Klassifikations-Freeze), `tests/contract/test_no_destructive_calls.py` (`EXPECTED_PUT_CALLS = 6`, bleibt 6), `src/mcp_connector/audit/allowlist.py`, Kanarie und Live-Paar unter `tests/integration/`, `scripts/acceptance_all_tools.py`, `scripts/check_tool_budget.py` (`BUDGET_BYTES = 18_000`, `MAX_TOOL_BYTES = 1400`; Stand 16222 Bytes bei 24 Werkzeugen)
- Rohprotokolle unter `raw/` des Phasenordners, Beleg unter `docs/` mit stabilen Ankern, jede zitierte Zeile wörtlich im Rohprotokoll
- Drei READMEs und drei CHANGELOGs gleichlaufend; der Tabellen-Test liest nur `README.md`

### Integration Points
- `tools/chatgpt.py` (`fetch`) und `tools/search.py` samt `PROVIDER_KINDS` für TASK-09
- Id-Codec der vorhandenen Familien für die `task:`-Id (Rundlauftest verlangt, TASK-07)
- `.github/workflows/ci.yml`: Jobs unit, exapp, canary-nc35, integration; hier entscheidet sich die Form von D-32-11

</code_context>

<specifics>
## Specific Ideas

- Leitfrage für `tasks_read` mit Kinderliste: "Was ist bei Projekt X noch offen?" soll mit einem Aufruf beantwortbar sein.
- Leitfrage für den Statusfilter "erledigt": "Was habe ich diese Woche geschafft?"
- Der Assistent soll in der Suche dasselbe sehen wie der Nutzer in der Tasks-App (eigene und geteilte Listen), aber keine Namen anderer Personen.
- Der Hinweis zur Tasks-App soll die Frage "Wo ist meine Aufgabe?" verhindern.

</specifics>

<deferred>
## Deferred Ideas

- Aufgabenlisten anlegen: kam beim Fall "keine Aufgabenliste" als naheliegender Ausweg auf, ist aber eine neue Fähigkeit und kein Teil dieser Phase. Der Fehler nennt den Ausweg über die Tasks-App.
- Ganzer Unteraufgaben-Baum in einem Aufruf: vom Owner abgewählt (D-32-02).
- Name der Person, die eine Liste geteilt hat: vom Owner abgewählt (D-32-06).
- Anriss der Beschreibung im Suchtreffer: vom Owner abgewählt (D-32-07).
- Tag-Alias `no-ai` neben `kein-ki`: eigene kleine Phase nach 0.8.0 (Owner, 13.11.2026).
- Live-Test der Werkzeuge in einem CI-Job mit ExApp-Topologie (Lücke W3 aus Phase 31): für die Planung dieser Phase zu prüfen, sonst Phase 34.

</deferred>

---

*Phase: 32-tasks-bundle-suchen-lesen-anlegen*
*Context gathered: 2026-11-13*

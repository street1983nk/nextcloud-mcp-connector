# Phase 32: Tasks-Bundle suchen, lesen, anlegen - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md , this log preserves the alternatives considered.

**Date:** 2026-11-13
**Phase:** 32-tasks-bundle-suchen-lesen-anlegen
**Areas discussed:** Unteraufgaben beim Lesen, Geteilte Listen in der Suche, Umfang eines Suchtreffers, Tasks-App fehlt oder ist aus

Der Owner hat alle vier vorgeschlagenen Bereiche gewählt. Die Fragen je Bereich wurden gebündelt gestellt (zwei bis drei je Bereich), nicht einzeln.

---

## Unteraufgaben beim Lesen

### Was zeigt tasks_read über die Unteraufgaben einer Aufgabe?

| Option | Description | Selected |
|--------|-------------|----------|
| Liste der Unteraufgaben | Je Unteraufgabe Id, Titel und Status; eine zusätzliche Abfrage je Lesen, vorab messen, Zeitbudget, bei Überschreitung Aufgabe ohne Kinderliste mit ehrlichem Hinweis | ja |
| Nur die Anzahl | "hat 4 Unteraufgaben, 2 offen", ohne Aufzählung; dieselbe zusätzliche Abfrage, kleinere Antwort | |
| Nur der Elternverweis | Keine Angabe zu Kindern, keine zusätzliche Abfrage | |

**User's choice:** Liste der Unteraufgaben (empfohlen)

### Wie tief geht die Kinderliste?

| Option | Description | Selected |
|--------|-------------|----------|
| Nur direkte Kinder | Eine Ebene, vorhersehbare Kosten und Antwortgröße | ja |
| Ganzer Baum | Alle Ebenen eingerückt, mehrere Abfragen, lange Antworten | |

**User's choice:** Nur direkte Kinder (empfohlen)

### Wie erscheinen Unteraufgaben in tasks_search?

| Option | Description | Selected |
|--------|-------------|----------|
| Eigene Treffer mit Elternverweis | Jede Unteraufgabe ist ein normaler Treffer und nennt Id und Titel der Elternaufgabe | ja |
| Unter der Elternaufgabe gruppiert | Eingerückt unter dem Elterntreffer, Sortierung und Blättern werden ungenau | |

**User's choice:** Eigene Treffer mit Elternverweis (empfohlen)
**Notes:** Die Kosten der Kinderabfrage bei großen Listen sind nicht gemessen (docs/spike-tasks.md 9.4 Punkt 2); die Messung ist Teil der gewählten Option.

---

## Geteilte Listen in der Suche

### In welchen Listen sucht tasks_search ohne Angabe einer Liste?

| Option | Description | Selected |
|--------|-------------|----------|
| Eigene und geteilte | Wie die Tasks-App; jeder Treffer nennt seine Liste; `list` schränkt ein | ja |
| Nur eigene, geteilte auf Wunsch | Geteilte Listen nur bei ausdrücklicher Anforderung | |

**User's choice:** Eigene und geteilte (empfohlen)

### Was verrät ein Treffer aus einer geteilten Liste über deren Herkunft?

| Option | Description | Selected |
|--------|-------------|----------|
| Listenname, geteilt, beschreibbar | Name der Liste, geteilt ja oder nein, beschreibbar ja oder nein; kein Name der teilenden Person | ja |
| Zusätzlich wer geteilt hat | Dazu der Anzeigename der Person, der die Liste gehört | |
| Nur der Listenname | Kein Kennzeichen für geteilt oder beschreibbar | |

**User's choice:** Listenname, geteilt, beschreibbar (empfohlen)

---

## Umfang eines Suchtreffers

### Welche Felder trägt ein Treffer?

| Option | Description | Selected |
|--------|-------------|----------|
| Mittel: ohne Beschreibung | Id, Titel, Status, Fälligkeit, Startdatum, Priorität, Tags, Liste samt Kennzeichen, Elternverweis, wiederkehrend | ja |
| Knapp | Nur Id, Titel, Status, Fälligkeit, Liste | |
| Ausführlich: mit Anriss | Wie Mittel, dazu rund 100 Zeichen der Beschreibung | |

**User's choice:** Mittel: ohne Beschreibung (empfohlen)

### Wie viele Treffer je Seite?

| Option | Description | Selected |
|--------|-------------|----------|
| 25 je Seite | Normale offene Liste in einem Zug, gut lesbar | ja |
| 50 je Seite | Weniger Blättern, doppelt so große Antworten | |
| 10 je Seite | Sehr kleine Antworten, viele Aufrufe | |

**User's choice:** 25 je Seite (empfohlen)

### Wonach kann der Assistent beim Status filtern?

| Option | Description | Selected |
|--------|-------------|----------|
| Offen, erledigt oder alle | Standard offen; "erledigt" für "Was habe ich geschafft?"; "alle" auch abgebrochene, gekennzeichnet | ja |
| Nur offen oder alle | Wortlaut der Anforderung; nur erledigte müsste der Assistent selbst aussortieren | |

**User's choice:** Offen, erledigt oder alle (empfohlen)
**Notes:** Erweitert den Wortlaut von TASK-02 um den Wert "erledigt".

---

## Tasks-App fehlt oder ist aus

### Wie verhält sich das Bundle ohne installierte oder eingeschaltete Tasks-App?

| Option | Description | Selected |
|--------|-------------|----------|
| Arbeitet, mit Hinweis | Alle Werkzeuge funktionieren; ein Hinweis, dass Aufgaben in der Oberfläche nur mit der Tasks-App sichtbar sind; ohne verlässliche Erkennung entfällt der Hinweis | ja |
| Arbeitet, ohne Hinweis | Kein Wort zur Tasks-App | |
| Verweigert ohne App | Fehler mit Ausweg "Tasks-App installieren" | |

**User's choice:** Arbeitet, mit Hinweis (empfohlen)

### Wie prüfen Testinstanz und CI das Verhalten mit und ohne Tasks-App?

| Option | Description | Selected |
|--------|-------------|----------|
| Beides messen | Ein Lauf mit App (Suchtreffer-Link, Sicht der App), ein Lauf ohne | ja |
| Nur mit Tasks-App | Fall ohne App nur per Unit-Test | |
| Nur ohne Tasks-App | Suchtreffer-Link nur gegen aufgezeichnete Antworten | |

**User's choice:** Beides messen (empfohlen)

### Auf welchen Fassungen wird live belegt, und wohin kommt die Reparatur des Test-Bootstraps für Nextcloud 32?

| Option | Description | Selected |
|--------|-------------|----------|
| 35 und 32, Reparatur als erster Plan | Beide Enden des Store-Fensters; Skript-Reparatur als erster Plan der Phase | ja |
| 35 und 32, Reparatur getrennt davor | Eigener kleiner Plan vor Phase 32, wie am 12.11. vorgemerkt | |
| Nur 35 | Ohne die 32er Strecke | |

**User's choice:** 35 und 32, Reparatur als erster Plan (empfohlen)
**Notes:** Ersetzt den am 12.11.2026 vorgemerkten eigenen kleinen Plan für `scripts/bootstrap_exapp.sh`.

---

## Abschluss

| Option | Description | Selected |
|--------|-------------|----------|
| Festschreiben | Entscheidungen in die Kontextdatei; kleinere technische Punkte entscheidet die Planung nach den bisherigen Linien und kennzeichnet sie | ja |
| Weitere Bereiche besprechen | Zwei bis vier weitere Punkte | |

**User's choice:** Festschreiben (empfohlen)

## Claude's Discretion

Feldnamen, Wortlaut der englischen Hinweise und Fehler, harter Deckel beim Blättern, Zeitbudgets (je Liste, Kinderabfrage), Deckel der Kinderliste, Erkennung des Zustands der Tasks-App, Form der zwei CI-Läufe, Kappungslänge der Beschreibung, Zuschnitt der Pläne.

## Deferred Ideas

- Aufgabenlisten anlegen (neue Fähigkeit, keine Phase zugeordnet)
- Tag-Alias `no-ai` neben `kein-ki` (eigene Phase nach 0.8.0)
- Live-Test der Werkzeuge in einem CI-Job mit ExApp-Topologie (in der Planung prüfen, sonst Phase 34)

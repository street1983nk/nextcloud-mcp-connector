# Phase 31: Ordner anlegen - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md, this log preserves the alternatives considered.

**Date:** 2026-11-12
**Phase:** 31-Ordner anlegen
**Areas discussed:** Deckel überschritten, Antwortinhalt, Rechte vorab prüfen, Umfang Live-Beweis

Ablauf: Die vier Bereiche wurden dem Owner in einer Mehrfachauswahl vorgelegt, er wählte alle vier. Danach je Bereich eine Frage mit Empfehlung, alle vier in einem Dialog. Der Owner wählte in jedem Bereich die empfohlene Option. Keine Freitext-Anmerkungen.

---

## Deckel überschritten

Frage: Ein Aufruf von files_create_folder mit parents=true bräuchte mehr als 10 neue Ordner. Was soll passieren?

| Option | Description | Selected |
|--------|-------------|----------|
| Vorab ablehnen (empfohlen) | Das Werkzeug zählt vorher die fehlenden Segmente und legt bei mehr als 10 gar nichts an. Die Meldung nennt die Zahl und den Deckel. Es bleiben keine halben Ketten stehen. | ja |
| 10 anlegen, dann stoppen | Die ersten 10 Ordner entstehen, dann bricht das Werkzeug ab und nennt das Angelegte. Spart die Vorprüfung, hinterlässt aber eine unfertige Kette. | |

**User's choice:** Vorab ablehnen
**Notes:** keine

---

## Antwortinhalt

Frage: Was soll files_create_folder bei Erfolg zurückmelden?

| Option | Description | Selected |
|--------|-------------|----------|
| Pfad, created, Datei-Id (empfohlen) | Wie files_upload: zusätzlich die Datei-Id des Zielordners. Bei parents=true dazu die Liste der neu angelegten Pfade. Bei einem schon vorhandenen Ordner kostet die Id eine Abfrage, die für die Ordner-oder-Datei-Prüfung ohnehin nötig ist. | ja |
| Nur Pfad und created | Kleinste Antwort, kleinster Beitrag zum Größenbudget der Werkzeugliste. Wer die Id braucht, muss den Ordner danach suchen. | |

**User's choice:** Pfad, created, Datei-Id
**Notes:** keine

---

## Rechte vorab prüfen

Frage: Soll files_create_folder das Schreibrecht prüfen, bevor es eine Kette von Ordnern anlegt?

| Option | Description | Selected |
|--------|-------------|----------|
| Nur Ablehnung auswerten (empfohlen) | Kein zusätzlicher Aufruf. Lehnt der Server mit 403 ab, sagt die Meldung "keine Rechte" und nennt, was schon angelegt wurde. | ja |
| Vorab prüfen | Eine Abfrage der Rechte am tiefsten vorhandenen Elternordner vor dem ersten Anlegen. Klarere Meldung ohne Schreibversuch, kostet einen Aufruf mehr und einen weiteren Zweig. | |

**User's choice:** Nur Ablehnung auswerten
**Notes:** keine

---

## Umfang Live-Beweis

Frage: Wie breit soll der Live-Beweis für files_create_folder sein? Gemessen ist bisher nur Nextcloud 35 mit SQLite.

| Option | Description | Selected |
|--------|-------------|----------|
| 32 und 35, ACL aus Phase 30 (empfohlen) | Das Werkzeug läuft live auf dem ältesten und dem neuesten Stand des Store-Fensters. Für den Gruppenordner mit ACL gilt die Rohantwort aus Phase 30. | ja |
| Nur 35 | Schnellster Weg, aber kein Beleg für das untere Ende des Store-Fensters. | |
| 32 und 35, ACL live erneut | Zusätzlich wird der Gruppenordner mit ACL über das Werkzeug selbst nachgefahren. | |

**User's choice:** 32 und 35, ACL aus Phase 30
**Notes:** keine

---

## Claude's Discretion

- Weg, die fehlenden Segmente vor dem ersten MKCOL zu zählen
- Wortlaut der Meldungen je Statuszweig
- Feldname für die Liste der neu angelegten Pfade
- Aufteilung in Pläne und Wellen

## Deferred Ideas

- Unteraufgaben beim Wiederöffnen einer Elternaufgabe (Phase 33)
- Umfang des Admin-Schalters aus E15 (Phase 33)
- Mindestfrist des Papierkorbs für TMOD-07 (Phase 33)

# Phase 33: Aufgaben ändern - Discussion Log

> Nur zur Nachvollziehbarkeit. Planung und Ausführung lesen 33-CONTEXT.md.

**Datum:** 2026-11-13
**Bereiche:** Schalter, ETag, Wiederöffnen, Leeren und Name, Teilfehler, Obergrenze

| Frage | Optionen | Owner-Wahl |
|-------|----------|------------|
| Umfang des Admin-Schalters (Hinweis: Auslöser S1 Löschen entfallen) | Alle drei / Abhaken frei, Rest hinter Schalter / Zwei Schalter | Alle drei (Empfehlung) |
| Herkunft der ETag | Aus tasks_read / Im selben Aufruf lesen / Optional | Aus tasks_read (Empfehlung) |
| Wiederöffnen einer Elternaufgabe | Kinder bleiben erledigt / Kinder auch öffnen / Wie die Tasks-App | Kinder bleiben erledigt (Empfehlung), vorher Messung, bei Abweichung der App Owner fragen |
| Felder leeren und Name | Leeren ja, tasks_complete / Leeren ja, tasks_set_status / Kein Leeren | Leeren ja, tasks_complete (Empfehlung) |
| Teilfehler in Ketten mit Unteraufgaben | Kinder zuerst, Stopp, ehrlich melden / Vorher alles prüfen / Mit Unteraufgaben ablehnen | Kinder zuerst, Stopp, ehrlich melden (Empfehlung) |
| Obergrenze Nachfahren | Ja, 50 / Keine Grenze | Ja, 50 (Empfehlung), Wert durch Messung bestätigen |

Claude-Ermessen: Antwortform, Reihenfolge der Nachfahren, Schnitt der Aufrufstellen. Vorprüfung vor dem ersten Schreibzugriff (D-33-11) aus Owner-Wahl 1 abgeleitet, als Ergänzung zu "Kinder zuerst".

Zurückgestellt: keine neuen Ideen.

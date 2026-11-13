[English](hardening.md) | Deutsch | [Français](hardening.fr.md)

# Den Connector auf vertraulichen Daten betreiben

Jede Grenze, die dieser Server bietet, auf einer Seite, in der Reihenfolge,
in der ein Administrator sie ziehen sollte. Jeder Abschnitt nennt den
Mechanismus, wogegen er schützt, und, wo es darauf ankommt, wogegen er
**nicht** schützt. Die ausführlichen Dokumente sind am Ende der Abschnitte
verlinkt.

## 1. Die Grenze, die zählt: die Nextcloud-Berechtigungen

Jede Anfrage läuft mit den Rechten des angemeldeten Nutzers gegen die eigenen
APIs von Nextcloud; der Assistent kann nie mehr sehen als die Person, die ihn
verbunden hat. Es gibt in diesem Server kein zweites Rechtemodell, das driften
könnte. Das ist die tragende Wand: alles Weitere verengt die Fläche, aber
nichts Weiteres ersetzt sie.

Praktische Folge: für eine Automation (n8n und Ähnliches) ein Konto
verbinden, das nur die Rechte des Auftrags trägt, kein persönliches Konto und
nie ein Admin-Konto.

## 2. Ausschließen, was der Assistent nie sehen darf: der kein-ki-Tag

Ein Ordner oder eine Datei mit dem kollaborativen Tag `kein-ki` verschwindet
für den Assistenten samt allem darunter, in jedem Werkzeug, jeder Suche und
jedem Kontextbündel.

- Die Einrichtung prüfen, bevor man ihr vertraut:
  `php occ mcp_connector:exclusion:check --admin=<uid>`
- Die wichtigste Grenze: ein Tag **oberhalb der Wurzel einer Freigabe**
  schützt den freigegebenen Ordner beim Empfänger nicht. Den Ordner taggen,
  der geteilt wird.
- Alle Grenzen, mit den Befunden dahinter: [exclusion.de.md](exclusion.de.md).

## 3. Die Dateifläche verengen: NC_MCP_FILES_ROOT

Mit `NC_MCP_FILES_ROOT=/Dokumente/KI` wird dieses Verzeichnis zur Wurzel der
Dateiwerkzeuge, und kein Dateiwerkzeug erreicht die Ordner darüber. Sinnvoll,
wenn der Assistent nur einen Arbeitsbereich braucht; alles andere ist über
die Dateiwerkzeuge dann gar nicht mehr erreichbar.

## 4. Den Ausgang schließen: NC_MCP_TALK_SEND

Dieser Server hält private Daten, nimmt fremde Inhalte entgegen und hat genau
einen Ausgang, `talk_send`. Diese drei zusammen sind die Lethal Trifecta, und
eine Zutat zu entfernen ist der stärkste verfügbare Zug: `talk_send`
instanzweit abschalten (Einstellungen, Verwaltung, Sicherheit) schließt den
Ausgang, das Lesen bleibt unberührt. Mail ist absichtlich nur lesbar und
bringt keinen eigenen Ausgang mit.

Wenn der Assistent nicht in Talk schreiben muss: abschalten, und diese ganze
Klasse von Datenabfluss endet an der Instanzgrenze.

## 5. Was das Abschalten von Bündeln NICHT tut

`NC_MCP_DISABLED_TOOLS` versteckt Werkzeuge, damit Clients mit kleinen
Modellen oder harten Werkzeuglimits weniger davon sehen. Es ist **keine
Zugriffskontrolle**: `search`, `fetch` und `prepare_context` erreichen die
Inhalte eines abgeschalteten Bündels weiterhin. Das gilt auch für das Bündel
`tasks`: ist `tasks` abgeschaltet, liest `fetch` weiterhin eine `task:`-ID,
und `search` findet Aufgaben weiterhin über den Suchprovider von Nextcloud.
Die Grenze sind und bleiben die Abschnitte 1, 2 und 3. Das steht auch im
README und wird hier bewusst wiederholt, weil es die verführerischste
Fehllesart der Konfiguration dieses Servers ist.

## 6. Prompt Injection: der ehrliche Rest

Eine Mail oder eine Talk-Nachricht schreibt jemand anderes, ein Dokument
womöglich auch, und ein Sprachmodell trennt Daten nicht zuverlässig von
Anweisungen. Eine vollständige Abwehr ist nicht bekannt. Dieser Server
begrenzt stattdessen den Schaden:

- kein Werkzeug löscht, überschreibt, verschiebt, benennt um oder ändert
  Freigaben oder Rechte; Schreiben ist nur Anlegen, und ein Contract-Test
  fällt beim ersten destruktiven Aufruf durch,
- Inhalte kommen mit ihrer Herkunft als Strukturfeldern zurück, der Client
  kann sehen, woher ein Text stammt,
- der Ausgang lässt sich instanzweit schließen (Abschnitt 4).

Was bleibt, mit jeder Gegenmaßnahme im Einzelnen: [privacy.md](privacy.md)
(englisch). Auf der Client-Seite die Schreibbestätigungen des Assistenten
angeschaltet lassen, wenn der Client sie anbietet.

## 7. Das Audit-Log anschalten

Standardmäßig aus, ein Schalter in den Verwaltungseinstellungen dieser App.
Angeschaltet wird jeder Werkzeugaufruf festgehalten mit Konto, Werkzeug,
Zeit, aufrufender App und Ausgang, nie mit einem Parameterwert oder einem
Teil eines Ergebnisses. Die Einträge sind Hash-verkettet;
`occ mcp_connector:audit:read` liest sie und `occ mcp_connector:audit:verify`
nennt das erste gebrochene Glied, falls manipuliert wurde. Auf vertraulichen
Daten ist das der Unterschied zwischen "wir glauben, es war nichts" und "wir
können zeigen, was war".

## 8. Lokal heißt nicht, dass das Modell lokal ist

Dieser Server indexiert, puffert und kopiert nichts, und kein Inhalt verlässt
die eigenen Maschinen, **außer** zu dem Assistenten, der gefragt hat. Ein
Cloud-Assistent erhält die Auszüge, die seine Werkzeuge holen. Wenn das für
die eigenen Daten nicht tragbar ist, gehört ein lokales Modell dazu; der
Connector kann ein entferntes Modell nicht lokal machen.

## 9. Vor dem Produktivbetrieb: selbst einbrechen

Diese Proben einmal durchspielen, als zweiter Nutzer und als der verbundene
Nutzer, und die Ergebnisse zu den Betriebsnotizen legen:

1. `php occ mcp_connector:exclusion:check --admin=<uid>` meldet keinen Befund.
2. Eine mit `kein-ki` getaggte Datei ist über `files_search`,
   `unified_search`, `search`, `fetch` und `prepare_context` nicht erreichbar.
3. Eine Datei, die aus einem Ordner **in** das Konto geteilt wurde, dessen
   Tag oberhalb der Freigabewurzel sitzt: bestätigen, dass sie erreichbar
   ist, und dann den geteilten Ordner selbst taggen, wenn sie es nicht sein
   darf (Abschnitt 2).
4. Eine Datei, die der verbundene Nutzer in Nextcloud nicht lesen darf, ist
   über kein Werkzeug erreichbar.
5. Mit abgeschaltetem `NC_MCP_TALK_SEND` verweigert `talk_send` instanzweit.

Der Freigabefall aus Abschnitt 2 ist der, den echte Installationen falsch
machen; mit der eigenen Ordnerstruktur testen, nicht nur auf dem Papier.

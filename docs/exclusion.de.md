# Ordner vom Assistenten fernhalten: das Tag kein-ki

**Sprachen:** [English](exclusion.md) | Deutsch | [Français](exclusion.fr.md)

Ein Ordner oder eine Datei mit dem kollaborativen Tag `kein-ki` ist für den Assistenten
unsichtbar, und alles darunter ebenso. Der Vergleich ignoriert Groß/Klein und umgebende
Leerzeichen, `Kein-KI` zählt also auch, eine andere Schreibweise wie `Kein KI` oder `keinki`
dagegen nicht. Das Tag ist die Liste: Es gibt keine zweite Ordnerliste in den Einstellungen und
keinen Admin-Schalter, der den Filter abschaltet; gibt es kein `kein-ki`-Tag, wird nichts
gefiltert ([26-CONTEXT.md, D-26-01 und D-26-02](../.planning/phases/26-guard-kern/26-CONTEXT.md)).

Diese Seite beschreibt die zwei Betriebsarten, die Einrichtung mit occ, das Prüfkommando und
jede gemessene oder entschiedene Grenze. Jeder Befehl unten lief am 2026-10-01 gegen
Nextcloud 35.0.0 und steht mit seiner Ausgabe im Rohbeleg
([raw/29-01-messungen.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt),
[raw/29-06-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt),
[raw/29-REVIEW-FIX-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live-beweis.txt), Wiederholungslauf mit dem aktuellen Code).

<a id="operating-modes"></a>
## Betriebsarten

| | Selbstbedienung (kollaborativ) | Organisationsmodus (eingeschränktes Tag per Gruppen-Delegation) |
|---|---|---|
| Zugriffsstufe des Tags | `public` | `restricted` |
| Wer `kein-ki` setzen und entfernen darf | jeder Nutzer, der die Datei sieht | Administratoren und Mitglieder der delegierten Gruppen |
| Gemessen auf Nextcloud 35 | ein normales Konto sieht das Tag und darf es zuweisen (M1b) | ein Mitglied von `ki-verantwortung` weist zu (201), ein Nichtmitglied bekommt 403 (M8) |

Umbenennen oder Löschen eines Tags per WebDAV ist in beiden Betriebsarten Administratoren
vorbehalten (Nextcloud-Quelltext, `SystemTagNode`,
[29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).

**Selbstbedienung** passt zu Teams, in denen jede Person über ihre eigenen Ordner entscheidet.
Wer eine Datei sieht, kann das Tag auch wieder entfernen; das folgt aus dem Nextcloud-Quelltext
(`canUserAssignTag`, [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md))
und wurde nicht eigens gemessen.

**Organisationsmodus** passt zu einer Organisation, in der eine benannte Gruppe entscheidet, was
vom Assistenten fernbleibt. In dieser Betriebsart zusätzlich `restrict_creation_to_admin`
setzen: Ohne den Schalter darf jedes Konto neue Tags anlegen, also auch Doppelgänger wie
`Kein KI`, die der Connector nicht beachtet. Gemessen: Ohne den Schalter legte ein normales
Konto ein Tag an (201), mit dem Schalter bekam dasselbe Konto 403 (M8).

Nextcloud lehnt ein neues Tag ab, das sich nur in Groß/Klein von einem bestehenden unterscheidet
(`Tag KEIN-KI-M6 already exists`, Exit 2, M6). Andere Schreibweisen nimmt Nextcloud an:
`Kein KI`, `keinki` und `kein` plus Halbgeviertstrich plus `ki` ließen sich neben `kein-ki` als
eigene Tags anlegen und wurden unverändert gespeichert (M6). Das Prüfkommando unten findet sie.

<a id="setup-self-service"></a>
## Einrichtung: Selbstbedienung

1. Das Tag als `public` anlegen:

   ```
   php occ tag:add kein-ki public --output=json
   ```

   Gemessene Ausgabe (M7): `{"id":"200","name":"kein-ki","access":"public"}`

2. Einen Ordner taggen. Nutzer tun das in der Weboberfläche (Datei-Details, Tags). Eine
   Administration kann es mit occ tun; der Pfad lautet `<nutzer>/files/<ordner>` ohne
   führenden Schrägstrich, gemessen mit dem Ordner `KI-frei` des Kontos `alice`:

   ```
   php occ tag:files:add alice/files/KI-frei kein-ki public
   ```

   Gemessene Ausgabe (M7): `public tag named kein-ki added.`

   Die Zugriffsstufe in diesem Befehl muss zur Stufe des bestehenden Tags passen; mit einer
   anderen Stufe findet Nextcloud das Tag nicht und der Befehl scheitert (Falle P7 in
   [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).

3. Das Ergebnis mit dem Prüfkommando kontrollieren (siehe [unten](#check-command)).

<a id="setup-organisation"></a>
## Einrichtung: Organisationsmodus

1. Die entscheidende Gruppe anlegen und ihre Mitglieder aufnehmen:

   ```
   php occ group:add ki-verantwortung
   php occ group:adduser ki-verantwortung alice
   ```

   Gemessene Ausgabe (M8): `Created group "ki-verantwortung"` und `user alice added`

2. Das Tag als `restricted` anlegen:

   ```
   php occ tag:add kein-ki restricted --output=json
   ```

   Gemessene Ausgabe (M8): `{"id":"201","name":"kein-ki","access":"restricted"}`. Die `id` ist
   die `<tag-id>` des nächsten Schritts.

3. Das Tag an die Gruppe delegieren. Für die Gruppen-Delegation von Tags hat Nextcloud kein
   occ-Kommando (geprüft gegen Nextcloud 35). Es gibt zwei Wege:

   - **Weboberfläche:** Das Formular der App systemtags liegt unter
     *Administrationseinstellungen > Grundeinstellungen > Kollaborative Schlagworte*
     (Menüpfad aus den Übersetzungsdateien von Nextcloud 35, M9).
   - **WebDAV als Administrator**, die Eigenschaft `oc:groups` per PROPPATCH gesetzt
     (gemessen 207, M8):

     ```
     curl -u admin:<app-password> -X PROPPATCH "https://cloud.example.com/remote.php/dav/systemtags/<tag-id>" -H "Content-Type: application/xml" --data '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:set><d:prop><oc:groups>ki-verantwortung</oc:groups></d:prop></d:set></d:propertyupdate>'
     ```

     Mehrere Gruppen werden mit `|` getrennt (Nextcloud-Quelltext, `SystemTagPlugin`,
     [29-RESEARCH.md](../.planning/phases/29-pr-fkommando-und-doku/29-RESEARCH.md)).
     Alternativ die Schritte 2 und 3 in einer Anfrage per POST (gemessen 201, M8):

     ```
     curl -u admin:<app-password> -X POST "https://cloud.example.com/remote.php/dav/systemtags/" -H "Content-Type: application/json" -d '{"name":"kein-ki","userVisible":true,"userAssignable":false,"groups":"ki-verantwortung"}'
     ```

4. Das Anlegen von Tags auf Administratoren beschränken:

   ```
   php occ config:app:set systemtags restrict_creation_to_admin --value=true --type=boolean
   php occ config:app:get systemtags restrict_creation_to_admin
   ```

   Gemessene Ausgabe (M8): `Config value 'restrict_creation_to_admin' for app 'systemtags' is now
   set to '1', stored as boolean in fast cache`, danach `1`.

5. Das Ergebnis mit dem Prüfkommando kontrollieren.

<a id="check-command"></a>
## Das Prüfkommando

```
php occ mcp_connector:exclusion:check --admin=<uid>
php occ mcp_connector:exclusion:check --admin=<uid> --json
```

Das Kommando läuft ohne Nutzersitzung, liest nur und ändert nichts: Im Live-Beweis waren die
Tabellen `systemtag`, `systemtag_object_mapping`, `systemtag_group` und die Konfiguration der
App `systemtags` vor und nach jedem der 20 Aufrufe gleich
([raw/29-06-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt)).
Ohne `--admin` liest es als echte Konten der Instanz, deshalb verglich der Wiederholungslauf vom
2026-10-01 auch die Kontotabellen `preferences`, `storages`, `mounts` und `filecache`: gleich vor
und nach jedem der 20 Aufrufe, und gleich um einen Lauf, dessen erstes lesendes Konto frisch
angelegt und nie angemeldet war
([raw/29-REVIEW-FIX-live-beweis.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live-beweis.txt),
[raw/29-REVIEW-FIX-live.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-REVIEW-FIX-live.txt), WR-04).
Die Ausgabe nennt Anzahlen, Tag-Namen und Delegationsgruppen, nie eine Datei, einen Pfad oder
ein Konto.

Es prüft sieben Schritte in dieser Reihenfolge:

1. `admin_identity`: Das mit `--admin` genannte Konto ist Administrator (`not_checked` mit
   `admin_unconfirmed`, wenn es sich nicht bestätigen ließ, etwa bei einer vertippten uid).
2. `tag_listing_readable`: Die Tag-Liste der Instanz ist lesbar.
3. `tag_exists`: Ein Tag namens genau `kein-ki` existiert (Groß/Klein egal, wie der Connector
   filtert).
4. `tag_visible`: Dieses Tag ist für Nutzer sichtbar.
5. `no_variants`: Keine andere Schreibweise (`Kein KI`, `keinki`, Striche, Unterstriche) ist in
   Gebrauch.
6. `operating_mode`: Selbstbedienung oder Organisationsmodus, mit den delegierten Gruppen.
7. `assignment_count`: Wie viele Objekte das Tag tragen.

**Urteil.** Gar kein `kein-ki`-Tag ist ein Hinweis, kein Fehler: `passed` bleibt true, und die
Ausgabe sagt, wie man es anlegt. Ein unsichtbares `kein-ki`-Tag oder nur eine andere
Schreibweise ohne das exakte Tag ist nicht bestanden (`passed` false). Das exakte Tag neben
einer anderen Schreibweise ist bestanden, mit einer Warnung, die die Objekte unter der anderen
Schreibweise als nicht ausgeschlossen nennt.

**Exit-Code.** Über AppAPI ist der Exit-Code des Kommandos immer 0, gleich wie das Urteil
ausfällt. Ein Skript oder Monitoring liest den Schlüssel `passed` der `--json`-Antwort, nie den
Exit-Code.

**Ohne `--admin`.** Das Kommando liest dann als das erste Konto der Nutzerliste der Instanz
(sortiert), auf vielen Instanzen ein Administrator, und wertet nur sichtbare Tags aus. Unsichtbare Tags und Delegationsgruppen kann es so nicht prüfen, und die Ausgabe sagt das.
Für die vollständige Prüfung mit `--admin=<uid>` aufrufen.

**Anzahlen.** Die Zahl zählt Zuordnungen über die ganze Instanz, auch von Dateien im
Papierkorb; auf Nextcloud 35 blieb sie sogar nach `occ trashbin:cleanup` stehen (gemessen 2
vorher, 2 im Papierkorb, 2 danach, M4 in
[raw/29-01-messungen.txt](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt)).
Sie ist also nicht die Zahl der Dateien, die ein Nutzer erreichen kann.

Das Kommando antwortet auf Englisch; die Zeile "See docs/exclusion.md" verweist auf die
englische Seite.

Gemessene Ausgabe, Selbstbedienung (Live-Beweis, Fall B):

```
$ php occ mcp_connector:exclusion:check --admin=<uid>
  checked the kein-ki exclusion tag of this instance, read only
  passed       the named account is an administrator
  passed       the tag listing of this instance can be read
  passed       a tag named exactly kein-ki exists
  passed       the kein-ki tag is visible to users
  passed       no other spelling of kein-ki is in use
  passed       the operating mode of the kein-ki tag
  passed       the items carrying kein-ki can be counted
  Self service: every user who can see a file can set and remove kein-ki on it.
  Items carrying kein-ki (assignments across the instance, trash bin included): 1
  A green result does not cover shares: a tag above the root of a share does not protect it for the recipient. See docs/exclusion.md.
```

Gemessene Ausgabe, exaktes Tag neben einer anderen Schreibweise (Live-Beweis, Fall F):

```
$ php occ mcp_connector:exclusion:check --admin=<uid>
  checked the kein-ki exclusion tag of this instance, read only
  passed       the named account is an administrator
  passed       the tag listing of this instance can be read
  passed       a tag named exactly kein-ki exists
  passed       the kein-ki tag is visible to users
  note         no other spelling of kein-ki is in use (variant_beside_exact)
  passed       the operating mode of the kein-ki tag
  passed       the items carrying kein-ki can be counted
  Self service: every user who can see a file can set and remove kein-ki on it.
  Items carrying kein-ki (assignments across the instance, trash bin included): 1
  Items tagged 'keinki' are NOT excluded: 1
  A green result does not cover shares: a tag above the root of a share does not protect it for the recipient. See docs/exclusion.md.
```

Derselbe Beweis deckt kein Tag, Organisationsmodus, ein unsichtbares Tag, nur eine andere
Schreibweise und ein mit `--admin` genanntes Nicht-Admin-Konto ab; die JSON-Form von Fall B
lautet `{"checked":true,"passed":true,"mode":"self_service","assigned":1,"unprotected":0,...}`.

## Grenzen

Ein grünes Prüfergebnis heißt, dass das Tag richtig eingerichtet ist. Es heißt nicht, dass nie
etwas Getaggtes durchscheinen kann. Das sind die Grenzen, je ein Satz, mit dem Befund, auf dem
sie beruhen.

<a id="limit-share-boundary"></a>
### Freigabe-Grenze

Ein Tag auf einem Ordner oberhalb der Wurzel einer Freigabe ist für den Empfänger unsichtbar,
der geteilte Ordner erscheint in dessen Sitzungen also ungeschützt; ein Tag auf dem geteilten
Ordner selbst wirkt, also den Knoten taggen, den man teilt.
Quelle: [25-MESSBERICHT.md, K5, Freigabe-Grenze](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="limit-invisible-tag"></a>
### Ein unsichtbares Tag wirkt nicht

Für ein Konto, das kein Administrator ist, existiert ein unsichtbares Tag nicht (die
Tag-Abfrage antwortet 412, die Liste lässt es weg), es filtert also nur in Sitzungen von
Administratoren; das Prüfkommando meldet es als nicht bestanden.
Quelle: [25-MESSBERICHT.md, K5, unsichtbares Tag](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md);
der Administrator sieht es: [raw/29-01-messungen.txt, M2](../.planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt).

<a id="limit-app-disabled"></a>
### App systemtags ausgeschaltet

Nach `occ app:disable systemtags` antwortet die Tag-Abfrage auf Nextcloud 32 bis 35 weiter mit
Treffern, der Connector filtert also weiter; weg sind der Suchprovider von systemtags, die
Capability (auf 32 bis 34 mit APCu erst nach einem Neustart des Webservers) und die
occ-Kommandos `tag:files:*`.
Quelle: [25-MESSBERICHT.md, K1](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="limit-timing"></a>
### Antwortzeit

Ein getaggtes Objekt kostet eine Tag-Abfrage mehr als ein fehlendes, die Antwortzeit kann die
beiden also unterscheiden; der Connector fügt keine künstliche Verzögerung ein (eine
bekannte, bewusst hingenommene Grenze).
Quelle: [28-CONTEXT.md, D-28-12](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-06](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-search-outage"></a>
### search im Ausfall

Ist die Ausschlussprüfung nicht beantwortbar, liefert das ChatGPT-Werkzeug `search` weniger
Treffer, ohne das zu melden; nichts Getaggtes kommt durch.
Quelle: [28-CONTEXT.md, D-28-13](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-08](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-notes-create"></a>
### notes_create

`notes_create` legt eine nicht existente Kategorie an und weist eine getaggte ab, die Abweisung
zeigt also, dass ein getaggter Ordner dieses Namens existiert (bewusst hingenommen, von einem
Test festgehalten).
Quelle: [28-CONTEXT.md, D-28-16](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-07](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-third-party-providers"></a>
### Suchprovider von Drittanbieter-Apps

Ein Suchprovider, der Dateien ohne fileId, Pfad oder `/f/<id>`-Link nennt, wird nicht geprüft
und kommt durch die Unified Search (zur Laufzeit lässt der Connector ihn im Zweifel durch, bewusst so entschieden); das Gate in der CI
sieht nur die Provider der CI-Instanz.
Quelle: [28-REVIEW.md, WR-02 und Owner decisions](../.planning/phases/28-gates-und-beweise/28-REVIEW.md).

<a id="limit-tables-free-text"></a>
### Tables-Freitext mit `/f/<id>`

Tables-Zellen mit Freitext, der eine `/f/<id>`-Adresse enthält, bleiben unberührt; nur
Link-Objekte werden geprüft.
Quelle: [28-REVIEW.md, WR-03](../.planning/phases/28-gates-und-beweise/28-REVIEW.md),
[28-CONTEXT.md, D-28-18](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md),
[28-SECURITY.md, A-28-03](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="limit-talk-file-room"></a>
### Talk-Datei-Räume bei ausfallender Pfadsuche

Fällt die Pfadsuche aus, während ein Ordner getaggt ist, antwortet Talk für einen Datei-Raum
anders als für ein erfundenes Token, ein Aufrufer kann also erkennen, dass ein Token zu einem
Datei-Raum gehört, auch bei einer getaggten Datei.
Quelle: [28-REVIEW.md, IN-02](../.planning/phases/28-gates-und-beweise/28-REVIEW.md).

## Weitere technische Grenzen

<a id="tech-sqlite"></a>
### SQLite mit vielen Tag-Zuordnungen

Gemessen: Auf SQLite brauchte eine Tag-Abfrage mit einem einzigen Treffer bei 140.005
Zuordnungen rund 240 s (240.298 ms, Nextcloud 35.0.0, gemessen 2026-09-26; PostgreSQL: Median
62 ms bei 110.005). Der Connector wartet höchstens 15 s auf eine Tag-Abfrage (`TAG_BUDGET` in
[exclusion.py](../src/mcp_connector/nextcloud/exclusion.py)), die Prüfung endet dort also als nicht beantwortbar, und
dateitragende Einträge werden zurückgehalten (fail-closed).
Quelle: [25-MESSBERICHT.md, G2 und Owner-Entscheid E3](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

<a id="tech-upload-oracle"></a>
### Upload neben einer getaggten Datei

Ein Upload an ein getaggtes Ziel bekommt die Abweisung eines fehlenden Elternordners; bei einer
getaggten Datei unter einem sichtbaren Elternordner zeigt diese Abweisung trotzdem, dass dort
etwas besonders ist, was sich ohne Schreiben nicht vermeiden lässt.
Quelle: [27-SECURITY.md, A-27-03](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-SECURITY.md).

<a id="tech-folder-oracle"></a>
### Ordner neben einem getaggten Ordner

Das Anlegen eines Ordners in einem getaggten Ordner oder darunter bekommt die Abweisung eines
fehlenden Elternordners; neben einem sichtbaren Elternordner zeigt diese Abweisung trotzdem,
dass dort etwas besonders ist, was sich ohne Schreiben nicht vermeiden lässt.
Quelle: [folder-evidence.md, Folder next to a tagged folder](folder-evidence.md#folder-next-to-a-tagged-folder).

<a id="tech-tables-talk-sandbox"></a>
### Tables und Talk ohne Sandbox

Tables und Talk bekommen nur die Tag-Prüfung, nicht die Ordner-Sandbox `NC_MCP_FILES_ROOT` der
Datei-Werkzeuge.
Quelle: [28-SECURITY.md, A-28-04](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="tech-foreign-text"></a>
### Dateinamen in Fremdtext

Ein Dateiname, der in eine Nachricht, einen Rich-Text oder eine Deck-Beschreibung getippt wurde,
liegt außerhalb einer Prüfung über fileIds und wird nicht geprüft.
Quelle: [28-SECURITY.md, A-28-03](../.planning/phases/28-gates-und-beweise/28-SECURITY.md).

<a id="tech-upload-staging"></a>
### Staging-Ordner eines Uploads in Teilen

Ein Upload in Teilen, der früh abbricht, lässt seinen Staging-Ordner
`uploads/<user>/nc-mcp-<sha256>` liegen; er verrät nichts und ist ein Aufräumpunkt.
Quelle: [28-CONTEXT.md, D-28-20](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md).

<a id="tech-talk-conversations"></a>
### Treffer von talk-conversations

Treffer des Suchproviders `talk-conversations` folgen zwei Regeln: Ein Treffer, dessen Token
nicht in der Gesprächsliste steht, wird zurückgehalten, sobald irgendetwas getaggt ist, und ist
die Liste nicht lesbar, werden alle zurückgehalten, mit einem degraded-Eintrag unter dem Namen
des Providers.
Quelle: [28-CONTEXT.md, D-28-21](../.planning/phases/28-gates-und-beweise/28-CONTEXT.md).

<a id="tech-one-wording"></a>
### Ein Wortlaut, wenn die Prüfung nicht beantwortbar ist

Jedes Werkzeug sagt dasselbe, wenn die Prüfung nicht beantwortbar ist: "The exclusion check
(tag kein-ki) could not be answered, so entries that may carry file content are withheld."
Quelle: [27-CONTEXT.md, D-27-05](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-CONTEXT.md).

<a id="tech-mariadb"></a>
### MySQL und MariaDB nicht gemessen

Die Befunde zu Schreibweisen und alle Zeiten gelten für SQLite und PostgreSQL; MySQL und
MariaDB wurden nicht gemessen.
Quelle: [25-MESSBERICHT.md, Grenzen der Messung](../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md).

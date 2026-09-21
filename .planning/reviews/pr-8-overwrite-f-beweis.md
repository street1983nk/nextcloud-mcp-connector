# PR #8: Live-Beweis Overwrite: F auf dem Chunk-Assembly-MOVE

**Datum:** 21.09.2026, **Instanz:** lokale Teststrecke nc35-nc (Nextcloud 35.0.0.10,
via Caddy auf 127.0.0.1:8082), **Nutzer:** admin, **Werkzeug:** curl direkt gegen
WebDAV, ohne Connector-Code. Anlass: PR #8 (piAreSquare) fuehrt Binaer-Uploads
ueber Nextclouds Chunk-Protokoll ein; das Create-only-Versprechen haengt dort am
finalen MOVE mit `Overwrite: F`. Der PR belegt das nur gegen gemockte Server,
dieser Lauf belegt es am lebenden Objekt.

## Ablauf und Ergebnisse

1. `PUT /files/admin/overwrite-beweis.txt` mit `If-None-Match: *`,
   Inhalt "ORIGINAL-...": **201**.
2. `MKCOL /uploads/admin/nc-mcp-beweis-chunks` mit Destination-Header: **201**;
   `PUT .../00001` (1024 Bytes 'A', OC-Total-Length 1024): **201**.
3. **KERNBEWEIS:** `MOVE .../.file` auf die EXISTIERENDE Datei mit
   `Overwrite: F`: **412 PreconditionFailed**, sabre-Fehlertext "The destination
   node already exists, and the overwrite header is set to false", Header
   `Overwrite` benannt. Dateiinhalt danach unveraendert ("ORIGINAL-...").
4. **Positivkontrolle:** identischer Chunk-Bestand, `MOVE` auf NEUEN Pfad mit
   `Overwrite: F`: **201**, Datei hat 1024 Bytes 'A'.
5. **Gegenprobe (traegt der Header?):** Opferdatei angelegt, zweiter
   Chunk-Bestand, `MOVE` auf die existierende Opferdatei OHNE Overwrite-Header:
   **204**, Datei ERSETZT (RFC-4918-Default ist Overwrite T). Der Header ist
   also die gesamte Schutzwirkung.
6. Aufgeraeumt: drei Testdateien per DELETE (je 204), beide Chunk-Verzeichnisse
   waren durch die MOVEs bereits konsumiert (DELETE je 404).

## Verdikt fuer den PR

- Die Kernannahme des PR haelt auf NC 35: `Overwrite: F` wird auch vom
  Chunk-Assembly-MOVE honoriert (412 + unveraenderte Datei).
- Die Gegenprobe zeigt, warum die Paranoia im PR richtig ist: ein erfolgreicher
  Overwrite antwortet mit genau dem 204, das `finish_chunked_upload` ueber
  `_check_write` als lauten Fehler meldet statt als sicheren Create. Ein Server
  oder Proxy, der den Header verschluckt, wird also erkannt, nicht verschwiegen.
- Offen bleibt der Beweis auf stable33/stable34 (die CI-Matrix des Connectors
  prueft die anderen Zweige); fuer das Review reicht NC 35 als Beleg der
  Semantik, die Matrix-Absicherung kommt mit dem regulaeren Integrationslauf.

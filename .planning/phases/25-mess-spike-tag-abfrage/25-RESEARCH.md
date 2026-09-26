# Phase 25: Mess-Spike Tag-Abfrage - Research

**Researched:** 2026-09-26
**Domain:** Messaufbau gegen echte Nextcloud-Instanzen (Docker/WSL2), WebDAV REPORT `oc:filter-files` mit `oc:systemtag`, AppAPI-Impersonation, synthetische Testdaten
**Confidence:** HIGH für Image-Tags, occ-Kommandos je Version, Topologie und Codepfade (live bzw. per Quelltext je Branch geprüft); MEDIUM für Zeitschätzungen des Datenaufbaus und den PHP-Einmal-Snippet-Weg (nicht ausgeführt, weil Research nichts an nc35 ändern darf)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### NC-Versions-Matrix
- **D-25-01:** NC 32, 33 und 34 werden SEQUENZIELL live gemessen: je eine Wegwerf-Instanz nacheinander (nextcloud-docker-dev), gleiches Messskript je Version. Nie mehr als eine Zusatzinstanz neben der nc35-Strecke (RAM-Merker der Box, 16 GB).
- **D-25-02:** Auf 32-34 laufen NUR die versionsabhaengigen Messungen: App-aus-Verhalten, 412-Verhalten, REPORT-Grundform. Alles andere (Impersonation, Latenz, Notes, Freigabe-Grenze, Varianten, unsichtbares Tag) laeuft ausschliesslich auf der bestehenden nc35-Strecke.

#### Latenz-Messaufbau
- **D-25-03:** Datenbestand synthetisch per Skript: ein Baum mit ~10.000 Dateien, davon 1/100/5000 getaggt; ZUSAETZLICH der Extremfall aus nextcloud/server PR #64298 (10.000 Dateien in EINEM Ordner, dort wurden 6,4 s fuer nc:system-tags gemessen). Testdaten werden nach der Messung entfernt (Muster des Stack-Researchers vom 26.09.).
- **D-25-04:** Harte Schwelle: braucht der REPORT bei 5000 getaggten Knoten laenger als 1 s, stoppt die Ableitung und der Owner entscheidet am Checkpoint (Alternativen waeren Cache-Strategie oder engerer Zielpfad). Unter 1 s gilt das Design "ein REPORT je Antwort" als bestaetigt.

#### Checkpoint-Regime
- **D-25-05:** EIN Owner-Checkpoint, nachdem die kritischen Messungen vorliegen (Notes-Befund, App-aus, Latenz), BEVOR Ableitungen in Phase 26/27 einfliessen. Muster der Checkpoints 22-07/24-09. Der Notes-Befund entscheidet dort ueber EXCL-05 (bauen oder dokumentiert vertagen).

#### Beleg-Ablage
- **D-25-06:** Messbericht und Rohdaten INTERN in .planning/phases/25-mess-spike-tag-abfrage/ (Muster: Messbericht als eigene MD-Datei mit Kommando+Ergebnis je Zeile). Nichts davon nach docs/: was Nutzer betrifft, wandert erst mit Phase 29 kuratiert dorthin.

### Claude's Discretion
- Aufbau- und Aufraeum-Mechanik der Wegwerf-Instanzen (nextcloud-docker-dev vs. offizielle Images), solange sequenziell und rueckstandsfrei.
- Skript-Zuschnitt fuer den Datenbestand und die Zeitmessung (Median aus mehreren Laeufen o.ae.), solange die Zahlen je Messung mit Kommando und Rohwert protokolliert sind.
- Reihenfolge der Messungen innerhalb der Phase, solange die kritischen drei (Notes, App-aus, Latenz) vor dem Checkpoint liegen.

### Deferred Ideas (OUT OF SCOPE)
- Keine neuen. Die vier offenen Designfragen (Ordner-Tag als Ausschlussliste, Admin-Schalter: Phase 26; Upload-Orakel, Zaehlen-vs-Schweigen: Phase 27) stehen bereits an ihren Phasen und werden hier nicht entschieden.
</user_constraints>

<phase_requirements>
## Phase Requirements

Die Phase trägt keine eigenen Requirement-IDs. Sie liefert Messvorbedingungen:

| ID | Description | Research Support |
|----|-------------|------------------|
| EXCL-02 (Vorbedingung) | Ein REPORT je Antwort, Präfixvergleich, nur Name-zu-Id cachebar, 412 löst neu auf | Latenzaufbau (Abschnitt "Pattern 3"), 412-Messung nach Löschen/Neuanlegen, Zielpfad-Messung; Quelllage: REPORT sucht per Tag-NAME (siehe "Quellbefund 1") |
| EXCL-04 (Vorbedingung) | Drei Zustände, Erfolg des REPORT maßgeblich, nicht die Capability | App-aus-Matrix 32/33/34 (+35), 412 bei unsichtbarem Tag, Varianten-Messung |
| EXCL-05 (Messbedingung) | Notiz-Id zu fileid belegt, sonst dokumentiert vertagen | Notes-Messung (Pattern 5); Quelle Notes v6.1.0 `Note::getId()` = `$this->file->getId()` |
</phase_requirements>

## Summary

Die nc35-Strecke läuft (NC 35.0.0, Notes 6.1.0, systemtags aktiv, AppAPI 35.0.0, ExApp 0.2.1 mit `NEXTCLOUD_URL=http://caddy`), ebenso die 34er-HaRP-Strecke (34.0.3) und eine Findling-Instanz. Die Docker-VM hat **7,6 GiB** (nicht 16), aktuell sind rund 1,5 GiB belegt; eine zusätzliche SQLite-Nextcloud kostet im Leerlauf rund 200 MiB. Freie Loopback-Ports: 8080 ist durch den gestoppten `nc-mcp-test` reserviert, **8083** ist frei und kollidiert mit nichts. Für 32/33/34 empfiehlt sich das **offizielle Image mit gepinntem Patch-Tag** nach dem Muster von `compose.test.yml` (kein HaRP, kein AppAPI, SQLite, ein Container) statt nextcloud-docker-dev: docker-dev klont im Standalone-Modus den Server-Quelltext eines Branches zur Laufzeit, misst also keinen Release. Das weicht vom Klammerzusatz in D-25-01 ab, ist aber durch "Claude's Discretion" (Aufbau-Mechanik) gedeckt; der Plan sollte das im Messbericht einen Satz lang begründen.

Die Quellcode-Prüfung dieser Research hat drei Befunde ergeben, die die Messliste schärfen: (1) Der REPORT löst die Tag-Id auf und sucht dann **per Tag-Namen** (`searchBySystemTag($tagName)` → `systemtag.name = ?`), für Nicht-Admins nur über sichtbare Tags. Gleichnamige Varianten (die DB erlaubt dank Unique-Index auf `(name, visibility, editable)` mehrere Tags gleichen Namens) landen also im selben REPORT; ob Groß/Klein-Varianten mitkommen, hängt von der DB-Kollation ab. (2) `tag:files:add/delete/delete-all` gehören zur **App systemtags** (`apps/systemtags/appinfo/info.xml`, 32 bis 34 geprüft) und verschwinden mit `app:disable systemtags`; `tag:add/list/delete/edit` sind Core und bleiben. Also erst taggen, dann abschalten. (3) `ISystemTagObjectMapper::setObjectIdsForTag()` (seit NC 31) setzt die komplette Objektmenge eines Tags in einer Transaktion; damit sind die Stufen 1/100/5000 in Sekunden umschaltbar, statt 5000 occ-Aufrufe à 0,41 s (gemessen) zu zahlen.

AppAPI-Impersonation (Erfolgskriterium 2) wird nach dem etablierten Muster von `tests/integration/test_exapp_dav_matrix.py` gemessen: vom Host über Caddy (`http://127.0.0.1:8082`) mit `Credentials(mode=MODE_APPAPI, secret=APP_SECRET)` aus `.env.nc35`, Gegenprobe mit dem App-Passwort derselben Nutzerin, serverseitiger Beleg über `data/exapp_impersonation.log`. Optional ein zweiter Lauf aus dem ExApp-Container selbst (`/app/.venv/bin/python`, httpx 0.28.1 vorhanden) gegen `http://caddy`, der exakt den Produktionsweg nimmt. Die prepare_context-Referenz existiert bereits als Messdatei: `tests/integration/test_ctx_bundle.py` mit `-s`, per `NC_MCP_E2E_*`-Exports auf nc35 umgelenkt.

**Primary recommendation:** Ein Python-Messskript (Vorlage `scripts/exchange_evidence.py`: `subprocess`-Aufrufe für docker/occ, Blöcke mit `guarded`, Protokollzeilen "Kommando | Rohwert") plus eine Wegwerf-Compose-Datei mit parametrisiertem Image-Tag auf Port 8083; Datenaufbau per Dateisystem + `occ files:scan`, Tagging per PHP-Einmal-Snippet mit `setObjectIdsForTag`, Messung immer als Nicht-Admin alice, Rückbau mit Inventur-Vergleich gegen einen vorher gezogenen Ausgangsstand.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tag-Menge ermitteln (REPORT) | Nextcloud (Sabre `FilesReportPlugin`, DB-Suche) | Messskript (Host) | Server entscheidet Sichtbarkeit und Menge; Skript misst nur |
| Identität (App-Passwort vs. AppAPI) | Nextcloud Auth-Backend (AppAPI) | ExApp-Container / Host-Skript | Impersonation wird in Nextcloud aufgelöst, nicht im Proxy (docs/spike-dav.md) |
| Testdaten erzeugen | Container-Dateisystem + `occ files:scan` | PHP-Snippet (Tag-Zuordnung) | Umgeht 10.000 HTTP-PUTs; Datenschicht ist dieselbe |
| Wanduhr messen | Messskript (Host, `time.perf_counter`) | Caddy-Hop | Produktionsnaher Weg (ExApp spricht über `http://caddy`) |
| Versionsmatrix 32-34 | Wegwerf-Container (offizielles Image) | occ | Nur versionsabhängige Messungen (D-25-02) |
| Beleg-Ablage | `.planning/phases/25-.../` | none | D-25-06 |

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `nextcloud` (Docker Hub, offizielles Image) | `32.0.15-apache`, `33.0.9-apache`, `34.0.4-apache` | Wegwerf-Instanzen der Matrix | Aktuelle Patch-Releases, amd64+arm64 verifiziert [VERIFIED: hub.docker.com API, 26.09.2026] |
| nc35-Strecke (`compose.nc35.yml`) | NC 35.0.0 (`nextcloud:35.0.0-apache-local`), Notes 6.1.0, app_api 35.0.0 | Alle nicht versionsabhängigen Messungen | Läuft seit 30 h healthy [VERIFIED: `occ status`, `occ app:list`] |
| httpx | 0.28.1 (Projekt + ExApp-Container) | REPORT/PROPFIND/Notes-REST | Selbe Aufrufform wie `clients/dav.py` [VERIFIED: uv.lock-Stand im Container] |
| lxml | vorhanden | REPORT-Body bauen | Projektregel "Bodies per lxml, nie f-String" (dav.py `_stat_body`) |
| `mcp_connector.nextcloud.credentials` | Repo | `Credentials(mode=MODE_APPAPI/MODE_BASIC).auth()` | Genau die Naht, die in Produktion impersoniert |

### Supporting
| Tool | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Docker Engine / Compose | 29.5.2 / v5.1.4 | Wegwerf-Instanzen | Immer |
| gh CLI | 2.92.0 | Quelltextprüfungen je Branch | Nur bei Rückfragen |
| uv | 0.11.7 | `uv run --no-sync python scripts/...` | Skriptlauf (Systempython defekt) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Offizielles Image je Patch-Tag | juliusknorr/nextcloud-docker-dev | docker-dev-Standalone (`ghcr.io/nextcloud/nextcloud-dev-php*`) holt Server-Quelltext per Branch zur Laufzeit (kein Release, großer Checkout, langsamer Start) [CITED: github.com/juliusknorr/nextcloud-docker-dev README]; das Repo selbst nutzt bereits das offizielle Image (`compose.test.yml`, `compose.exapp.yml`) |
| Neue Wegwerf-Instanz für 34 | Laufende `nc-mcp-exapp-nc` (34.0.3) | Spart einen Pull, aber `app:disable systemtags` an einer Langzeit-Topologie mit ExApp verletzt "Wegwerf" und riskiert Rückstände; nur als Notfall-Rückfall |
| Tagging per PHP-Snippet | `occ tag:files:add` je Datei | 0,41 s je occ-Aufruf gemessen, 5000 Aufrufe ≈ 35 min |
| Tagging per PHP-Snippet | DAV `PUT systemtags-relations/files/{fileid}/{tagid}` | Offizieller HTTP-Weg, ≈ 0,1 bis 0,25 s je Aufruf sequenziell (≈ 10 bis 20 min für 5000); parallel drohen SQLite-Sperren. Rückfall, falls das Snippet scheitert |
| 10.000 WebDAV-PUTs | Dateien im Container anlegen + `occ files:scan` | PUT-Schleife ≈ 20 bis 40 min; Dateisystem + Scan ≈ 1 bis 3 min [ASSUMED, im ersten Datenblock messen und protokollieren] |

**Installation:** keine neuen Pakete. Images:
```bash
docker pull nextcloud:32.0.15-apache   # je ~500 MB komprimiert, sequenziell direkt vor der Messung
```
Lokal liegen bereits `nextcloud:33.0.7-apache` und `nextcloud:34.0.3-apache`; sie sind nicht die aktuellen Patches. Empfehlung: die aktuellen Patches ziehen (Store-Nutzer laufen auf ihnen), Version of record ist immer `occ status`, nie die Compose-Zeile (Kommentar in `compose.exapp.yml`). Plattenplatz: 58 GB frei auf C:, `docker system df` meldet 27 GB rückforderbar.

**Nebenbefund:** `nextcloud:35.0.1-apache` hat inzwischen ein amd64-Manifest (seit 25.09.2026) [VERIFIED: hub.docker.com]. Der Kommentar in `compose.nc35.yml` ("no matching manifest for linux/amd64") ist damit veraltet. Für diese Phase ohne Belang (35 wird auf der bestehenden 35.0.0 bestätigt), als Backlog-Notiz festhalten.

## Package Legitimacy Audit

Diese Phase installiert keine externen Pakete (pyproject.toml und uv.lock bleiben unverändert). Docker-Images sind offizielle Docker-Hub-Library-Images bzw. bereits lokal vorhanden.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (keine) | | | | | | |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Quellbefunde dieser Research (neu gegenüber STACK/PITFALLS)

### Quellbefund 1: Der REPORT sucht per Tag-NAMEN, Varianten landen gemeinsam darin
`FilesReportPlugin::processFilterRulesForFileNodes` (stable34) löst die Ids per `getTagsByIds($ids, $user)` auf (unsichtbar/unbekannt → `TagNotFoundException` → **412** "Cannot filter by non-existing tag") und ruft dann `$this->userFolder->searchBySystemTag($tagName, $uid, $dbLimit, $dbOffset)`. `Folder::searchBySystemTag` baut `SearchComparison(COMPARE_EQUAL, 'systemtag', $tagName)`, `SearchBuilder` mappt `systemtag` auf `systemtag.name`, `QuerySearchHelper::equipQueryForSystemTags` joint die Mapping-Tabelle und filtert für Nicht-Admins auf `systemtag.visibility = true`. [VERIFIED: gh api nextcloud/server stable34, Dateien `apps/dav/lib/Connector/Sabre/FilesReportPlugin.php`, `lib/private/Files/Node/Folder.php`, `lib/private/Files/Cache/SearchBuilder.php`, `lib/private/Files/Cache/QuerySearchHelper.php`]

Folgen für die Messung:
- Ein REPORT auf die Id eines sichtbaren `kein-ki` liefert **alle** Dateien, die irgendein sichtbares Tag exakt dieses Namens tragen (z. B. `public` und `restricted` gleichnamig), aber nicht die eines gleichnamigen `invisible`-Tags (für Nicht-Admins). Für Admins kommen auch die unsichtbaren mit.
- `createTag` verhindert seit 32 neue Dubletten case-insensitiv (`mb_strtolower`-Vergleich über alle Tags) [VERIFIED: stable32 `SystemTagManager::createTag`]. Die DB selbst erlaubt Dubletten: Unique-Index `tag_ident` auf `(name, visibility, editable)` [VERIFIED: `core/Migrations/Version13000Date20170718121200.php`]. Varianten für die Messung müssen daher **per DB-Insert** angelegt werden (simulierter Altbestand).
- Ob `Kein-KI` zu `kein-ki` passt, entscheidet die Kollation: SQLite-`=` ist binär (case-sensitiv). nc35 läuft auf SQLite (`dbtype: sqlite3`, gemessen). Auf MySQL/MariaDB mit case-insensitiver Kollation könnte es anders ausfallen [ASSUMED]. Der Messbericht muss das als Grenze des Befunds nennen.

### Quellbefund 2: `tag:files:*` verschwindet mit der App
`apps/systemtags/appinfo/info.xml` registriert `OCA\SystemTags\Command\Files\Add|Delete|DeleteAll` (stable32, stable33, stable34 identisch vorhanden) [VERIFIED: gh api]. `tag:add/delete/edit/list` liegen in `core/Command/SystemTag/` [VERIFIED]. `systemtags` ist in `core/shipped.json` auf 32, 33, 34 und 35 nur `defaultEnabled`, nicht `alwaysEnabled`; `dav` ist `alwaysEnabled` [VERIFIED]. Auf nc35 und nc34 live bestätigt: `occ list` zeigt `tag:files:add` usw.

### Quellbefund 3: `setObjectIdsForTag` für schnelle Stufen
`ISystemTagObjectMapper::setObjectIdsForTag(string $tagId, string $objectType, array $objectIds)` `@since 31.0.0`: löscht alle Zuordnungen des Tags und fügt die neue Menge in einer Transaktion ein, Events je entferntem Objekt [VERIFIED: stable32/35 Quelle]. Damit wechselt man 1 → 100 → 5000 mit je einem Aufruf, und `setObjectIdsForTag($id, 'files', [])` räumt auf.

### Quellbefund 4: occ-Kommandos je Version
| Kommando | 32 | 33 | 34 | 35 | Beleg |
|---|---|---|---|---|---|
| `tag:add <name> <public\|restricted\|invisible> --output=json` (liefert `id`) | ja | ja | ja | ja | Quelle `core/Command/SystemTag/Add.php` stable32; live 35 |
| `tag:files:add <target> <tags> <access>` (legt fehlendes Tag an) | ja (nur bei aktiver App) | ja | ja | ja | Quelle je Branch; live 34/35 |
| `files:delete <file> --force` | ja | ja | ja | ja | Quelle je Branch; live 34 |
| `files:delete --skip-trash` | nein | nein | nein | ja | Quelle stable32 (nur `--force`), live 34 ohne, live 35 mit |
| `files:scan --path`, `files:cleanup`, `trashbin:cleanup` | ja | ja | ja | ja | live 35 [VERIFIED], ältere Versionen [ASSUMED, seit Jahren Bestand] |

### Quellbefund 5: Notiz-Id = fileid laut Quelle
Notes v6.1.0 `lib/Service/Note.php`: `getId()` gibt `$this->file->getId()` zurück; `getCategory()` ist der Ordnerpfad relativ zum Notes-Ordner [VERIFIED: gh api nextcloud/notes@v6.1.0]. Die Messung bestätigt das nur noch live (Erfolgskriterium 4 verlangt den Live-Beleg).

### PR #64298: Zahlen im PR-Text haben sich verschoben
Der PR ist weiter **OPEN**. Die aktuelle Beschreibung nennt 6,2 s / ~700 Queries → 2,4 s / ~40 Queries für PROPFIND `oc:fileid` + `nc:system-tags` auf 10k Dateien mit ~385k Tag-Zuordnungen (PITFALLS zitierte 6,4 s / ~2.000 Queries → 2,1 s). [VERIFIED: `gh pr view 64298`, 26.09.2026]. Wichtig: gemessen wurde ein **PROPFIND mit `nc:system-tags`**, nicht der REPORT. Der Extremfall ist also Referenz für den Weg, den das Design nicht nimmt, und für die Kosten von `files_list` in einem Riesenordner.

## Architecture Patterns

### System Architecture Diagram

```
                 Messskript (Host, uv run)                        Protokoll (.planning/phases/25-.../)
                        |                                                      ^
     +------------------+-------------------+-------------------+              |
     |                  |                   |                   |              |
  docker exec        httpx Basic         httpx AppAPI       docker exec        |
  (occ, PHP-Snippet, (App-Passwort)      (APP_SECRET +      nc_app_mcp_connector
   Dateien anlegen)     |                 user=alice)        (optional: python -> http://caddy)
     |                  v                   v                   |
     |            127.0.0.1:8082 (nc35-caddy) <-----------------+
     |                  |
     v                  v
  nc35-nc  ----> Sabre DAV: PROPFIND /systemtags/  -> Tag-Ids (sichtbar für alice)
  (SQLite)       REPORT oc:filter-files            -> getTagsByIds -> 412 | searchBySystemTag(NAME)
                                                   -> 207 Multistatus (href, oc:fileid, resourcetype)
                 Notes REST /index.php/apps/notes/api/v1/notes -> id  --vergleich-->  PROPFIND oc:fileid
                 data/exapp_impersonation.log (Serverbeleg je impersoniertem Request)

  Sequenziell danach, je Version:                     
  compose.spike-tags.yml (NC_SPIKE_TAG=32.0.15-apache | 33.0.9-apache | 34.0.4-apache)
     -> 127.0.0.1:8083 -> nc-spike-tags (SQLite, admin + alice) -> App-aus / 412 / REPORT-Grundform
     -> docker compose down -v  (Volume weg, sonst Upgrade-Lauf beim nächsten Tag)
```

### Recommended Project Structure
```
compose.spike-tags.yml                 # Wegwerf-Instanz, Image-Tag per Variable, Port 8083 (oder im Phasenordner, siehe unten)
scripts/tag_spike.py                   # Messskript, unter ruff/pyright/vulture (Projektgates)
.planning/phases/25-mess-spike-tag-abfrage/
  25-MESSBERICHT.md                    # Befundtabelle: Kommando | Rohwert | Deutung
  raw/                                 # Rohausgaben je Block (Multistatus-Auszüge, Zeitreihen, occ-Ausgaben)
```
Ablageort des Skripts ist Ermessen: `scripts/` bedeutet Qualitätsgates (ruff-Vollregelsatz, pyright, vulture) und Wiederverwendbarkeit bei NC 36; im Phasenordner wäre es ruff-frei (`exclude = [".planning"]`), aber pyright/vulture sähen es nicht. Empfehlung `scripts/`, weil Phase 26 (Roundtrip-Zähler) und Phase 29 (occ-Check-Gegenprobe) dieselben Bausteine brauchen.

### Pattern 1: Wegwerf-Instanz je Version (offizielles Image)
**What:** Eine Compose-Datei, Image-Tag als Pflichtvariable, eigener Projektname, eigenes Volume, Loopback-Port 8083.
**When to use:** 32, 33, 34 nacheinander; nie zwei gleichzeitig.
```yaml
# Source: Muster compose.test.yml (Repo), Werte angepasst
name: nc-mcp-spike-tags
services:
  nextcloud:
    image: "nextcloud:${NC_SPIKE_TAG:?set NC_SPIKE_TAG, e.g. 32.0.15-apache}"
    container_name: nc-spike-tags
    ports:
      - "127.0.0.1:8083:80"          # loopback only (WR-06)
    environment:
      SQLITE_DATABASE: nextcloud
      NEXTCLOUD_ADMIN_USER: admin
      NEXTCLOUD_ADMIN_PASSWORD: spike-tags-admin-pw
      NEXTCLOUD_TRUSTED_DOMAINS: "localhost 127.0.0.1"
    healthcheck:
      test: ["CMD", "php", "-r", "exit(file_get_contents('http://localhost/status.php') ? 0 : 1);"]
      interval: 5s
      timeout: 5s
      retries: 40
    volumes:
      - nc-spike-tags-data:/var/www/html
volumes:
  nc-spike-tags-data:
```
Ablauf je Version (Zeiten [ASSUMED], im Protokoll messen): Pull ≈ 1 bis 3 min, Erstinstallation bis `occ status` → `installed: true` ≈ 1 bis 2 min (Healthcheck ist früher grün, deshalb `wait_for_install` aus `scripts/bootstrap_test_nc.sh` übernehmen), Messung < 2 min, `down -v` Sekunden.
```bash
export NC_SPIKE_TAG=32.0.15-apache
docker compose -f compose.spike-tags.yml up -d --wait
# occ status bis "installed: true" pollen (wait_for_install-Muster)
# alice anlegen: Passwort über stdin (occ_pw-Muster, OC_PASS + --password-from-env)
# App-Passwort: occ user:auth-tokens:add alice --password-from-env --name spike25
occ config:system:set auth.bruteforce.protection.enabled --value=false --type=boolean
occ status; occ app:list | grep -E "systemtags|dav"      # Version of record
# ... Messblöcke ...
docker compose -f compose.spike-tags.yml down -v
```

### Pattern 2: REPORT-Aufruf mit beiden Credential-Arten
```python
# Source: Aufrufform wie clients/dav.py (stat/find_by_fileid), Body wie STACK.md Abschnitt 2
from urllib.parse import quote
from lxml import etree
from mcp_connector.nextcloud.clients import xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials

def report_body(tag_id: str) -> bytes:
    if not tag_id.isdigit():
        raise ValueError("tag id must be digits")
    root = etree.Element(f"{{{xml.OC}}}filter-files", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.OC}}}fileid")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    rules = etree.SubElement(root, f"{{{xml.OC}}}filter-rules")
    etree.SubElement(rules, f"{{{xml.OC}}}systemtag").text = tag_id
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")

def home_url(creds: Credentials, sub: str = "/") -> str:
    # bewusst NICHT dav.files_url: das biegt ueber safe_path auf NC_MCP_FILES_ROOT um
    return f"{creds.base_url}/remote.php/dav/files/{quote(creds.user, safe='')}{quote(sub, safe='/')}"

basic = Credentials(base_url=env["NC_MCP_URL"], user="alice", secret=env["NC_MCP_TEST_APP_PASSWORD"], mode=MODE_BASIC)
appapi = Credentials(base_url=env["NC_MCP_URL"], user="alice", secret=env["APP_SECRET"], mode=MODE_APPAPI,
                     app_id=env["APP_ID"], app_version=env["APP_VERSION"], aa_version=env.get("AA_VERSION", ""))
response = await client.request("REPORT", home_url(creds), headers={"Content-Type": "application/xml"},
                                content=report_body(tag_id), auth=creds.auth())
```
Vergleich: Menge `{oc:fileid}` beider Läufe als sortierte Liste ins Protokoll, dazu Status, Bytes, Anzahl. Kontrollen wie in `test_exapp_dav_matrix.py`: (a) `GET /ocs/v2.php/cloud/user` unter AppAPI liefert `alice`, (b) falsches `APP_SECRET` wird abgelehnt, (c) die REPORT-Zeile erscheint in `data/exapp_impersonation.log` mit `"user":"alice","method":"REPORT"`. `.env.nc35` enthält `APP_ID`, `APP_SECRET`, `APP_VERSION`, `NC_MCP_URL`, `NC_MCP_TEST_USER`, `NC_MCP_TEST_APP_PASSWORD` (Namen gelesen, Werte nicht); `AA_VERSION` fehlt dort, ist optional (Container: `35.0.0`).

Optionaler Produktionsweg-Lauf aus dem ExApp-Container (Env dort vorhanden, Secret wird nie ausgegeben):
```bash
docker exec -i nc_app_mcp_connector /app/.venv/bin/python - < report_probe.py   # liest APP_SECRET/NEXTCLOUD_URL aus os.environ
```

### Pattern 3: Synthetischer Datenbestand auf nc35
**Baum (~10.000 Dateien):** z. B. `/spike25/tree/a{0..9}/b{0..9}/c{0..9}/f{0..9}.txt` = 1.000 Ordner, 10.000 Dateien, Tiefe 4 (optional eine Ebene tiefer für den Vorfahren-Aspekt). **Extremfall:** `/spike25/flat/f00000..f09999.txt` in einem Ordner.
```bash
# im Container als www-data, Datenverzeichnis des offiziellen Images
MSYS_NO_PATHCONV=1 docker exec -u www-data nc35-nc sh -c '
  base=/var/www/html/data/alice/files/spike25
  mkdir -p "$base/flat"
  for i in $(seq -w 0 9999); do printf "spike25 %s\n" "$i" > "$base/flat/f$i.txt"; done
  for a in 0 1 2 3 4 5 6 7 8 9; do for b in 0 1 2 3 4 5 6 7 8 9; do for c in 0 1 2 3 4 5 6 7 8 9; do
    d="$base/tree/a$a/b$b/c$c"; mkdir -p "$d"
    for f in 0 1 2 3 4 5 6 7 8 9; do printf "x\n" > "$d/f$f.txt"; done
  done; done; done'
MSYS_NO_PATHCONV=1 docker exec -u www-data nc35-nc php occ files:scan --path=/alice/files/spike25
```
**Tag-Stufen per PHP-Einmal-Snippet** (Skript über stdin, Argumente hinter `--`; Bootstrap wie occ über `lib/base.php`, als www-data) [MEDIUM: Mechanik aus Quelle, nicht ausgeführt; erster Lauf ist ein Smoke-Test mit 1 Datei]:
```php
<?php
// Source: ISystemTagObjectMapper::setObjectIdsForTag (@since 31.0.0)
require_once '/var/www/html/lib/base.php';
[$_, $tagId, $count, $sub] = $argv;              // z. B. -- 7 5000 spike25/tree
$folder = \OCP\Server::get(\OCP\Files\IRootFolder::class)->getUserFolder('alice')->get($sub);
$ids = [];
$walk = function ($node) use (&$walk, &$ids) {
    foreach ($node->getDirectoryListing() as $child) {
        if ($child instanceof \OCP\Files\Folder) { $walk($child); } else { $ids[] = (string)$child->getId(); }
    }
};
$walk($folder);
sort($ids);
$step = max(1, intdiv(count($ids), (int)$count));   // gleichmaessig ueber den Baum verteilt
$pick = array_slice(array_values(array_filter($ids, fn($k) => $k % $step === 0, ARRAY_FILTER_USE_KEY)), 0, (int)$count);
\OCP\Server::get(\OCP\SystemTag\ISystemTagObjectMapper::class)->setObjectIdsForTag($tagId, 'files', $pick);
echo count($pick), "\n";
```
```bash
docker exec -i -u www-data -w /var/www/html nc35-nc php -- "$TAG_ID" 5000 spike25/tree < set_tag_objects.php
```
Stufe 1 und 100 zusätzlich mit mindestens einem getaggten Ordner (Subtree-Fall) fahren; die 5000 dürfen reine Dateien sein, der Messbericht nennt die Zusammensetzung.

**Optionaler Ballast (Recognize-artig, näher an PR #64298):** 30 bis 40 Füll-Tags (`tag:add spike25-fill-NN public`) und je `setObjectIdsForTag(fill, 'files', alle 10.000 flat-Ids)` ≈ 300k bis 400k Zuordnungen. Danach dieselben REPORT-Messungen wiederholen: zeigt, ob die Größe der Mapping-Tabelle den REPORT auf `kein-ki` verteuert. Dauer [ASSUMED] Minuten; wenn es länger als 10 min läuft, abbrechen und als Grenze notieren.

### Pattern 4: Wanduhr sauber messen
- Messpunkt: `time.perf_counter()` um `client.request(...)` (httpx liest den Body vollständig), Timeout `httpx.Timeout(60.0)`, ein `AsyncClient` je Block, `follow_redirects=False`.
- Warm: 3 Aufwärmläufe verwerfen, dann N = 15; protokollieren: min, Median, p95 (bei 15 Werten der 15. Wert ist max, also p95 ≈ zweitgrößter Wert, ehrlich benennen), max, Antwortbytes, Trefferzahl, Status.
- Kalt (sekundär, N = 3): vor jedem Lauf `docker exec nc35-nc apachectl -k graceful` (setzt mod_php-Worker und damit OPcache zurück), dann 5 s warten. OS-Seitencache der SQLite-Datei bleibt warm; so benennen.
- Referenzpunkte in derselben Serie: (a) `PROPFIND /systemtags/` Depth 1 (Namensauflösung), (b) REPORT 1/100/5000, (c) PROPFIND Depth 1 auf `/spike25/flat` ohne `nc:system-tags` (das zahlt `files_list` heute schon, weil das Tool clientseitig fenstert), (d) dasselbe mit `nc:system-tags` (PR-Referenz), (e) `status.php` als Bodenwert des Hops.
- Messbedingungen ins Protokoll: `docker stats --no-stream` davor, `occ status`, `dbtype sqlite3`, `memcache.local` leer (gemessen: auf nc35 nicht gesetzt, Produktion hat meist APCu), Host-Last (n8n, Findling, 34er-Topologie laufen mit).
- Schwelle D-25-04 prüft den **Median warm** des REPORT bei 5000 gegen 1 s; p95 und kalt werden mitgeliefert, damit der Owner am Checkpoint die Streuung sieht.

**prepare_context-Referenz:** vorhandene Messdatei nutzen, nicht neu bauen:
```bash
set -a && . ./.env.nc35 && set +a
export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 NC_MCP_E2E_NEXTCLOUD=nc35-nc \
       NC_MCP_E2E_HARP=nc35-harp NC_MCP_E2E_CADDY=nc35-caddy \
       NC_MCP_E2E_CONTAINERS=nc35-nc,nc_app_mcp_connector,nc35-harp,nc35-caddy,nc35-greenmail
uv run pytest tests/integration/test_ctx_bundle.py -m integration -s -k wall_clock
```
Liefert min/Median/max für `short` und `full` (RUNS = 3) plus Einzelbeine; historische Referenz 0,84 s / 0,99 s (Plan 04-04, NC 34). Einmal **vor** dem Datenaufbau (Baseline), einmal **mit** den 20.000 Spike-Dateien (die Suche im files-Provider läuft dann über mehr Einträge). Für die Checkpoint-Aussage zählt: REPORT-Median bei 5000 im Verhältnis zur prepare_context-Wanduhr, weil der REPORT laut ARCHITECTURE parallel zu den Beinen startet.

### Pattern 5: Notiz-Id gegen fileid
```text
1. GET  /index.php/apps/notes/api/v1/settings            -> notesPath (Standard "Notes")
2. POST /index.php/apps/notes/api/v1/notes {"title":"spike25 Notiz","content":"x","category":"spike25"} -> id, category, title
3. PROPFIND Depth 1 /remote.php/dav/files/alice/<notesPath>/spike25/  mit oc:fileid, d:displayname
4. Vergleich: Notes-id == oc:fileid der Datei "<title>.md"? Zusätzlich GET /notes/{fileid} liefert dieselbe Notiz
5. Ordner <notesPath>/spike25 taggen -> REPORT liefert den Ordner (fileid des Ordners, nicht der Notiz):
   Beleg, dass der Notes-Anschluss neben dem fileid-Satz den Pfad notesPath + "/" + category braucht
6. Gegenprobe Dateiname != Titel: zweite Notiz mit gleichem Titel anlegen (Notes vergibt "Titel (2).md"),
   id trotzdem == fileid?
7. Aufräumen: DELETE /notes/{id} je Notiz, danach Kategorie-Ordner per WebDAV DELETE, trashbin:cleanup nur, wenn der Papierkorb vorher leer war
```
Als alice mit App-Passwort (Notes-REST unter AppAPI ist seit Phase 2 belegt, docs/spike-dav.md). Bestehender Client: `clients/notes.py` (`NOTES_API_PREFIX = "/index.php/apps/notes/api/v1"`, `create_note`, `get_note`) kann direkt genutzt werden.

### Pattern 6: Einzelbefunde (je eine Zeile im Protokoll)
| Befund | Ort | Aufbau | Erwartung laut Quelle |
|---|---|---|---|
| App aus | 32, 33, 34, 35 | Datei anlegen, `tag:files:add` (App an), dann `app:disable systemtags`; messen: Capability `systemtags`, `GET /ocs/v2.php/search/providers` (Eintrag `systemtags`), `PROPFIND /systemtags/`, REPORT, PROPFIND `nc:system-tags`, `occ list \| grep tag:`; danach `app:enable systemtags` und Capability erneut | DAV antwortet unverändert; Capability, Suchprovider und `tag:files:*` fehlen |
| 412 unbekannte Id | 32-35 | REPORT mit Id 999999 | 412, Body `Cannot filter by non-existing tag` |
| 412 gelöscht/neu | 32-35 (Grundform), 35 ausführlich | Tag anlegen (Id A), zuordnen, `tag:delete A`, gleichen Namen neu anlegen (Id B), neu zuordnen; REPORT A und B | A → 412, B → 207; `PROPFIND /systemtags/` zeigt nur B |
| Unsichtbares Tag | 35 | `tag:add … invisible`, `tag:files:add` auf alices Datei; REPORT als alice und als admin; Tag-Liste als alice | alice: 412 und Tag fehlt in Liste; admin: 207 |
| Varianten | 35 | Tag X `public`; per DB-Insert gleichnamig `restricted` (Y), gleichnamig `invisible` (Z), Groß/Klein-Variante `public` (W); je eine Datei zuordnen; REPORT als alice auf X, Y, W | X und Y liefern beide die Dateien von X und Y (Namenssuche), Z fehlt für alice, W getrennt (SQLite binär) |
| Zielpfad | 32-35 | Tag auf `/p/tagged`; REPORT auf Home-Wurzel, auf `/p/tagged/sub`, auf fremden Ordner `/q` | Alle liefern `/p/tagged`, hrefs home-relativ; Zielpfad filtert nicht |
| Freigabe-Grenze | 35 | alice taggt `/p`, teilt `/p/sub` an bob; zweiter Fall: alice taggt `/r` und teilt `/r` selbst; REPORT als bob | Fall 1 leer, Fall 2 liefert `/r` in bobs Pfadsicht |

Varianten-Insert (PHP-Snippet, gleiche Bootstrap-Form wie oben):
```php
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->insert('systemtag')->values([
    'name' => $qb->createNamedParameter('kein-ki-spike25'),
    'visibility' => $qb->createNamedParameter(1), 'editable' => $qb->createNamedParameter(0),
    'etag' => $qb->createNamedParameter(md5((string)time())),
])->executeStatement();
echo $db->lastInsertId('*PREFIX*systemtag'), "\n";
```
Die Spalte `etag` existiert in 32 bis 35 (`createTag` schreibt sie, stable32 geprüft) [VERIFIED].

### Anti-Patterns to Avoid
- **Als admin messen:** admin sieht unsichtbare Tags, der REPORT fällt anders aus. Jede Tag-Messung als alice (Nicht-Admin), admin nur als ausdrücklicher Gegenfall.
- **`dav.files_url` / `parse_entries` im Messskript:** biegen auf `NC_MCP_FILES_ROOT` um bzw. verwerfen Einträge außerhalb der Sandbox. Eigene URL und eigener Leser.
- **Volume zwischen Versionen behalten:** `up` mit neuem Tag auf altem Volume startet einen Upgrade-Lauf (32 → 33); ein Rückwärtsschritt scheitert. Immer `down -v`.
- **`tag:files:add` nach `app:disable systemtags`:** das Kommando existiert dann nicht.
- **Spike-Tag `kein-ki` exakt so nennen:** ein vergessenes Tag dieses Namens verfälscht die Integrations- und Kanarientests der Phasen 26 bis 28. Präfix `kein-ki-spike25` (Varianten gleichnamig untereinander).
- **5000 occ-Aufrufe oder 10.000 PUTs:** Stunden statt Minuten.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Nextcloud-Instanz je Version | eigenes Image, Quelltext-Build | offizielles `nextcloud:<patch>-apache` | Release-genau, Installer im Entrypoint |
| Installationswarten | Schlafen fester Länge | `wait_for_install` aus `scripts/bootstrap_test_nc.sh` | Healthcheck ist vor der Installation grün |
| Passwörter an occ | `-e`/argv | `occ_pw`-Muster (stdin, `OC_PASS`, `--password-from-env`) | argv ist in `ps` lesbar (WR-06) |
| AppAPI-Header | eigene base64-Bastelei | `Credentials(mode=MODE_APPAPI).auth()` | Produktionsnaht, maskiertes `repr` |
| Multistatus lesen | Regex | `xml.parse_multistatus` / `xml.parse_root` (XXE-gehärtet) | Hrefs und Props sauber; `nc:system-tags` braucht `parse_root` (STACK Parser-Falle) |
| prepare_context-Wanduhr | neues Messprogramm | `tests/integration/test_ctx_bundle.py -s` | Existiert, trennt Beine, prüft Budgets |
| Tag-Zuordnung in Masse | Schleife über occ | `setObjectIdsForTag` | eine Transaktion |

**Key insight:** Die Messung soll Nextcloud-Verhalten belegen, nicht das eigene Werkzeug. Alles, was nicht gemessen wird (Datenaufbau), darf den schnellsten internen Weg nehmen; alles, was gemessen wird (REPORT, Notes, Impersonation), geht über denselben HTTP-Weg wie der Connector.

## Runtime State Inventory

Kein Rename, aber eine Messphase mit Zustandsänderungen an einer Langzeit-Instanz; deshalb eine Rückbau-Inventur nach demselben Raster.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (nc35) | Ausgangsstand gemessen: `occ tag:list --output=json` = `[]`; alice hat 275 Dateien, Papierkorb leer | Vor dem Spike: Tag-Liste, `find data/alice/files -type f \| wc -l`, Papierkorb-Zähler, Anzahl `oc_systemtag_object_mapping` (PHP-Snippet) als Baseline; danach identisch |
| Stored data (Spike) | 20.000 Dateien + ~1.100 Ordner unter `/spike25`, Tags `kein-ki-spike25*`, `spike25-fill-*`, Notizen der Kategorie `spike25`, Share alice → bob | Reihenfolge: Tags per `tag:delete` (entfernt Zuordnungen), Share löschen, `occ files:delete --force --skip-trash alice/files/spike25` (35), Notizen per Notes-API, `files:cleanup`; danach Baseline-Vergleich |
| Live service config | App systemtags wird auf nc35 kurz deaktiviert | `app:enable systemtags` im `finally`, Capability danach gemessen |
| OS-registered state | Keiner (keine Cronjobs, keine Tasks) | none, verifiziert durch Aufbau-Beschreibung |
| Secrets/env vars | Neues App-Passwort `spike25` je Wegwerf-Instanz; auf nc35 die vorhandenen aus `.env.nc35` | Wegwerf: fällt mit `down -v`; nc35: keine neuen Tokens nötig, falls doch, `user:auth-tokens:delete` |
| Build artifacts | Neu gezogene Images 32.0.15/33.0.9/34.0.4 (je ~2 GB entpackt), Volume `nc-mcp-spike-tags_nc-spike-tags-data` | `down -v` je Version; Images nach Owner-Wunsch behalten oder `docker rmi` |

## Common Pitfalls

### Pitfall 1: Git-Bash verbiegt absolute Pfade in docker-Argumenten
**What goes wrong:** `docker exec ... occ files:scan --path=/alice/files/spike25` erreicht den Container als `C:/Program Files/Git/alice/...`.
**Why it happens:** MSYS-Pfadkonvertierung beim Start nativer Programme (im Repo bereits gemessen, Kommentar in `.env.nc35` zu `NC_MCP_TEST_SHARED_DIR`).
**How to avoid:** Skript in Python, `subprocess` ruft `docker` direkt (keine Konvertierung, Muster `exchange_evidence.py`); in Bash `MSYS_NO_PATHCONV=1`. CR aus Container-Ausgaben strippen (`tr -d '\r'`-Muster).
**Warning signs:** "file not found" bei korrekt aussehendem Pfad.

### Pitfall 2: Halbe Instanz (Healthcheck grün, Installation läuft noch)
**What goes wrong:** occ-Kommandos scheitern oder treffen eine unvollständige Installation.
**How to avoid:** `occ status` auf `installed: true` pollen (60 × 5 s), erst dann Bootstrap.
**Warning signs:** "Nextcloud is not installed" oder leere `app:list`.

### Pitfall 3: Volume-Wiederverwendung zwischen Versionen
**What goes wrong:** 33 startet auf dem 32er-Volume ein Upgrade statt einer frischen Installation; die Messung gilt dann einer upgegradeten Instanz.
**How to avoid:** `docker compose -f compose.spike-tags.yml down -v` als letzter Schritt jedes Versionsblocks, vor dem nächsten `up` `docker volume ls | grep spike-tags` leer prüfen.

### Pitfall 4: SQLite ist nicht Produktion
**What goes wrong:** Latenz und Varianten-Befund (Groß/Klein) gelten für SQLite; MariaDB/PostgreSQL können abweichen.
**How to avoid:** Messbedingungen ins Protokoll; am Checkpoint ausdrücklich nennen. Liegt der Median nahe an 1 s (etwa 0,6 bis 1,0 s), Owner-Frage stellen, ob eine Gegenmessung auf einer PostgreSQL-Wegwerf-Instanz vor Phase 26 gewünscht ist (würde D-25-02 erweitern, also Owner-Entscheid).

### Pitfall 5: Vergessene Testdaten verfälschen spätere Phasen
**What goes wrong:** 20.000 Spike-Dateien oder ein Tag `kein-ki*` bleiben auf nc35; prepare_context- und Kanarientests späterer Phasen messen eine andere Instanz.
**How to avoid:** Baseline vorher, Rückbau im `finally`, Baseline-Vergleich als letzte Protokollzeile (Muster Stack-Research 26.09.: Tag, Share, Dateien, Tokens entfernt).

### Pitfall 6: systemtags bleibt aus
**What goes wrong:** Abbruch zwischen `app:disable` und `app:enable`; die Capability fehlt dauerhaft, spätere Tests laufen auf einer untypischen Instanz.
**How to avoid:** Block mit `try/finally`, `app:enable` immer; Abschlusszeile "Capability systemtags vorhanden: ja".

### Pitfall 7: Speicher der Docker-VM
**What goes wrong:** Die VM hat 7,6 GiB, nicht 16; parallel laufen nc35-Topologie, 34er-Topologie, Findling, n8n (≈ 1,5 GiB gemessen). `files:scan` von 20.000 Dateien und PHP mit `memory_limit 512M` kommen dazu.
**How to avoid:** Nur eine Wegwerf-Instanz (D-25-01), `docker stats --no-stream` vor jedem Block ins Protokoll; die Wegwerf-Instanzen tragen keine Testdaten außer einer Handvoll Dateien.

### Pitfall 8: 412 als leere Menge gedeutet (im Messskript)
**What goes wrong:** Das Skript behandelt 412 wie "keine Treffer" und protokolliert "0".
**How to avoid:** Status und Body-Auszug (`s:message`) immer mitprotokollieren, nie nur die Trefferzahl.

### Pitfall 9: Messen durch das gemessene Werkzeug
**What goes wrong:** Den REPORT über einen künftigen Connector-Pfad messen; bei Abweichung ist unklar, ob Server oder Code.
**How to avoid:** Roh-httpx mit `Credentials` (Projektregel "Gegenprobe nie mit dem Muster der Umsetzung"); die Notes-id kommt aus der Notes-API, die fileid aus PROPFIND, zwei unabhängige Wege.

### Pitfall 10: Die Impersonations-Kontrolle fehlt
**What goes wrong:** Ein grüner REPORT unter "AppAPI" war in Wahrheit ein anderer Kanal.
**How to avoid:** Kontrollen aus `test_exapp_dav_matrix.py`: `cloud/user` = alice, falsches Secret abgelehnt, Log-Zeile im `exapp_impersonation.log` (existiert auf nc35, letzte Zeile 24.09.).

### Pitfall 11: Veraltetes `.env.nc35`
**What goes wrong:** `APP_SECRET` in `.env.nc35` (Stand 24.09.) passt nicht mehr zur laufenden Registrierung, falls die ExApp seitdem neu registriert wurde (Container 0.2.1 läuft seit 30 h).
**How to avoid:** Kontrolle (a) aus Pitfall 10 als allererster Schritt; bei 401 `bootstrap_exapp.sh --nc35` nicht blind neu laufen lassen, sondern Owner fragen (Topologie wird auch von anderen Messungen genutzt).

### Pitfall 12: greenmail ist In-Memory
**What goes wrong:** `test_ctx_bundle.py` erwartet die Testmails; nach einem Neustart von `nc35-greenmail` fehlen sie, das Mail-Bein misst dann etwas anderes.
**How to avoid:** Ausgabe des Mail-Beins im Protokoll lesen; bei fehlenden Mails das als Messbedingung nennen statt still zu vergleichen.

## Code Examples

Zentrale Formen stehen in den Patterns oben. Ergänzend die Protokollzeile, die jede Messung schreibt (Format nach `docs/exchange-evidence.md`, intern abgelegt):
```python
def row(block: str, command: str, status: int, raw: str, seconds: float | None = None) -> str:
    timing = "" if seconds is None else f" | {seconds * 1000:.0f} ms"
    return f"{now_stamp()} | {block} | {command} | HTTP {status}{timing} | {raw[:300]}"
```
Ins Protokoll gehören nie: `APP_SECRET`, App-Passwörter, der `AUTHORIZATION-APP-API`-Wert, Authorization-Header.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `nextcloud:35.0.0-apache` ohne amd64 | `35.0.1-apache` mit amd64 | 25.09.2026 | nc35 könnte künftig vom offiziellen Tag laufen; nicht in dieser Phase |
| Tag-Zuordnung je Objekt | `setObjectIdsForTag` | NC 31 | Massenzuordnung in einer Transaktion |
| PR #64298 Zahlen 6,4 s / 2,1 s | 6,2 s / 2,4 s (PR-Text aktuell) | nach 14.09.2026 | PITFALLS-Zitat korrigieren, PR weiterhin offen |

**Deprecated/outdated:**
- Kommentar in `compose.nc35.yml` zum fehlenden amd64-Manifest: überholt.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Dateien anlegen + `files:scan` für 20.000 Dateien dauert ≈ 1 bis 3 min | Standard Stack, Pattern 3 | Nur Zeitplanung; Rückfall bleibt gleich |
| A2 | PHP-Snippet mit `require_once lib/base.php` läuft per `docker exec -i -u www-data -w /var/www/html … php --` | Pattern 3 | Rückfall DAV-PUT auf `systemtags-relations` (≈ 10 bis 20 min sequenziell) |
| A3 | MariaDB/MySQL könnte Groß/Klein-Varianten im REPORT anders behandeln als SQLite | Quellbefund 1, Pitfall 4 | Befund "Varianten" gilt nur für SQLite; Doku-Grenze in Phase 29 |
| A4 | Pull ≈ 1 bis 3 min, Erstinstallation ≈ 1 bis 2 min je Version | Pattern 1 | Nur Zeitplanung |
| A5 | `apachectl -k graceful` leert OPcache der Worker (Definition "kalt") | Pattern 4 | Kaltwerte ungenau benannt; Warmwerte (maßgeblich für D-25-04) unberührt |
| A6 | `files:scan`, `files:cleanup`, `trashbin:cleanup` existieren auf 32 bis 34 unverändert | Quellbefund 4 | Wird dort nicht gebraucht (Wegwerf-Instanz fällt mit `down -v`) |

## Open Questions

1. **Gilt D-25-01 "(nextcloud-docker-dev)" als Festlegung oder als Beispiel?**
   - What we know: Discretion-Klausel gibt die Aufbau-Mechanik frei; das Repo nutzt überall das offizielle Image.
   - Recommendation: offizielles Image, Begründung ein Satz im Messbericht; nur bei Owner-Widerspruch umstellen.
2. **Patch-Stand der Matrix: aktuelle Patches (32.0.15/33.0.9/34.0.4) oder lokal vorhandene (33.0.7/34.0.3)?**
   - Recommendation: aktuelle Patches; lokale nur als Rückfall bei Netzproblemen, Version im Protokoll nennen.
3. **Ballast (300k bis 400k Zuordnungen) ja oder nein?**
   - What we know: D-25-03 verlangt den 10k-Ordner-Extremfall; die 385k Zuordnungen des PR sind der Teil, der `nc:system-tags` teuer macht.
   - Recommendation: ja, als eigener, abbrechbarer Block nach den Pflichtstufen; fällt er aus Zeitgründen weg, im Bericht nennen.
4. **Speicherort des Messskripts (`scripts/` vs. Phasenordner).**
   - Recommendation: `scripts/tag_spike.py` unter den Gates (siehe Project Structure).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine (Docker Desktop, WSL2) | alle Blöcke | ✓ | 29.5.2, VM 7,6 GiB, 12 CPUs | none |
| Docker Compose | Wegwerf-Instanzen | ✓ | v5.1.4 | none |
| nc35-Topologie | Impersonation, Latenz, Notes, Einzelbefunde | ✓ | 35.0.0, healthy | none |
| `.env.nc35` (APP_SECRET, App-Passwörter) | Messung 2 | ✓ | 24.09.2026 | Kontrolle zuerst, sonst Owner |
| ExApp-Container-Python | optionaler Produktionsweg-Lauf | ✓ | `/app/.venv/bin/python`, httpx 0.28.1 | Host-Lauf genügt |
| Images 32.0.15/33.0.9/34.0.4-apache | Matrix | ✗ (Pull nötig) | Hub verifiziert | lokal 33.0.7/34.0.3 |
| Port 127.0.0.1:8083 | Wegwerf-Instanz | ✓ (frei) | | 8084 |
| uv | Skriptlauf | ✓ | 0.11.7 | none |
| gh CLI | Quellprüfung | ✓ | 2.92.0 | WebFetch |
| `sqlite3` CLI im NC-Container | DB-Zählungen | ✗ | | PHP-Snippet mit `IDBConnection` |
| `bc` auf dem Host | Zeitrechnung in Bash | ✗ | | Python `perf_counter` |
| Plattenplatz | Images, 20k Dateien | ✓ | 58 GB frei | `docker image prune` nach Owner-OK |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** Images (Pull), `sqlite3`, `bc`.

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | ja (Test-Credentials) | App-Passwörter und `APP_SECRET` nur aus `.env.nc35`/stdin, nie argv, nie Protokoll |
| V3 Session Management | nein | |
| V4 Access Control | ja (gemessen, nicht gebaut) | Messung als Nicht-Admin; Freigabe-Grenze als Befund |
| V5 Input Validation | ja | Tag-Id nur Ziffern, XML-Bodies per lxml, Antworten über `xml.parse_root` (XXE-Schutz) |
| V6 Cryptography | nein | |
| V14 Configuration | ja | Wegwerf-Port nur `127.0.0.1`, Bruteforce-Schutz nur auf Wegwerf-Instanzen aus, `down -v` |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret im `ps`/Container-Config | Information Disclosure | stdin-Muster (`occ_pw`, `nc_body` mit curl-Config auf stdin) |
| Secret im Messbericht | Information Disclosure | Protokollfunktion schreibt keine Header; Review des Berichts vor Commit (grep auf `APP_SECRET`-Wert und Token-Präfixe) |
| Offene Wegwerf-Instanz mit Default-Passwort | Elevation | Loopback-Bindung, Abriss direkt nach Messung |
| Rückstände (Tag, Share) auf nc35 | Tampering der Testbasis | Baseline-Inventur und Vergleich |

## Project Constraints (from CLAUDE.md)

- uv als Toolchain (`uv run --no-sync python …`), Systempython defekt.
- Docker/WSL2 als Teststrecke; Instanzen nur auf Loopback.
- Code und Kommentare Englisch, Projektkommunikation (Messbericht) Deutsch mit echten Umlauten, keine Em-Dashes, keine Emojis.
- Security: Messskript darf nichts sehen oder schreiben, was nicht zur Messung gehört; keine destruktiven Writes außerhalb der Spike-Objekte.
- GSD-Workflow: Änderungen nur über `/gsd-execute-phase`.
- Python-Qualitätsgates für alles unter `scripts/`: `ruff check .`, `ruff format --check .`, pyright (lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`, wie CI), `vulture src scripts vulture_whitelist.py`; lokal grün vor Commit.
- Commits als Owner `street1983nk <k.cherif@outlook.de>`, keine Claude-Trailer; Push nur mit Owner-Freigabe (Push-Hook blockiert main).
- Keine Mails, keine externen Posts; Owner-Checkpoint im Kurzformat (Befundliste mit Empfehlung, Antwort in einem Satz möglich).

## Empfohlene Reihenfolge (Ermessen, kritische drei vor dem Checkpoint)

1. **Werkzeug:** Compose-Datei, Messskript-Gerüst, Baseline-Inventur nc35, Kontrollen (cloud/user unter AppAPI).
2. **nc35 ohne Massendaten:** Notes (kritisch), Impersonation-Vergleich, 412 unbekannt und gelöscht/neu, unsichtbares Tag, Varianten, Zielpfad, Freigabe-Grenze, App-aus 35 (Bestätigung), prepare_context-Baseline.
3. **nc35 Latenz (kritisch):** Datenaufbau, Stufen 1/100/5000, Referenzen, optional Ballast, prepare_context mit Daten, Rückbau, Baseline-Vergleich.
4. **Matrix 32 → 33 → 34 (kritisch App-aus):** je Version auf, App-aus, 412, REPORT-Grundform inkl. Zielpfad, ab.
5. **Messbericht + Owner-Checkpoint** (Notes → EXCL-05, App-aus → Fail-closed-Auslöser, Latenz gegen 1 s → Batch-Entscheidung).

Bei grober Granularität (config `granularity: coarse`) lassen sich 1+2, 3 und 4+5 zu drei Plänen bündeln.

## Sources

### Primary (HIGH confidence)
- Live, lesend 26.09.2026: `docker ps/stats/images/system df`, `occ status/app:list/user:list/tag:list/list` auf `nc35-nc` und `nc-mcp-exapp-nc`, `printenv` im ExApp-Container, Laufzeit `occ status` (0,41 s je Aufruf)
- hub.docker.com API: Tags und Architekturen für nextcloud 32/33/34/35
- gh api nextcloud/server (stable32 bis stable35): `FilesReportPlugin.php`, `Folder.php`, `SearchBuilder.php`, `QuerySearchHelper.php`, `SystemTagManager.php`, `SystemTagObjectMapper.php`, `ISystemTagObjectMapper.php`, `core/Command/SystemTag/*`, `apps/systemtags/lib/Command/Files/*`, `apps/systemtags/appinfo/info.xml`, `apps/files/lib/Command/Delete.php`, `core/shipped.json`, `core/Migrations/Version13000Date20170718121200.php`
- gh api nextcloud/notes@v6.1.0: `lib/Service/Note.php`, `lib/Controller/NotesApiController.php`
- `gh pr view 64298 -R nextcloud/server` (Status OPEN, Zahlen)
- Repo: `compose.nc35.yml`, `compose.test.yml`, `compose.exapp.yml`, `scripts/bootstrap_test_nc.sh`, `scripts/exchange_evidence.py`, `src/mcp_connector/nextcloud/credentials.py`, `clients/dav.py`, `clients/notes.py`, `tests/integration/test_exapp_dav_matrix.py`, `test_ctx_bundle.py`, `topology.py`, `tests/conftest.py`, `docs/spike-dav.md`, `pyproject.toml`

### Secondary (MEDIUM confidence)
- github.com/juliusknorr/nextcloud-docker-dev README (Standalone-Modus klont Quelltext per Branch)

### Tertiary (LOW confidence)
- Zeitschätzungen für Pull, Installation, `files:scan` (A1, A4)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, Tags und Architekturen per Registry-API, laufende Topologie gemessen
- Architecture: HIGH für Aufrufformen (Repo-Code), MEDIUM für den PHP-Snippet-Weg
- Pitfalls: HIGH, überwiegend im Repo bereits erlebt (MSYS, Installationsrennen, Topologie-Verwechslung) oder aus Quelle abgeleitet

**Research date:** 2026-09-26
**Valid until:** 2026-10-10 (Patch-Tags wandern wöchentlich; PR #64298 kann landen)

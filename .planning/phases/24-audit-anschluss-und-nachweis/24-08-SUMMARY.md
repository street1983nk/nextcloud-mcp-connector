---
phase: 24-audit-anschluss-und-nachweis
plan: 08
subsystem: auth
tags: [token-exchange, evidence, docker, jwks, audit, harp, appapi]

requires:
  - phase: 24-01
    provides: "die Spalte actor in Zeile und Ausgabe, und EXCHANGE_CLIENT_ID als unterscheidbare Spur"
  - phase: 24-03
    provides: "die Abweisungskette x:exchange mit Bezeichner und Anzahl, REFUSALS_KEYWORD"
  - phase: 24-06
    provides: "die laufende NC-35-Topologie mit der ExApp als 0.2.1 und den Weg, den Exchange-Pfad zu armieren"
provides:
  - "docs/exchange-evidence.md: der gemessene Zwei-Konten-Negativbeweis des Exchange-Pfads"
  - "scripts/exchange_evidence.py: der wiederholbare Messlauf, der die Rohausgabe erzeugt"
  - "compose.nc35.yml: der Dienst test-issuer, ein HTTPS-Schluesselsatz ohne Keycloak"
  - "Annahme A6 der Recherche gemessen und bestaetigt"
  - "Befund: auf dem ExApp-Weg entscheidet eine von HaRP aufloesbare Nextcloud-Anmeldung vor dem getauschten Token"
affects: [24-09]

tech-stack:
  added: []
  patterns:
    - "Registrierungsnutzlast zur Laufzeit aus dem Bootstrap lesen statt kopieren, damit die Wiederherstellung genau das zurueckschreibt, was der Bootstrap schreibt"
    - "Ein Messblock ist eigenstaendig: ein gefallener Block wird als Ergebnis gemeldet, der Lauf geht weiter und laesst die Topologie nicht armiert stehen"
    - "Statuscodes eines ExApp-Aufrufs stehen im Apache-Zugriffslog des Nextcloud-Containers, die handelnde Identitaet im exapp_impersonation.log"

key-files:
  created:
    - docs/exchange-evidence.md
    - scripts/exchange_evidence.py
  modified:
    - compose.nc35.yml
    - docs/standalone-oauth.md

key-decisions:
  - "Der Test-Issuer ist ein caddy:2 mit eigener interner CA und zwei statischen Dokumenten, kein Keycloak: die Tokens signiert der Lauf selbst, also fragt niemand den Issuer nach einem"
  - "Die Caddy-Konfiguration schreibt der command-Eintrag im Container statt eines Host-Mounts, damit der Dienst aus jedem Checkout und aus jedem Worktree startet"
  - "SSL_CERT_FILE wird nicht als Deploy-Variable gesetzt; der Lauf haengt die Wurzel an das Vertrauensbuendel des Images. A6 ist trotzdem gemessen, isoliert und mit Rohausgabe"
  - "Die Nutzlast der Registrierung wird zur Laufzeit aus scripts/bootstrap_exapp.sh extrahiert, weil eine Kopie von dreizehn Routen die Wiederherstellung still falsch machen wuerde"
  - "Messung 4 bekommt vier Faelle statt einem, weil ein einzelner Fall nicht sagt, welche der beiden Anmeldungen entschieden hat"
  - "Der eine Verweis auf die Messdatei steht in docs/standalone-oauth.md; die offene Ankuendigung dort verspricht ein Einrichtungsdokument, und das gehoert Plan 24-09"

patterns-established:
  - "Ein Nachweis dieses Repos nennt die Topologie, die armierte Konfiguration ohne Geheimnisse, die Rohausgabe je Block, den serverseitigen Beleg und am Ende, was er nicht beweist"
  - "Eine widerlegte Erwartung wird als Befund ausgeschrieben, samt der drei Messungen, die den Mechanismus isolieren"

requirements-completed: [EXCH-07]

duration: 95min
completed: 2026-09-24
---

# Phase 24 Plan 08: Der Zwei-Konten-Negativbeweis des Exchange-Pfads Summary

**Zwei ueber den Token-Exchange-Pfad geborene Identitaeten sehen nichts voneinander, gemessen gegen die laufende NC-35-HaRP-Topologie mit `404` und nie `200`, mit dem Apache-Statuscode und der Nextcloud-seitigen Impersonationszeile je Aufruf; und Messung 4 hat ihre Erwartung widerlegt: eine von HaRP aufloesbare Nextcloud-Anmeldung entscheidet die handelnde Identitaet vor dem getauschten Token.**

## Performance

- **Duration:** 95 min
- **Started:** 2026-09-24T04:55:00Z
- **Completed:** 2026-09-24T06:26:00Z
- **Tasks:** 3
- **Files modified:** 4 (2 neu, 2 geaendert)

## Accomplishments

- `docs/exchange-evidence.md` steht neben `docs/spike-dav.md` und `docs/nc35-evidence.md`, mit Kopf, vier Messbloecken, Statuscodes, serverseitigem Beweis, dem gemischten Lauf, der Abweisungskette und `## Consequence`.
- Die beiden Identitaeten sind nachweislich ueber den Exchange-Pfad entstanden: die armierte `NC_MCP_EXCHANGE_*`-Umgebung steht in der Rohausgabe, und die Audit-Zeile traegt `client_id = urn:mcp-connector:token-exchange` samt `actor`.
- Annahme A6 ist gemessen statt gelesen: `200` auf den Schluesselsatz ueber HTTPS aus dem ExApp-Container heraus, mit nichts als `SSL_CERT_FILE`.
- Der gemischte Lauf liegt vor: beide Aufrufe in `u:alice`, `prev_hash` des zweiten ist der `hash` des ersten, `audit:verify --json` meldet `"broken":false,"findings":[]`.
- Die Abweisungskette traegt `x:exchange`, `rejected`, `exchange_issuer` und die Anzahl, und keinen Wert aus dem Token.
- Die Topologie steht danach genau so da wie vor dem Lauf, live gegengeprueft.

## Task Commits

1. **Task 1: Der Test-Issuer im Compose-Netz und der wiederholbare Messlauf** - `c92c1f1`
2. **Task 2: Die vier Messungen und die Messdatei** - `46887e8`
3. **Task 3: Der gemischte Lauf und die pruefbare Kette** - `cb61989`

Der gemischte Lauf und die Audit-Bloecke von Task 3 stehen inhaltlich in derselben Datei wie Task 2, weil ein Lauf alle Daten auf einmal erzeugt; der Commit von Task 3 traegt deshalb den Verweis, der der zweite Teil dieses Tasks ist.

## Files Created/Modified

- `docs/exchange-evidence.md` - die Messdatei: Kopf mit Datum, Nextcloud 35.0.0 (Build 35.0.0.10), AppAPI 35.0.0, HaRP, App 0.2.1 und Test-Issuer; die armierte Konfiguration; A6; die vier Messungen; Zugriffslog; Impersonationslog; gemischter Lauf mit drei Audit-Rohausgaben; Abweisungskette; `## Consequence`; "What this does not prove".
- `scripts/exchange_evidence.py` - der Lauf: Schluessel erzeugen, Schluesselsatz im Test-Issuer veroeffentlichen, armieren, messen, Kette lesen, Bootstrap-Registrierung wiederherstellen und live gegenpruefen.
- `compose.nc35.yml` - fuenfter Unterschied zur 34er-Topologie: der Dienst `test-issuer`.
- `docs/standalone-oauth.md` - der eine Verweis auf die Messdatei.

## Die vier Messungen, kurz

| Messung | Was lief | Ergebnis |
|---------|----------|----------|
| 1 | Jedes Konto legt seine Datei an und liest sie, ueber sein getauschtes Token | `201` / `207` / `200`, beide Konten |
| 2 | alices Token auf den bekannten Pfad von bobs Datei, dazu der Versuch ueber `/../bob/...` und eine Suche nach dem Marker | `404`, Pfadverweigerung, `count: 0` |
| 3 | Die Gegenrichtung, symmetrisch | `404`, Pfadverweigerung, `count: 0` |
| 4 | Gueltiger `Authorization: Basic` von alice neben dem Exchange-Token von bob | **abweichend, siehe Befund** |

## Befund: Messung 4 hat ihre Erwartung widerlegt

Der Plan erwartete den Satz von `docs/spike-dav.md` spiegelbildlich: ein zusaetzlicher gueltiger Basic-Header aendert die handelnde Identitaet nicht. Gemessen wurde das Gegenteil, und die Datei schreibt es aus statt es umzuformulieren.

**Was gemessen wurde** (vier Faelle, damit der Mechanismus nicht geraten werden muss):

1. Basic von alice allein: alices Datei wird geliefert. Die Anmeldung ist also gueltig.
2. Exchange-Token von bob allein: dieselbe Datei wird verweigert. Der Pfad ist also aktiv.
3. Basic zuerst, Exchange-Token danach: `HTTP 401`, niemand handelt.
4. Exchange-Token zuerst, Basic danach: **alices Datei wird geliefert**, die Anfrage lief als alice.
5. Dieselbe Reihenfolge mit einer Basic-Anmeldung, die alice nie hatte: die Anfrage laeuft als bob.

**Die Audit-Zeile jenes Falls** traegt weder eine `client_id` noch eine handelnde Partei. Ein Aufruf des Exchange-Pfads traegt beides. Die Identitaet kam also aus dem AppAPI-Header, den HaRP gesetzt hat, nachdem es alice aus ihrer Basic-Anmeldung aufgeloest hatte.

**Einordnung.** Das ist die dokumentierte Reihenfolge von `exapp/middleware.py` ("verify the AppAPI handshake, then the bearer") und gilt fuer unsere eigenen OAuth-Tokens genauso. Es ist keine Rechteausweitung: der Aufrufer muss eine funktionierende Nextcloud-Anmeldung des anderen Kontos halten, und wer die haelt, handelt ohnehin als dieses Konto. Neu ist, dass es gemessen ist, und die Folgerung gehoert in die Einrichtungsdoku:

> Auf einer ExApp-Installation entscheidet die Nextcloud-Anmeldung, die der Reverse Proxy aus der Anfrage aufloesen kann, welches Konto handelt, und erst danach das getauschte Token. Wer ein Sitzungs-Cookie, ein App-Passwort oder eine andere aufloesbare Anmeldung neben ein getauschtes Token legt, handelt als das Konto dieser Anmeldung, und nichts in der Antwort sagt, dass das Token nicht entschieden hat.

Das Risiko, das dieser Satz benennt, ist ein browsernaher Betrieb, in dem ein Cookie mitfaehrt, ohne dass es jemand beabsichtigt.

## Decisions Made

- **Der Test-Issuer ist kein Keycloak.** Der Lauf signiert seine Tokens selbst, also braucht er vom Issuer nur einen TLS-terminierten Schluesselsatz. Ein vollstaendiger Keycloak waere nur fuer die Golden-Fixture interessant, die ausdruecklich nicht im Scope ist (D-v1.6-02).
- **Die Caddy-Konfiguration entsteht im Container, nicht als Host-Mount.** Der bestehende `caddy`-Dienst der Datei mountet eine absolute Windows-Pfadangabe. Ein zweiter solcher Mount haette bedeutet, dass der neue Dienst nur aus dem Hauptcheckout startet und aus keinem Worktree, in dem dieser Plan ausgefuehrt wird. Der `command`-Eintrag schreibt die Datei stattdessen selbst.
- **`SSL_CERT_FILE` ist nicht die Deploy-Variable des Laufs.** A6 ist isoliert gemessen und haelt. Fuer den Lauf selbst waere sie trotzdem gefaehrlich: httpx baut fuer **jeden** Client einen SSL-Kontext, auch fuer die auf dem eigenen Weg nach Nextcloud, und `ssl.create_default_context` wirft `FileNotFoundError` fuer eine Datei, die noch nicht da ist. Zwischen "Deploy-Daemon startet den Container" und "Datei ist hineinkopiert" liegt ein Fenster, das dieser Lauf nicht schliessen kann. Er haengt die Wurzel deshalb an das Vertrauensbuendel des Images, was derselbe Mechanismus ohne das Fenster ist.
- **Die Registrierungsnutzlast wird gelesen, nicht kopiert.** `json_info` wird zur Laufzeit aus `scripts/bootstrap_exapp.sh` extrahiert und ausgefuehrt. Eine Kopie der dreizehn Routen haette gedriftet, und eine gedriftete Wiederherstellung ist eine Topologie, der niemand wieder trauen kann.
- **Messung 2 und 3 fragen dreimal statt einmal.** Der Werkzeugpfad wird im Heimatverzeichnis des handelnden Kontos aufgebaut, also faellt der erste Versuch in der eigenen Wurzel; der zweite nennt das fremde Heimatverzeichnis ausdruecklich, der dritte sucht nach dem Marker. Erst zusammen decken sie die Frage ab, die spike-dav mit einem rohen DAV-Aufruf stellen konnte.
- **Der eine Verweis steht in `docs/standalone-oauth.md`.** Die offene Ankuendigung dort verspricht ein *Einrichtungsdokument*, und das ist Plan 24-09. Was sie nicht verspricht und ein Leser trotzdem braucht, ist der Ort der Messung; genau dieser Satz steht jetzt dort.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `SSL_CERT_FILE` nicht als Deploy-Variable gesetzt**
- **Found during:** Task 1
- **Issue:** Der Plan verlangt "der ExApp-Container bekommt `SSL_CERT_FILE` auf das selbst signierte Zertifikat gesetzt". Die Variable wird beim Erzeugen des Containers gesetzt, das Zertifikat kann erst danach hinein. httpx baut den SSL-Kontext beim Bauen jedes Clients, und `ssl.create_default_context(cafile=...)` wirft fuer eine fehlende Datei; der erste ausgehende Aufruf des Programms waere also ein Absturz gewesen.
- **Fix:** A6 ist als eigener Messpunkt genau so gefahren, wie der Plan ihn beschreibt (Rohausgabe im Dokument und unten). Der Lauf selbst haengt die Wurzel der Test-CA an das Vertrauensbuendel des Images, das httpx ohne die Variable ohnehin liest.
- **Files modified:** `scripts/exchange_evidence.py`
- **Verification:** `200 application/json {"keys": [...]}` aus dem ExApp-Container; der Lauf holt den Schluesselsatz danach im Betrieb.
- **Committed in:** `c92c1f1`

**2. [Rule 3 - Blocking] Die Registrierungsnutzlast reist ueber stdin**
- **Found during:** Task 1
- **Issue:** Die Wohlbekannt-Routen der Nutzlast tragen je vier Backslashes. Eine MSYS-Shell auf Windows zerlegt die Kommandozeile, die sie bekommt, noch einmal und frisst eine Ebene davon; das Heredoc frisst die zweite, und die Nutzlast erreicht AppAPI mit dem ungueltigen JSON-Escape `\.`.
- **Fix:** Das Skript reist ueber `bash -s` auf stdin. Der Grund steht als Kommentar an der Stelle.
- **Files modified:** `scripts/exchange_evidence.py`
- **Verification:** Die Registrierung antwortet "ExApp mcp_connector successfully registered", dreizehn Routen unveraendert.
- **Committed in:** `c92c1f1`

**3. [Rule 2 - Missing Critical] Messung 2 und 3 fragen dreimal**
- **Found during:** Task 2
- **Issue:** Der erste Lauf zeigte, dass der Werkzeugpfad im Heimatverzeichnis des handelnden Kontos aufgebaut wird: alices Versuch landete auf `/remote.php/dav/files/alice/<bobs Dateiname>`. Das ist ein `404`, aber es ist nicht derselbe Beweis wie in `spike-dav.md`, wo der absolute DAV-Pfad des anderen Kontos gefragt wurde.
- **Fix:** Je Richtung drei Versuche: der bekannte Name, der ausdrueckliche Weg ueber `/../<anderes Konto>/...` und eine Suche nach dem Marker. Alle drei sind abgewiesen.
- **Files modified:** `scripts/exchange_evidence.py`, `docs/exchange-evidence.md`
- **Verification:** Rohausgabe beider Messbloecke im Dokument.
- **Committed in:** `c92c1f1`, `46887e8`

**4. [Rule 1 - Bug] Messung 4 als roher HTTP-Aufruf statt als MCP-Sitzung**
- **Found during:** Task 2
- **Issue:** Mit zwei `Authorization`-Headern wird die Anfrage in einer der beiden Reihenfolgen an der Transportgrenze abgewiesen. Der MCP-Client des SDK verhandelt vor dem Aufruf, wirft dann ueber den Handschlag, und der Statuscode ist weg: die Messung haette den Client gemessen und nicht die Grenze.
- **Fix:** Ein `tools/call` als eine POST-Anfrage der staatenlosen Aera 2026-07-28, mit dem `_meta`-Umschlag und den beiden Kopfzeilen `mcp-method` und `mcp-name`, die der Server verlangt (beides gemessen, nicht gelesen). Der Statuscode bleibt damit sichtbar.
- **Files modified:** `scripts/exchange_evidence.py`
- **Verification:** `HTTP 401` im einen Fall, `HTTP 200` mit dem Inhalt im anderen.
- **Committed in:** `c92c1f1`

**5. [Rule 2 - Missing Critical] Jeder Messblock steht fuer sich**
- **Found during:** Task 2
- **Issue:** Der erste Lauf brach in Messung 4 ab, und damit blieben die drei Log-Bloecke, der gemischte Lauf, die Audit-Ausgaben **und die Wiederherstellung** ungefahren. Ein Messlauf, der beim ersten Ueberraschungsfall die Topologie armiert stehen laesst, ist der schlechtere der beiden Fehler.
- **Fix:** `guarded()` meldet einen gefallenen Block als Ergebnis und laeuft weiter; die Wiederherstellung steht in einem `finally`.
- **Files modified:** `scripts/exchange_evidence.py`
- **Verification:** Der Lauf endet mit Exitcode 0 und der Gegenprobe der Wiederherstellung.
- **Committed in:** `c92c1f1`

---

**Total deviations:** 5 auto-fixed (3 blockierend, 2 fehlende kritische Funktionalitaet)
**Impact on plan:** Kein Scope Creep. Vier der fuenf sind Korrekturen am Messaufbau, die der erste Lauf erzwungen hat; die fuenfte ist die Haltbarkeit des Laufs selbst.

## Issues Encountered

- **Der Worktree brauchte ein eigenes venv.** `uv run` legte zunaechst ein leeres an und fand `ruff` nicht; `uv sync --all-extras` im Worktree hat das geloest. Ohne eigenes venv haette der Lauf ausserdem den Quellbaum des Hauptcheckouts importiert.
- **MSYS-Pfadumwandlung schlaegt bei `docker exec -e SSL_CERT_FILE=/tmp/...` zu**: der Wert kommt im Container als `C:/Users/.../Temp/...` an. Im Skript spielt das keine Rolle, weil `subprocess` ohne Shell aufruft; von Hand braucht es `MSYS_NO_PATHCONV=1`.
- **Der Aufbau des rohen MCP-Aufrufs war dreimal falsch, bevor er richtig war** (`params._meta`, dann `mcp-method`, dann `mcp-name`). Jede Stufe hat der Server benannt; die drei Befunde stehen als Kommentar im Skript.

## Verification

Alle Gates gruen vor jedem Commit, der letzte Stand:

| Pruefung | Ergebnis |
|----------|----------|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 271 files already formatted |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `uv run vulture src scripts vulture_whitelist.py` | ohne Befund |
| `uv run pytest` | 4359 passed, 33 skipped, 168 deselected |
| `uv run pytest tests/unit/test_exapp_env_setup.py tests/unit/test_docs_audit_truth.py -q` | gruen |
| `grep -c "NC_MCP_EXCHANGE_ISSUER" docs/exchange-evidence.md` | 1 |
| `grep -c "urn:mcp-connector:token-exchange" docs/exchange-evidence.md` | 3 |
| Em-Dashes und Nicht-ASCII in `docs/exchange-evidence.md` | 0 |
| Verweise auf die Messdatei in der Doku | genau 1 (`docs/standalone-oauth.md`) |
| `git status --short` | leer, kein Schluessel und kein Token im Baum |
| `docker exec nc_app_mcp_connector printenv \| grep -c NC_MCP_EXCHANGE` | 0 |
| `occ mcp_connector:exchange:check --token=probe` | "the token exchange path is not configured on this instance" |

## Die Rohausgabe, die der Plan im SUMMARY verlangt

**A6, der Schluesselsatz ueber HTTPS aus dem ExApp-Container:**

```
== assumption A6: the key set over HTTPS, from inside the ExApp container ==
200 application/json {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid"
```

**Die armierte Umgebung:**

```
NC_MCP_AUDIT_LOG=yes
NC_MCP_EXCHANGE_AZP=mcp-evidence-orchestrator
NC_MCP_EXCHANGE_ENABLED=yes
NC_MCP_EXCHANGE_ISSUER=https://test-issuer/realms/evidence
NC_MCP_PUBLIC_URL=http://127.0.0.1:8082/exapps/mcp_connector
```

**Die beiden Zeilen, auf die es ankommt (Apache-Zugriffslog von `nc35-nc`):**

```
"PROPFIND /remote.php/dav/files/alice/exchange-bob-1a377c064b.md HTTP/1.1" 404
"PROPFIND /remote.php/dav/files/bob/exchange-alice-1a377c064b.md HTTP/1.1" 404
```

**Der gemischte Lauf in der Kette:**

```
495 - 2026-09-24T06:14:20Z - u:alice - files_read - - mcp-evidence-orchestrator - ok - - 78 - path - -
494 - 2026-09-24T06:14:19Z - u:alice - files_read - exchange evidence - - ok - - 93 - path - -
```

```
{"checked":true,"chains":5,"entries":495,"tombstones":0,"explained_entries":0,"used_bytes":147456,"sweepable_entries":476,"over_bound_unevictable":false,"broken":false,"findings":[]}
```

**Die Abweisungskette:**

```
493 - 2026-09-24T06:14:17Z - x:exchange - - - - - rejected - exchange_issuer - - - - 1
```

**Die Wiederherstellung, live gegengeprueft:**

```
ExApp mcp_connector successfully registered.
mcp_connector (MCP Connector): 0.2.1 [enabled]
the token exchange path is not configured on this instance, so there is nothing to hold a
token against. Nothing was checked and nothing about the token follows from that.
```

## Threat Model Coverage

| Threat ID | Disposition | Wie erfuellt |
|-----------|-------------|--------------|
| T-24-31 (Elevation of Privilege) | mitigate | Messung 2 und 3, je drei Wege, alle abgewiesen; `404` im Zugriffslog, dazu die Impersonationszeile mit dem aufgeloesten Konto |
| T-24-32 (Spoofing, Confused Deputy) | **nicht bestaetigt** | Messung 4 hat ihre Erwartung widerlegt. Der Befund steht oben und im Dokument; keine Rechteausweitung, aber eine Aussage, die in die Einrichtungsdoku gehoert |
| T-24-10 (Information Disclosure) | mitigate | Schluessel und Tokens leben im Prozess des Laufs; `git status --short` zeigt nur die vier Dateien des Plans |
| T-24-33 (Repudiation, falsche Grenze) | mitigate | `NC_MCP_EXCHANGE_ISSUER` und `urn:mcp-connector:token-exchange` stehen beide in der Rohausgabe der Datei |
| T-24-34 (Tampering, selbst signiertes Zertifikat) | accept | Nur in der lokalen Wegwerf-Topologie; die CA wird beim Neuanlegen des Containers neu erzeugt, und das Vertrauen lebt in einem Container, den die Wiederherstellung ersetzt |
| T-24-SC (Supply Chain) | accept | Diese Phase installiert kein Paket; `pyproject.toml` und `uv.lock` sind im Diff nicht enthalten |

## Known Stubs

Keine. Jede Zahl und jede Zeile dieses Plans stammt aus einem gefahrenen Kommando.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: auth-precedence | src/mcp_connector/exapp/middleware.py | Gemessen, nicht neu gebaut: eine von HaRP aufloesbare Nextcloud-Anmeldung entscheidet die handelnde Identitaet vor einem getauschten Token, und die Antwort sagt das nicht. Fuer den Exchange-Pfad ist das eine Aussage, die ein Betreiber kennen muss (siehe Befund oben) |

## Next Phase Readiness

**Fuer Plan 24-09 (Doku, EXCH-08):**

- Der Verweis auf `docs/exchange-evidence.md` ist gesetzt, **genau einmal**, in `docs/standalone-oauth.md`. `docs/token-exchange.md` soll ihn **nicht** noch einmal setzen; wenn 24-09 ihn dort lieber haette, muss er in `standalone-oauth.md` weichen.
- Der Befund aus Messung 4 gehoert in die ehrliche Grenzbeschreibung von `docs/token-exchange.md`. Der Satz dafuer steht ausformuliert im Abschnitt "Befund" oben und im Dokument.
- Die Voreinstellungen, gegen die gemessen wurde, sind die dokumentierten: Schluesselsatz = Issuer plus `/protocol/openid-connect/certs`, Audience = oeffentliche URL plus `/mcp`, Konto-Claim `sub`, Profil `account_id_v1`. Wer sie in der Doku nennt, nennt damit den gemessenen Fall.
- Aus 24-06 unveraendert gueltig: keine gemessene Obergrenze unterhalb von `MAX_TOKEN_BYTES = 8192` in die Doku.

**Topologiezustand:** die NC-35-Topologie laeuft, der Dienst `test-issuer` laeuft mit, die ExApp ist als 0.2.1 mit der Bootstrap-Registrierung eingetragen und traegt keine `NC_MCP_EXCHANGE_*`-Variable. Ein erneuter Lauf braucht nur `uv run --no-sync python scripts/exchange_evidence.py --env-file .env.nc35`.

Keine Blocker. `.planning/STATE.md` und `.planning/ROADMAP.md` wurden von diesem Agenten bewusst nicht angefasst.

## Self-Check: PASSED

Beide neuen Dateien existieren (`docs/exchange-evidence.md`, `scripts/exchange_evidence.py`), beide geaenderten sind im Diff (`compose.nc35.yml`, `docs/standalone-oauth.md`), und alle drei Commits stehen in der Historie dieses Worktrees (`c92c1f1`, `46887e8`, `cb61989`, auf `de95424` aufgesetzt). Der Arbeitsbaum ist sauber.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Plan: 08*
*Completed: 2026-09-24*

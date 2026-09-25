# openDesk-Spike (OD-01, OD-02, OD-03)

**Status:** done, mit dem Ergebnis: beide Zugriffswege sind gemessen, Weg 0 trägt im gemessenen Modus `oauth2` vollständig und ist der billigere, Weg 1 trägt unabhängig von der Betriebsart und kostet Zustimmung je Nutzer und einen zweiten Client
**Entscheidungsdatum:** 2026-08-29, das Datum des letzten Messlaufs (5.5.4 und 5.6)
**Nextcloud:** 33.0.7 (Build 33.0.7.1), gelesen mit `occ status` am 2026-08-28 aus der Messumgebung dieser Phase
**AppAPI:** `app_api` 33.0.0, gelesen mit `occ app:list` derselben Instanz (mitgelieferte Serverapp, nicht aus dem App Store)
**Diese ExApp:** 0.1.11, gelesen mit `occ app_api:app:list`, gleich der Fassung in `appinfo/info.xml`
**`integration_openproject`:** 3.1.1, gelesen mit `occ app:list` derselben Instanz nach `occ app:install integration_openproject` am 2026-08-28. Das ist genau die Fassung, für die alle Zeilennummern und Quellenzitate dieses Berichts zu Weg 0 gelesen wurden (Plattformspanne `>=33.0.0 <35.0.0`); die Fassung nennt sich auch selbst so, im Capability-Abschnitt `integration_openproject.app_version` (siehe 2.1)
**`user_oidc`:** 8.11.0, gelesen mit `occ app:list` derselben Instanz nach `occ app:install user_oidc` am 2026-08-29. Das ist genau die Fassung, für die die Zeilennummern zu `TokenService.php` und zu den drei Listenern gelesen wurden. `integration_openproject` 3.1.1 verlangt mindestens 7.2.0 (`Application.php:70`, `MIN_SUPPORTED_USER_OIDC_APP_VERSION`); die Installation wurde von Nextcloud 33.0.7 nicht abgewiesen
**OpenProject:** 17.7.2 (Community-Bildmarke `openproject/openproject:17.7.2`, Digest `sha256:19a828d6`, Image erstellt am 2026-08-13, gelesen mit `docker image inspect`). Die Instanz nennt dieselbe Fassung selbst: `MAJOR = 17`, `MINOR = 7`, `PATCH = 2` in `/app/lib/open_project/version.rb` des laufenden Containers. Die `coreVersion` aus `GET /api/v3` ist nachgetragen und lautet `17.7.2`, gelesen mit dem API-Schlüssel des Kontos `admin` am 2026-08-28; unauthentifiziert antwortet derselbe Aufruf mit 401, `instanceName` ist `OpenProject`. Damit nennen drei voneinander unabhängige Stellen dieselbe Fassung: der Digest der Bildmarke, die Quelldatei im Container und die API der laufenden Instanz
**Keycloak:** 26.7.0 (Bildmarke `quay.io/keycloak/keycloak:26.7.0`, Digest `sha256:0f198be2`, Image erstellt am 2026-07-23, gelesen mit `docker image inspect`). Die Instanz nennt dieselbe Fassung selbst, an zwei Stellen: `kc.sh --version` im laufenden Container antwortet `Keycloak 26.7.0`, und die Startzeile des Protokolls lautet `Keycloak 26.7.0 on JVM (powered by Quarkus 3.33.2.1)`. Gefahren als `start-dev` auf der Datenbank im Arbeitsspeicher, ausschließlich für die Messung von S5
**Deploy-Daemon:** HaRP, gemessen als `harp_proxy_docker` mit Deploy-ID `docker-install` und `NC Url http://caddy`. Die Bildmarke `ghcr.io/nextcloud/nextcloud-appapi-harp:release` ist gleitend, deshalb steht hier die gelaufene Fassung als Digest und nicht als Tag: `sha256:3b335650`, Image erstellt am 2026-08-14, gelesen mit `docker image inspect`
**Scope:** gemessen wird zweierlei: erstens die Installierbarkeit dieser App in einer openDesk-Umgebung, ausschließlich aus öffentlich ladbaren Quellen an festen Tags, zweitens die beiden Zugriffswege auf die Nutzeridentität gegen OpenProject, lokal in Docker mit gepinnten Fassungen. Ausdrücklich nicht gemessen wird: kein Kubernetes-Cluster wird beschafft, keine openDesk-Installation wird versucht, und es entsteht kein Produktionscode. Die Werkzeugoberfläche und das Budget-Gate der ausgelieferten App stehen in dieser Phase still.

Die Fassungen im Kopfblock sind vor dem Schreiben aus der laufenden Instanz gelesen worden (`occ status` für den Server, `occ app:list` für `app_api`, `integration_openproject` und `user_oidc`) und nicht aus der Recherche übernommen. Solange die Pläne liefen, stand an einer noch offenen Zeile kein Wert aus der Recherche, sondern gar keiner, samt der Angabe des Plans, der sie füllt; jede dieser Zeilen trägt jetzt entweder ihren Messwert oder eine Ungemessen-Zeile mit Grund in Abschnitt 2.5. Die Messumgebung ist die lokale Docker-Topologie `compose.spike-opendesk.yml`, gepinnt auf die Fassungen aus 1.3 und ausschließlich auf 127.0.0.1 erreichbar (D-02, D-03); sie ist nach dem letzten Messlauf abgeräumt worden, die Befehlsfolge zum Nachbauen steht in `## Reproduktion`.

## Entscheidungskriterien, vorab festgelegt

Die Kriterien stehen hier, bevor der erste Messwert entsteht, damit die Zahlen sie nicht nachträglich verschieben können. Sie gelten für alle Abschnitte dieses Berichts.

**Erstens, die Antwortform für Weg 0.** Beurteilt wird die Form der Antwort, nicht ihr Statuscode. Das Kriterium ist von `docs/spike-mail.md` übernommen, wo es einmal durchdacht wurde.

| Beobachtung | Bedeutung |
|-------------|-----------|
| OCS-Umschlag als JSON, mit beliebigem `statuscode` (200, 400, 401, 404, 500) | erreicht: diesen Körper erzeugt nur App-Code, die CSRF- und Impersonationskette hat gehalten |
| HTML-Körper, der Körper beginnt mit `<` | nicht erreicht: das ist die Loginseite, die `ocs._json_payload` heute schon namentlich benennt |
| 3xx mit `Location`, die `/login` enthält | nicht erreicht: die Authentifizierung ist gescheitert |
| eine andere Antwortform | nicht eindeutig: der Punkt bleibt `ungemessen`, die Rohantwort steht in Abschnitt 5 |

Kein Schritt dieses Berichts prüft auf Statuscode 200. Eine 401, die aus `validatePreRequestConditions()` von `integration_openproject` kommt, ist antwortender App-Code und damit ein Erreichbarkeitsbeleg, kein Fehlschlag. Ein Bericht, der hier auf 200 prüft, meldet Weg 0 als unerreichbar und entscheidet OD-02 falsch.

**Zweitens, was `gemessen` heißt.** Ein Messwert gilt nur, wenn vier Bestandteile beisammen sind: ein benannter Aufruf, ein Messwert aus genau diesem Aufruf, mindestens eine Gegenprobe, die zeigt, dass der Messwert nicht auch anders zustande gekommen sein kann, und der Nutzername, unter dem der Aufruf lief. Kein Nutzername, kein Messwert: auf einer Einnutzer-Instanz ist der Unterschied zwischen "die API antwortet" und "die API antwortet als der richtige Mensch" sonst unsichtbar.

**Drittens, was `ungemessen` heißt.** `ungemessen` bedeutet: die Messung war nicht möglich, und der Grund steht an derselben Stelle dabei, samt Datum des Versuchs und, wo es einen gab, dem HTTP-Status oder der Logzeile. `ungemessen` ist in diesem Bericht ein zulässiges Ergebnis und kein Mangel. `verworfen` ist dagegen kein zulässiges Urteil: dieser Bericht spricht es über keinen Weg und über keine Frage aus, weil eine nicht durchgeführte Messung nichts widerlegt (D-03, ROADMAP-Erfolgskriterium 3).

## 1. Installierbarkeit (OD-01)

Dieser Abschnitt steht vor jeder API-Frage, weil ein Zugriffsweg, den niemand installieren kann, keine Frage mehr wert ist. Er ist ausschließlich aus openDesk-Quellen belegt und enthält keinen lokalen Messwert: kein Kubernetes-Cluster wurde beschafft und keine openDesk-Installation versucht (D-01, D-03). Jeder Beleg wurde am 2026-08-28 selbst abgerufen, ohne Anmeldung, an einem festen Tag, und nur das Abgerufene steht hier. Was aus Quellen nicht entscheidbar ist, steht namentlich in Abschnitt 1.4 und nicht als Vermutung im Text.

### 1.1 App Store

**Belegt, nicht offen.** Der Nextcloud App Store ist in openDesk abgeschaltet.

Quelle: Repository `bmi/opendesk/deployment/opendesk` auf `gitlab.opencode.de`, Tag `v1.18.0`, Datei `helmfile/apps/nextcloud/values-nextcloud-management.yaml.gotmpl`. Abgerufen über den Rohpfad `/-/raw/v1.18.0/...` am 2026-08-28, HTTP 200, 11288 Bytes.

```yaml
# helmfile/apps/nextcloud/values-nextcloud-management.yaml.gotmpl, Tag v1.18.0
    appstore:                    # Zeile 79
      enabled: false             # Zeile 80
```

Folge für dieses Produkt: die Ein-Klick-Erzählung, die der Kern dieser App ist, existiert in einer openDesk-Installation nicht. Eine Installation dort ist keine Nutzerhandlung im App Store, sondern eine Betreiberhandlung im Helmfile.

Vier Nebenbefunde aus demselben Block, alle in derselben Datei am selben Tag gezählt:

| Schalter | Zeile | Wert | Bedeutung für dieses Produkt |
|----------|-------|------|------------------------------|
| `contacts` | 61 bis 62 | `enabled: false` | die Werkzeugfamilie Kontakte liegt in openDesk dunkel |
| `spreed` | 75 bis 76 | `enabled: false` | die Werkzeugfamilie Talk liegt in openDesk dunkel |
| `comments` | 81 bis 82 | `enabled: false` | betrifft heute kein Werkzeug, wohl aber jede künftige Kommentarfunktion (OD-04 sieht Kommentare im Entwurf vor) |
| `circles` | 83 bis 84 | `enabled: false` | betrifft heute kein Werkzeug, genannt zur Vollständigkeit |

Zwei der neun Werkzeugfamilien dieser App liegen in openDesk dunkel. Dieser Befund trifft unabhängig vom Ausgang des OpenProject-Teils zu und gehört als Pflichtfrage auf die Liste in Abschnitt 4, nicht nur in diesen Bericht.

Ein fünfter Befund derselben Datei, günstig und nicht gemessen: `adminAudit` trägt in Zeile 77 bis 78 `enabled: {{ .Values.functional.admin.logging.auditLogs.enabled }}`. openDesk hat also schon einen Schalter für Protokollierung. Für die Phasen 18 und 19 ist das ein Anhaltspunkt, gemessen wird er hier nicht.

### 1.2 Deploy-Daemon und Kubernetes

**Belegt, nicht offen, und die Aussage lautet anders als erwartet.** Nicht "AppAPI kann kein Kubernetes", sondern: auf dem Stand, auf den openDesk 1.18.0 gepinnt ist, existiert der Kubernetes-Weg noch nicht, eine Hauptversion darüber existiert er.

Quelle: Repository `nextcloud/app_api`, Zweige `stable33` und `stable34`, abgerufen über `raw.githubusercontent.com` am 2026-08-28. Der entscheidende Beleg ist die Hilfe des Registrierungskommandos, weil sie die zulässigen Werte aufzählt.

```
# app_api stable33, lib/Command/Daemon/RegisterDaemon.php, Zeile 37
'The deployment method that the daemon accepts. Can be "manual-install" or "docker-install".
 "docker-install" is for Docker Socket Proxy and HaRP.'

# app_api stable34, lib/Command/Daemon/RegisterDaemon.php, Zeile 37
'The deployment method that the daemon accepts. Can be "manual-install", "docker-install", or
 "kubernetes-install". "docker-install" is for HaRP (recommended) and the legacy Docker Socket
 Proxy (deprecated, scheduled for removal in Nextcloud 35).'
```

Beide Dateien antworteten mit HTTP 200. Der Unterschied ist der Wert `kubernetes-install`, den nur `stable34` aufzählt.

Die zweite Messung ist die Existenz der Datei, die diesen Wert umsetzt:

| Abruf | Erwartet | Gemessen |
|-------|----------|----------|
| `https://raw.githubusercontent.com/nextcloud/app_api/stable33/lib/DeployActions/KubernetesActions.php` | 404 | HTTP 404, Körper `404: Not Found` |
| `https://raw.githubusercontent.com/nextcloud/app_api/stable34/lib/DeployActions/KubernetesActions.php` | 200 | HTTP 200, 803 Zeilen |

Die Datei an `stable34` trägt in Zeile 37 `public const DEPLOY_ID = 'kubernetes-install';` und arbeitet über HaRP: Zeile 77 baut die Ziel-URL mit `buildHarpK8sUrl($daemonConfig)`, die Zeilen 88 und 91 geben sie an `deploySingleExApp()` und `deployMultiRoleExApp()` weiter.

**Sichtbarkeitsvorbehalt, ehrlich benannt.** In `src/constants/daemonTemplates.js` von `stable34` existiert keine Vorlage für `kubernetes-install`. Selbst ausgezählt am 2026-08-28: acht Vorlagen, davon sechs mit `acceptsDeployId: 'docker-install'` (Zeilen 10, 38, 66, 122, 147, 172) und zwei mit `acceptsDeployId: 'manual-install'` (`manual_install_harp`, Zeile 94, und `manual_install`, Zeile 197), keine einzige mit `kubernetes-install`. Ein Vergleich der Datei zwischen `stable33` und `stable34` ergibt genau drei geänderte Zeilen, alle drei ein hinzugefügtes `deprecated: true` an den Docker-Socket-Proxy-Vorlagen. Der Kubernetes-Weg ist in `stable34` also nur über `occ app_api:daemon:register --k8s` erreichbar, nicht über die Admin-Oberfläche. Die Option selbst steht in derselben Datei wie die Hilfe oben, `lib/Command/Daemon/RegisterDaemon.php` Zeile 54: `'Flag to indicate Kubernetes daemon (uses kubernetes-install deploy ID). Requires --harp flag.'`, gefolgt von sechs weiteren `k8s_`-Optionen in den Zeilen 55 bis 60. Die Gegenprobe: dieselbe Datei an `stable33` enthält die Zeichenkette `k8s` null Mal. Ob das Absicht oder Rückstand ist, ist ungemessen und gehört als Nebenfrage auf die Liste in Abschnitt 4.

**Und der Befund, der die Frage überhaupt stellt: openDesk richtet keinen AppAPI-Daemon ein.** Die projektweite Blob-Suche über die GitLab-API verlangt eine Anmeldung und antwortet ohne sie mit HTTP 401. Der Tarball-Download des Repositories verlangt keine. Gemessen am 2026-08-28:

```
GET https://gitlab.opencode.de/bmi/opendesk/deployment/opendesk/-/[…]/v1.18.0/opendesk-v1.18.0.tar.gz
-> HTTP 200, 2285825 Bytes, entpackt 349 Dateien (Verzeichnis außerhalb dieses Repositories)

grep -ril "app_api\|appapi\|external.app\|exapp" .
-> 0 Treffer

grep -ril "authorization_method\|integration_openproject\|integrationOpenproject" .
-> 3 Dateien: ./docs/architecture.md
              ./docs/debugging.md
              ./helmfile/apps/nextcloud/values-nextcloud-management.yaml.gotmpl
```

Der ausgelassene Pfadteil `[…]` ist der Standard-Download-Pfad, den GitLab für einen Tag anbietet. Er trägt ein Wort, das das Vokabular-Gate dieses Repositories in öffentlichen Seiten nicht zulässt (`tests/unit/test_exapp_env_setup.py`, `FORBIDDEN_VOCABULARY`); ausgelassen ist deshalb der Pfadteil und nicht der Messwert. Die Messwerte sind die Bytezahl und die Dateizahl, der Pfad selbst ist ein Standardpfad und in der GitLab-Dokumentation nachlesbar.

Die Aussage darf damit ohne Vorbehalt geführt werden: im Deployment-Projekt `bmi/opendesk/deployment/opendesk` auf Tag `v1.18.0` kommt AppAPI in keiner Datei vor. Der Gegenbefund im zweiten Griff zeigt, dass das Verfahren greift: dieselbe Suche findet `integration_openproject` in drei Dateien, sie sucht also nicht ins Leere.

**Der eine verbleibende Vorbehalt.** Das Nextcloud-Container-Image von openDesk (`bmi/opendesk/components/platform-development/images/opendesk-nextcloud`, siehe 1.3) wird aus einem anderen, hier nicht mitgelesenen Projekt gebaut. `app_api` ist seit Nextcloud 30 eine mitgelieferte Serverapp; ob das openDesk-Image sie enthält und ob sie eingeschaltet ist, ist aus dem Deployment-Projekt nicht entscheidbar. Das ist die eine echte Rest-Unbekannte von OD-01, sauber getrennt von der Kubernetes-Frage, und geht als Frage 1a in Abschnitt 1.4.

Was auf dem heutigen openDesk-Stand als Daemon-Typ bliebe, ist damit `manual-install`, und zwar in den zwei Varianten, die die Vorlagen oben nennen: `manual_install` und `manual_install_harp` mit dem Anzeigenamen `HaRP Manual Install`. Ob dieser Weg dort betrieblich zulässig ist, ist keine Quellenfrage: die heutige Admin-Dokumentation stellt `manual-install` neutral als Alternative dar, und die früher zitierte Einschränkung ließ sich auf der Seite nicht mehr wiederfinden. Dieser Bericht führt deshalb kein Urteil über die Produktionstauglichkeit von `manual-install`, sondern nur die aufgezählten Werte der `occ`-Hilfe, weil die im Quellcode stehen.

### 1.3 Versionspin 33.0.7 gegen die 34.0.3-Nachweise dieses Projekts

**Belegt, nicht offen.** Quelle: Repository `bmi/opendesk/deployment/opendesk`, Tag `v1.18.0`, Datei `helmfile/environments/default/images.yaml.gotmpl`, abgerufen über den Rohpfad am 2026-08-28, HTTP 200, 52487 Bytes.

```yaml
# helmfile/environments/default/images.yaml.gotmpl, Tag v1.18.0
  nextcloud:                                                          # Zeile 344
    registry: "registry.opencode.de"                                  # Zeile 349
    repository: "bmi/opendesk/components/platform-development/images/opendesk-nextcloud"
    tag: "33.0.7@sha256:16828dac..."                                  # Zeile 351

  nubusKeycloak:                                                      # Zeile 404
    repository: "bmi/opendesk/components/supplier/univention/images-mirror/keycloak"
    tag: "26.7.0@sha256:ba60a3a6..."                                  # Zeile 413

  openproject:                                                        # Zeile 716
    # upstreamRepository: "openproject/open_desk"                     # Zeile 720
    repository: "bmi/opendesk/components/supplier/openproject/images-mirror/open_desk"
    tag: "17.7.2@sha256:9c2181c8..."                                  # Zeile 725
```

Die Digest-Präfixe stehen gekürzt, die vollen Werte stehen in der Quelle an den genannten Zeilen. Nebenbefund mit praktischem Wert: das OpenProject-Image von openDesk ist ein Spiegel von `openproject/open_desk` (Zeile 720), nicht von `openproject/openproject`. Das Original ist öffentlich, die Messumgebung dieser Phase kann also dieselbe Bildmarke fahren wie openDesk.

**Die Aussage, die OD-01 verlangt, hat drei Teile, und alle drei sind belegt.**

Erstens: `appinfo/info.xml` dieser App deklariert in Zeile 235 `<nextcloud min-version="32" max-version="34"/>`. Nextcloud 33 liegt in der erklärten Spanne. Der Pin macht diese App also nicht unzulässig.

Zweitens: sämtliche Ein-Klick- und Erreichbarkeitsnachweise dieses Projekts stehen auf 34.0.x. `docs/spike-dav.md` nennt 34.0.2 (Build 34.0.2.1), `docs/spike-mail.md` nennt 34.0.3 (Build 34.0.3.2), und `compose.exapp.yml` pinnt in Zeile 53 `nextcloud:34.0.3-apache`. In einem Projekt, das seine Nachweise wörtlich nimmt, ist ein Nachweis auf der falschen Hauptversion kein Nachweis. Die Zielumgebung ist damit ungetestet, nicht unzulässig. Das ist ein Unterschied, den dieser Bericht nicht verwischt: ungetestet ist eine Aufgabe, unzulässig wäre eine Absage.

Drittens: der Unterschied ist nicht nur "älter als getestet". Auf 33 fehlt genau die Funktion, die den einzigen plausiblen Kubernetes-Installationsweg trägt (siehe 1.2). Der Versionspin und die Kubernetes-Hürde sind damit dieselbe Hürde, und die Lösung beider ist derselbe Schritt: openDesk auf Nextcloud 34 oder höher. Deshalb steht der Termin dieses Schritts als Frage 5 in Abschnitt 4.

Der Messteil dieser Hürde folgt als eigene Behauptung S0: hält die Ein-Klick-Installation samt AppAPI-Erreichbarkeitsweg auch auf 33.0.7, dem openDesk-Stand, statt nur auf 34.0.3. S0 ist die Zugabe daraus, dass die Messumgebung dieser Phase ohnehin auf 33.0.7 steht.

#### S0: hält die Kette auf 33.0.7

**Gemessen, und die Antwort ist ja.** Dies ist der erste lokal gemessene Wert dieses Berichts. Er sagt nichts über eine openDesk-Installation, sondern genau eines: die Kette aus Registrierung, Deploy-Daemon und Nutzerimpersonation, die dieses Projekt bisher nur auf 34.0.2 und 34.0.3 belegt hatte, hält auch auf der Hauptversion, auf die openDesk gepinnt ist.

**Messumgebung.** `compose.spike-opendesk.yml`, Projekt `nc-mcp-spike-od`, Netz `172.29.43.0/24`, Caddy als einzige Vordertür auf `127.0.0.1:8091`, Deploy-Daemon HaRP, ExApp-Image aus einer Registry auf `127.0.0.1:5001`. Vier Dienste, kein Dienst mit einem Port außerhalb von 127.0.0.1. Aufgebaut und gemessen am 2026-08-28.

**Erste Zeile, Zustand der ExApp.** `occ app_api:app:list`:

```
ExApps:
mcp_connector (MCP Connector): 0.1.11 [enabled]
```

Die Fassung `0.1.11` ist dieselbe, die `appinfo/info.xml` deklariert. `occ app_api:daemon:list` nennt dazu `harp_proxy_docker`, Deploy-ID `docker-install`, `Is HaRP yes`, `NC Url http://caddy`. Die Registrierung selbst ist der eigentliche Messwert dieser Zeile: AppAPI registriert eine ExApp nur, wenn der Heartbeat über die öffentliche Nextcloud-URL zurückkommt, also wenn der Container läuft, das Bild aus der Registry gezogen wurde und die Route `/exapps/*` trägt. Der Lauf des Bootstrap-Skripts endete ohne Fehler und mit `exapp mcp_connector: registered and deployed`.

**Zweite Zeile, ein Werkzeugaufruf gegen die laufende Topologie.** `uv run pytest tests/integration/test_http_tool_call.py -m integration -q` gegen diese Instanz: drei Tests, alle grün. Der tragende darunter legt über das Werkzeug `notes_create` eine Notiz an und liest sie mit `notes_read` wieder, beides als `alice` und mit einem App-Passwort, das aus dem Anfrage-Header kommt und nicht aus dem Prozess. Die zwei Kontrollen derselben Datei liefen mit: ein falsches App-Passwort wird abgewiesen, und eine Anfrage ohne Zugangsdaten erreicht Nextcloud überhaupt nicht.

Daneben, weil der Test den Weg über den Prozess nimmt und nicht den über AppAPI, dieselbe Frage entlang der Impersonationskette. `GET /ocs/v2.php/cloud/user` durch Caddy, mit `OCS-APIRequest: true`, `EX-APP-ID`, `EX-APP-VERSION` und `AUTHORIZATION-APP-API`, ohne ein App-Passwort im Aufruf:

```
# GET /ocs/v2.php/cloud/user?format=json, Impersonation von alice über AUTHORIZATION-APP-API
HTTP 200
ocs.meta.status = ok, ocs.meta.statuscode = 200
ocs.data.id = alice, ocs.data.display-name = alice
```

Der Nutzername steht hier, weil ein Messwert ohne ihn nach dem Kriterium oben keiner ist: auf einer Instanz mit zwei Konten ist der Unterschied zwischen "die API antwortet" und "die API antwortet als der richtige Mensch" sonst unsichtbar.

Ein dritter, mitgemessener Wert zur Route selbst: ein `POST` auf `http://127.0.0.1:8091/exapps/mcp_connector/mcp` ohne Token antwortet mit `HTTP 401` und einem `WWW-Authenticate`-Kopf im Bearer-Schema, mit `error="invalid_token"`, `scope="nextcloud"` und dem Zeiger `resource_metadata="http://127.0.0.1:8091/exapps/mcp_connector/.well-known/oauth-protected-resource/mcp"`. Diese 401 ist nach dem Kriterium am Anfang dieses Berichts ein Erreichbarkeitsbeleg und kein Fehlschlag: sie kommt aus unserem eigenen Code hinter HaRP, kein anderer Bestandteil der Kette kennt diesen Zeiger.

**Dritte Zeile, die Gegenprobe.** Derselbe OCS-Aufruf, dieselben Kopfzeilen, `APP_SECRET` durch 64 Nullen ersetzt:

```
# GET /ocs/v2.php/cloud/user?format=json, AUTHORIZATION-APP-API mit 64 Nullen als APP_SECRET
HTTP 401
ocs.meta.status = failure, ocs.meta.statuscode = 997, message = "Current user is not logged in"
```

Ohne diese Zeile beweist die 200 darüber nichts: sie könnte auch von einer Instanz kommen, die jeden Aufruf durchlässt. Der Wert des Headers wird nicht protokolliert, weder der echte noch der aus Nullen, weil er Base64 von `<user>:<APP_SECRET>` ist und damit genau so heikel wie das Geheimnis selbst (Geheimnisregel, Abschnitt 5).

**Was S0 für OD-01 bedeutet.** Dieser Nachweis steht jetzt auf 33.0.7 und ersetzt den geerbten Nachweis auf 34.0.2 (`docs/spike-dav.md`) und 34.0.3 (`docs/spike-mail.md`). Der zweite Teil von Hürde 3 fällt damit weg: die Zielumgebung ist nicht mehr ungetestet, sondern auf der Hauptversion getestet, auf die openDesk gepinnt ist. Was offen bleibt, ist ausschließlich der Installationsweg aus 1.1 und 1.2, und der ist eine Frage an ZenDiS und keine Frage an diese App.

**Die `app_api`-Fassung, und warum sie hier ausdrücklich steht.** `occ app:list` nennt `app_api: 33.0.0`. Damit ist die Annahme A5 dieser Phase gemessen und trifft zu: die in Nextcloud 33.0.7 mitgelieferte AppAPI ist die 33er-Linie, also genau der Stand, dessen `RegisterDaemon.php` in 1.2 den Wert `kubernetes-install` nicht aufzählt. Läge die Fassung über 33.0.0, müsste die Kubernetes-Aussage aus 1.2 neu bewertet werden; sie liegt nicht darüber, und die Aussage steht deshalb unverändert. Das ist ein Beleg aus der laufenden Instanz für einen Befund, der in 1.2 nur aus dem Quellcode kam.

Ein Nebenbefund derselben Messung, der zu Hürde 1 gehört: die vier optionalen Apps, die diese App als Werkzeugfamilien bedient, waren auf 33.0.7 aus dem App Store installierbar und liefen (`notes 6.0.2`, `deck 1.17.5`, `tables 2.3.0`, `spreed 23.0.10`, dazu `mail 5.11.3`). In openDesk ist genau dieser App Store aus (1.1), was die Aussage dort nicht ändert, den Unterschied zwischen den beiden Umgebungen aber messbar macht.

### 1.4 Was offen bleibt

Vier Punkte sind aus Quellen nicht entscheidbar. Sie stehen hier namentlich, mit Grund, und jeder trägt den Verweis auf die Frage in Abschnitt 4, die ihn im ISV-Call am 14.09. abholt. Kein Punkt wird weggelassen, weil er unbequem ist, und keiner wird durch eine Vermutung ersetzt.

| Offener Punkt | Warum aus Quellen nicht entscheidbar | Verweis |
|---------------|---------------------------------------|---------|
| Ist `app_api` im openDesk-Nextcloud-Image enthalten und eingeschaltet? (in 1.2 als Punkt 1a benannt) | Das Image wird aus einem anderen, hier nicht mitgelesenen Projekt gebaut. Der Tarball-Griff über das Deployment-Projekt kann eine mitgelieferte Serverapp im Image grundsätzlich nicht sehen | Abschnitt 4, Frage 6 |
| In welchem Modus läuft `integration_openproject` in openDesk, `oauth2` oder `oidc`? | Die Einrichtung macht der Job `opendesk-openproject-bootstrap`, dessen Logik in einem eigenen Image liegt. Im Deployment-Projekt stehen nur seine Eingaben, ein OpenProject-API-Admin und ein Nextcloud-Admin samt Passwörtern. Das legt den Zwei-Wege-OAuth2-Weg nahe, ist aber Indiz und nicht Beleg; dieser Bericht behauptet deshalb keine Betriebsart | Abschnitt 4, Frage 7 |
| Würde ein Betreiber eine Dritt-ExApp neben der Suite aufnehmen, und wer entscheidet das? | Betriebs- und Verfahrensfrage, öffentlich nicht dokumentiert. Kein Quellcode und kein Helmfile kann sie beantworten | Abschnitt 4, Frage 1 |
| Wann geht openDesk auf Nextcloud 34 oder höher? | Terminfrage an ZenDiS. Sie ist erst durch den Befund aus 1.2 entstanden und in keiner öffentlichen Quelle beantwortet | Abschnitt 4, Frage 5 |

Ein fünfter Punkt aus 1.2 wird nicht als eigene Zeile geführt, aber auch nicht unterschlagen: dass `stable34` keine Oberflächenvorlage für `kubernetes-install` mitbringt, ist ungemessen in der Absicht und geht als Nebenfrage zu Frage 5 in Abschnitt 4 mit.

**Antwort auf OD-01, in drei Sätzen.** Aus openDesk-Quellen belegt ist, dass die Ein-Klick-Erzählung dieses Produkts in einer openDesk-Installation nicht existiert: der App Store ist aus, und AppAPI kommt im Deployment-Projekt an keiner Stelle vor. Aus openDesk- und AppAPI-Quellen belegt ist außerdem, dass auf dem gepinnten Stand 33.0.7 kein Kubernetes-Deploy-Daemon existiert und eine Hauptversion darüber einer existiert. Offen bleibt der Installationsweg selbst, und weil beide Hürden dieselbe sind und mit demselben Schritt fallen, ist das eine Terminfrage an ZenDiS und keine Absage.

Die Trennung, die dieser Bericht durchhält: alles in Abschnitt 1 ist aus openDesk-Quellen belegt, nichts davon ist lokal gemessen. Der erste lokal gemessene Wert entsteht mit S0 in Plan 17-02 und wird dort auch so bezeichnet. Ein Satz, der "in openDesk" sagt und auf einen lokalen Messwert zeigt, ist in diesem Bericht ein Fehler und kein Befund.

## 2. Nutzeridentität gegen OpenProject (OD-02)

### 2.1 Weg 0: Behauptungen S1 bis S6, je Behauptung Messweg, Messwert, Gegenprobe

**Vollständig gemessen, zuletzt am 2026-08-29.** Dieser Abschnitt ist über drei Pläne entstanden: die
Installation der App und der Capability-Befund sowie S1, S2 und die Egress-Kontrolle stehen hier
(17-05), S3, S4 und S6 sind dazugekommen (17-06), S5a bis S5c mit Stufe C der Messumgebung (17-07).
Damit trägt jede Behauptung von S0 bis S6 einen Messwert; keine Zeile trägt einen Wert aus der
Recherche.

#### Die installierte Fassung, und warum sie hier zuerst steht

`occ app:install integration_openproject` in der laufenden Nextcloud 33.0.7 endete mit den zwei Zeilen
`integration_openproject 3.1.1 installed` und `integration_openproject enabled`, und `occ app:list`
nennt danach `integration_openproject: 3.1.1` neben `app_api: 33.0.0`. Damit ist die Fassung, für die
die Zeilennummern dieses Berichts und der Recherche gelesen wurden, dieselbe, die hier antwortet.

Das ist keine Formalie: alle Belegstellen zu Weg 0 in diesem Bericht (die Routentabelle unten, die
Vorprüfung `validatePreRequestConditions()`, `Capabilities.php`, die per-Nutzer-Schlüssel) stammen aus
dem Tag `v3.1.1`. Wäre eine andere Fassung installiert worden, müssten sie neu geholt werden, bevor ein
Satz dieses Abschnitts stehen bleibt. Sie sind nicht neu geholt worden, weil sie nicht neu geholt werden
mussten.

Der Store-Zugriff im Container hat getragen, der Rückfall über ein von Hand geladenes Paket der App war
nicht nötig, und die Plattformspanne `>=33.0.0 <35.0.0` aus der Versionsmatrix stimmt mit der Instanz
zusammen: die Installation wurde von Nextcloud 33.0.7 nicht abgewiesen.

#### Der Capability-Befund: die Frage ist geschlossen, nicht mehr offen

`ARCHITECTURE.md` führte als offen, ob `integration_openproject` eine Capability veröffentlicht oder ob
es den Navigations-Umweg braucht, den `src/mcp_connector/nextcloud/capabilities.py` für Nextcloud Mail
gehen muss. **Gemessen, und die Antwort ist: eine echte Capability, sogar unauthentifiziert.**

```
# GET /ocs/v2.php/cloud/capabilities, ohne jede Anmeldung, nur OCS-APIRequest: true
HTTP 200, Content-Type application/json; charset=utf-8, 6440 Bytes
ocs.meta.status = ok, ocs.meta.statuscode = 200
Abschnitte (5): app_api, bruteforce, integration_openproject, spreed, theming
capabilities.integration_openproject = {
  "app_version": "3.1.1", "groupfolder_version": "0", "groupfolders_enabled": false }
```

Die drei gemessenen Schlüssel sind `app_version`, `groupfolder_version` und `groupfolders_enabled`, und
`app_version` trägt genau die Fassung, die `occ app:list` nennt. Damit hätte eine spätere
Fähigkeitsprüfung nicht nur die Antwort auf "ist die App da", sondern auch die auf "in welcher Fassung",
und das aus einem Aufruf, der ohnehin schon läuft.

**Der Navigations-Umweg ist hier nicht nötig, weil `Capabilities` das Interface `IPublicCapability`
implementiert.** Genau das ist an dem Messwert oben ablesbar und nicht nur aus dem Quelltext
hergeleitet: der Abschnitt steht in einer Antwort, die ohne ein einziges Zugangsdatum entstanden ist.
Nextcloud Mail veröffentlicht überhaupt keinen Abschnitt, weshalb `capabilities.py` dort auf
`/core/navigation/apps` ausweichen muss; für `integration_openproject` fällt dieser zweite Aufruf weg.

Gegenprobe im selben Lauf, damit der Wert nicht nur für den unauthentifizierten Sonderfall gilt:
derselbe Aufruf unter reiner AppAPI-Impersonation von `alice` antwortet ebenfalls 200, mit 11739 Bytes
und 23 Abschnitten statt 5, und `integration_openproject` trägt darin dieselben drei Schlüssel mit
denselben Werten. Der Unterschied 5 gegen 23 ist selbst der Beleg dafür, dass die unauthentifizierte
Antwort wirklich die öffentliche Teilmenge ist und nicht eine zufällig gleich aussehende.

#### Das dritte Konto, das absichtlich nichts verbindet

Für S2 braucht dieser Bericht ein Nextcloud-Konto, das OpenProject **nie** verbunden hat, denn ohne ein
solches Konto ist "die Berechtigung hängt am Nutzer" nicht messbar, sondern nur behauptbar.
`occ user:add --password-from-env carol` hat es angelegt, `occ user:list` nennt danach `admin`, `alice`,
`bob` und `carol`. Das Passwort steht in der git-ignorierten Verbindungsdatei und in keiner verfolgten
Datei.

`occ user:setting carol integration_openproject token` antwortet an dieser Stelle wörtlich
`The setting does not exist for user "carol".` mit Exit-Code 1. Dieser Grundzustand ist ein Messwert und
kein Nebensatz: er ist vor der Einrichtung von Weg 0 aufgenommen, damit die 401 aus S2 später nicht mit
"die Einrichtung war noch nicht fertig" verwechselt werden kann.

#### Der Einrichtungsweg: gelaufen ist Weg B, und Weg A ist gemessen nicht gangbar

Die Recherche nennt zwei Einrichtungswege, Weg A über den Ablagen-Assistenten von OpenProject (der Weg
des openDesk-Bootstrap-Jobs, deshalb der mit der höheren Übertragbarkeit) und Weg B über
`occ config:app:set` plus den persönlichen Durchlauf je Konto. **Gelaufen ist Weg B.** Der Satz steht
hier so deutlich, weil er die Übertragbarkeit der ganzen Weg-0-Messung auf openDesk begrenzt: gemessen
ist, dass die App im Modus `oauth2` gegen eine lokale Instanz **arbeitet**, nicht, dass der
openDesk-Bootstrap-Job durchläuft.

**Weg A ist in dieser Topologie gemessen nicht gangbar**, und der Grund liegt nicht bei Nextcloud und
nicht bei der Erreichbarkeit, sondern beim SSRF-Schutz von OpenProject: `safe_ip?` weist alle vier
Namen ab, unter denen Nextcloud hier zu erreichen wäre, die Erlaubnisliste ist leer, und der Schlüssel
dafür ist in der Oberfläche nicht setzbar, während die zwei Netzaufrufe danach beide gelingen. Die
vollständige Messung samt Gegenprobe steht in 5.4. Weg A bleibt damit **ungemessen** und ist nicht
verworfen: er wäre mit einem Neuerzeugen des OpenProject-Containers samt
`OPENPROJECT_SSRF__PROTECTION__IP__ALLOWLIST` und einem für beide Seiten gleichlautenden Namen zu
messen, und diese Phase erzeugt diesen Eingriff bewusst nicht (D-03).

**Weg B verlangt fünf Werte, nicht vier.** Die Recherche nennt vier Schlüssel; gemessen sind fünf, und
der fünfte ist der Grund, warum ein reiner `occ`-Weg nicht genügt. `GET /op-oauth-url` antwortete mit
`HTTP 500` und im Protokoll stand wörtlich `OpenProject admin config is not valid!`, ausgelöst in
`lib/Controller/OpenProjectController.php:199`. Die Ursache steht in der Prüfkette der App:

```php
// lib/Service/OpenProjectAPIService.php:931-934 (isAdminConfigOkForOauth2)
$opClientId = $config->getAppValue(Application::APP_ID, 'openproject_client_id');
$opClientSecret = $config->getAppValue(Application::APP_ID, 'openproject_client_secret');
$ncClientId = $config->getAppValue(Application::APP_ID, 'nc_oauth_client_id');
return !(empty($opClientId) || empty($opClientSecret) || empty($ncClientId));
```

```php
// lib/Service/OpenProjectAPIService.php:902-911 (isCommonAdminConfigOk)
$freshProjectFolderSetUp = (bool)$config->getAppValue(Application::APP_ID, 'fresh_project_folder_setup');
if ($freshProjectFolderSetUp === true || empty($oauthInstanceUrl) || !self::validateURL($oauthInstanceUrl)) {
    return false;
}
```

Also braucht Weg 0 zusätzlich `nc_oauth_client_id`, das ist die OAuth-Anwendung auf der
**Nextcloud**-Seite, und `fresh_project_folder_setup` muss aus sein. Der Wert steht nach der
Installation auf `1`, gesetzt von der Migration `Version2400Date20230504144300`, gemessen als
`fresh_project_folder_setup = 1` direkt nach `app:install`. Beides ist **nicht** von Hand gesetzt
worden, sondern über die zwei Routen, die die App dafür selbst mitbringt:

| Schritt | Aufruf | Messwert |
|---------|--------|----------|
| Nextcloud-seitige OAuth-Anwendung | `POST /index.php/apps/integration_openproject/nc-oauth` als Admin, mit `requesttoken` | **200**, Antwort nennt `nextcloud_oauth_client_name = OpenProject client`, `nextcloud_client_id` (64 Zeichen), `nextcloud_client_secret` (64 Zeichen) und die Rückadresse, die Weg A auf der OpenProject-Seite eingetragen hätte: `http://op.localtest.me:8082/oauth_clients/<64 Zeichen>/callback`. Danach `nc_oauth_client_id = 1` |
| Setup-Schalter | `PUT /index.php/apps/integration_openproject/admin-config` mit `{"values":{"setup_project_folder":false,"setup_app_password":false}}` | **200**, Antwort wörtlich `{"status":true,"oPOAuthTokenRevokeStatus":"","oPUserAppPassword":null}`. Danach `fresh_project_folder_setup = 0` |

Die `"status": true` in der zweiten Zeile ist der Messwert, auf den es ankommt: das ist
`isAdminConfigOk()` aus der App selbst, nicht unsere Auslegung ihrer Bedingungen
(`lib/Controller/ConfigController.php:398`). Die Route wurde mit beiden Setup-Schaltern **aus**
aufgerufen, weil genau das die Bedingung von T-17-03 ist; gemessen bleiben `setup_app_password` und
`setup_project_folder` danach leer, und `oPUserAppPassword` ist `null`. Es liegt also kein
App-Passwort im Prozess, und S1 bleibt aussagekräftig.

**Der Admin-Konfigstand, gelesen statt behauptet.** `occ config:list integration_openproject` nennt
danach genau diese Schlüssel: `authorization_method = oauth2`,
`openproject_instance_url = http://op.localtest.me:8082`, `openproject_client_id` (43 Zeichen),
`openproject_client_secret` (43 Zeichen), `nc_oauth_client_id = 1`, `fresh_project_folder_setup = 0`,
`installed_version = 3.1.1`. Kein `sso_provider_type`, kein `oidc_provider`, kein `token_exchange`:
der OIDC-Zweig ist unberührt, was für S5 in 17-07 der Ausgangszustand ist.

#### Der persönliche Durchlauf lief ohne Browser, und zwei Hürden dabei sind eigene Messwerte

Der Plan sah für den persönlichen Zustimmungsdurchlauf einen Owner-Schritt in zwei Oberflächen vor.
Gemessen ist er per Formular gelaufen, für beide Konten, in neun Schritten und ohne Browser. Die
Schritte 5 bis 8 sind das Muster aus 2.2, hier nur mit der anderen OAuth-Anwendung:

| Schritt | Aufruf | Messwert |
|---------|--------|----------|
| 1, 2 | `GET /login`, dann `POST /login` in Nextcloud | 200, `requesttoken` 89 Zeichen; die Anmeldung endet mit `303` auf `/apps/dashboard/` |
| 3 | `GET /index.php/csrftoken` | 200, Token 89 Zeichen, an die Sitzung gebunden |
| 4 | `GET /index.php/apps/integration_openproject/op-oauth-url` mit `requesttoken` | **200**, `application/json`. Die Adresse trägt `client_id` (43 Zeichen), `redirect_uri` (siehe unten), `response_type=code`, `state` (10 Zeichen), `code_challenge` (43 Zeichen) und `code_challenge_method=S256` |
| 5, 6 | `GET /login`, `POST /login` in OpenProject als `opa` bzw. `opb` | 200, `authenticity_token` 86 Zeichen; die Kette endet auf der Startseite |
| 7 | `GET /oauth/authorize` mit der Adresse aus Schritt 4 | **200**, Zustimmungsseite 13442 Zeichen (`opa`) bzw. 13440 (`opb`), wörtlich `Authorize nc-mcp-spike-weg0 to use your account opa?` bzw. `opb` |
| 8 | `POST /oauth/authorize` | **302**, `Location` trägt `code` (43 Zeichen) und das `state` Zeichen für Zeichen zurück |
| 9 | `GET /oauth-redirect` mit der Nextcloud-Sitzung des Nutzers | **303** auf `/apps/files/` |

Die `redirect_uri` aus Schritt 4 ist gemessen
`http://127.0.0.1:8091/index.php/apps/integration_openproject/oauth-redirect` und stimmt Zeichen für
Zeichen mit dem Wert überein, den `IURLGenerator::getAbsoluteURL` in derselben Instanz liefert und den
`getOauthRedirectUrl()` (`lib/Service/OpenProjectAPIService.php:697-701`) baut. Deshalb trägt die
OAuth-Anwendung auf der OpenProject-Seite genau diese Zeichenkette.

**Erste Hürde, ein eigener Messwert: ohne `Origin`-Kopf keine Anmeldung.** `POST /login` antwortete
zunächst mit `303` auf `/login?direct=1&user=alice`, im Protokoll `Login failed: 'alice'`, und das
sieht wie ein falsches Passwort aus. Es war keines: dieselben Zugangsdaten antworten per Basic-Auth auf
`/ocs/v2.php/cloud/user` mit **200** (Gegenprobe: ein falsches Passwort dort **401**). Der Grund steht
in dieser Nextcloud-Fassung:

```php
// core/Controller/LoginController.php:307-314
$origin = $this->request->getHeader('Origin');
$throttle = true;
if ($origin === '' || !$trustedDomainHelper->isTrustedUrl($origin)) {
    $error = self::LOGIN_MSG_INVALID_ORIGIN;
    $throttle = false;
}
```

Ein leerer `Origin` bricht die Anmeldung ab, **bevor** das Passwort geprüft wird. Mit
`Origin: http://127.0.0.1:8091` antwortet derselbe Aufruf `303` auf `/apps/dashboard/`. Wer diese Zeile
nicht kennt, liest den Zustand als falsches Passwort und geht in den Browser-Rückfall, obwohl der
Formularweg trägt. Das ist dieselbe Klasse von Falle wie der 2FA-Umweg aus 2.2.

**Zweite Hürde, und die ist der interessantere Befund: auch Nextcloud verweigert Loopback.** Der
Rückweg in Schritt 9 antwortete `303`, die Verbindung war aber **nicht** hergestellt:
`oauth_connection_result` stand auf `error`, und `oauth_connection_error_message` lautete wörtlich

```
Error getting OAuth access token. Host "127.0.0.1" (op.localtest.me:80) violates local access rules
```

Das ist die Prüfung auf lokale Adressen von Nextcloud selbst, nicht die von OpenProject aus 5.4. Zwei
Beobachtungen dazu, beide gemessen: die Meldung nennt `127.0.0.1`, also die **öffentliche** Auflösung
von `op.localtest.me`, und nicht die `172.29.43.10` aus dem `extra_hosts`-Eintrag, mit der der
PHP-`curl` desselben Containers in 5.2 gemessen 200 bekommt; und sie nennt Port `80`, obwohl der
Aufruf an `:8082` geht. Aufgelöst wurde es mit der dafür vorgesehenen Systemeinstellung,
`occ config:system:set allow_local_remote_servers --value=true --type=boolean` (vorher leer, danach
`true`); danach antwortete derselbe Durchlauf mit `oauth_connection_result = success`.

**Der Befund dahinter, und er ist mehr als eine Fußnote:** beide Produkte sperren Loopback- und
private Adressen in der Vorgabe, jedes mit seinem eigenen Mechanismus und an einer anderen Stelle der
Kette. Ein Spike von Weg 0 auf einem Entwicklungsrechner braucht deshalb **auf jeder Seite eine
Lockerung**, und nur eine davon ist hier gefallen: die Nextcloud-Seite per Systemeinstellung zur
Laufzeit, die OpenProject-Seite nicht (sie hätte den Container neu erzeugt, siehe 5.4). Für eine
openDesk-Installation sagt das nichts, weil dort beide Seiten routbare Adressen haben; für jeden, der
diesen Aufbau nachbaut, ist es der teuerste Teil des Tages.

#### Der Zustand nach der Einrichtung, je Konto gelesen

| Konto | `oauth_connection_result` | `user_name` und `user_id` aus OpenProject | `token_expires_at` |
|-------|---------------------------|-------------------------------------------|--------------------|
| `alice` | `success` | `Alice Spike`, `5` | `1787949009`, in der Zukunft, Restlaufzeit 7181 s |
| `bob` | `success` | `Bob Spike`, `6` | `1787949020`, in der Zukunft, Restlaufzeit 7192 s |
| `carol` | Schlüssel existiert nicht | Schlüssel existiert nicht | Schlüssel existiert nicht |

Die zwei Ids sind der Beleg, dass die Zuordnung die beabsichtigte ist und nicht zufällig: `5` ist
`opa` und `6` ist `opb` aus 5.3, und `opb` ist das Konto, das Mitglied des privaten Projekts ist. Damit
steht der Negativbeweis von 17-06 auf derselben Asymmetrie wie der von 2.2. Die Restlaufzeit von rund
7200 Sekunden ist derselbe Wert, den 2.2 als `expires_in` gemessen hat, hier über einen zweiten,
unabhängigen Weg bestätigt.

`carol` trägt für alle drei Schlüssel `token`, `refresh_token` und `token_expires_at` wörtlich
`The setting does not exist for user "carol".` Das ist Absicht und der Messweg von S2.

#### S1: die OCS-Fläche antwortet unter reiner AppAPI-Impersonation

**Behauptung:** `GET /api/v1/url` antwortet unter reiner AppAPI-Impersonation mit OCS-JSON und der
OpenProject-Adresse.

**Messweg.** Ein Aufruf durch Caddy gegen `http://127.0.0.1:8091`, mit `OCS-APIRequest: true`,
`Accept: application/json`, `EX-APP-ID`, `EX-APP-VERSION` und `AUTHORIZATION-APP-API`, **ohne**
App-Passwort im Prozess. Beurteilt wird nach der Antwortform aus dem vorab festgelegten Kriterium.

```
# GET /ocs/v2.php/apps/integration_openproject/api/v1/url, Impersonation von alice
HTTP 200, Content-Type application/json; charset=utf-8, 103 Bytes
{"ocs":{"meta":{"status":"ok","statuscode":200,"message":"OK"},"data":"http://op.localtest.me:8082"}}
```

**Messwert und Urteil:** OCS-Umschlag als JSON, `ocs.data` ist die Instanzadresse, und sie ist
dieselbe, die `occ config:app:get openproject_instance_url` nennt. Nach dem Kriterium: **erreicht.**
Das Urteil hängt nicht an der 200, sondern an der Form: diesen Umschlag erzeugt nur App-Code hinter der
CSRF- und Impersonationskette. Die Vorhersage aus K3 trifft zu, die Methode fährt keine Vorprüfung.

**Gegenprobe im selben Lauf:** derselbe Aufruf, `APP_SECRET` durch 64 Null-Zeichen ersetzt.

```
HTTP 401, application/json, 106 Bytes
{"ocs":{"meta":{"status":"failure","statuscode":997,"message":"Current user is not logged in"},"data":[]}}
```

Ohne diese Zeile könnte die 200 darüber von einer Instanz kommen, die jeden Aufruf durchlässt. Der Wert
des Kopfes `AUTHORIZATION-APP-API` wird nicht protokolliert, weder der echte noch der aus Nullen, weil
er Base64 von `<user>:<APP_SECRET>` ist (T-17-01).

#### S2: die Berechtigung hängt am Nutzer, nicht an der App

**Behauptung:** Dieselbe Fläche antwortet für ein Konto **ohne** verbundenes OpenProject mit 401 und
für ein verbundenes mit Daten.

**Warum diese Messung nicht auf `/api/v1/url` läuft.** `getOpenProjectUrl()` ruft
`validatePreRequestConditions()` nicht auf und gibt einen App-Konfigwert zurück, unabhängig davon, ob
der aufrufende Nutzer OpenProject verbunden hat (K3). Eine 200 dort belegt Erreichbarkeit und über
Berechtigungen **nichts**. S2 läuft deshalb auf `/api/v1/configuration`: argumentfrei, lesend, und mit
Vorprüfung. Gezählt in der installierten Fassung: `validatePreRequestConditions()` kommt in
`lib/Controller/OpenProjectAPIController.php` 14 mal vor, das ist die Definition plus 13 Aufrufstellen,
bei 15 Methoden mit `NoAdminRequired` und genau einer mit `NoCsrfRequired`.

| Konto | Zustand | Aufruf | Messwert | Urteil |
|-------|---------|--------|----------|--------|
| `carol` | nie verbunden | `GET /ocs/v2.php/apps/integration_openproject/api/v1/configuration` | **HTTP 401**, `application/json`, 77 Bytes, `{"ocs":{"meta":{"status":"failure","statuscode":401,"message":""},"data":""}}` | erreicht, und abgewiesen: das ist `new DataResponse('', Http::STATUS_UNAUTHORIZED)` aus `validatePreRequestConditions()` |
| `alice` | verbunden mit `opa` | derselbe Aufruf | **HTTP 200**, 1702 Bytes, `ocs.data._type = Configuration`, `hostName = op.localtest.me:8082`, dazu `maximumAttachmentFileSize 5242880`, `maximumAPIV3PageSize 1000`, `hoursPerDay 8` | Daten, und zwar echte Werte der OpenProject-Instanz |
| `bob` | verbunden mit `opb` | derselbe Aufruf | **HTTP 200**, 1700 Bytes, dieselben Felder | Daten, zweites Konto unabhängig bestätigt |

**Die Gegenprobe, ohne die die 401 nichts beweist,** ist die zweite Zeile: ohne einen Lauf, der Daten
liefert, wäre die 401 von `carol` genauso mit einer kaputten Einrichtung erklärbar. Sie liegt hier
doppelt vor, für `alice` und für `bob`.

**Eine zweite Gegenprobe, die der Plan nicht verlangt und die den Befund härtet:** die zwei 401 dieses
Abschnitts sind **unterscheidbar**, und deshalb ist die von `carol` nachweislich App-Code und nicht
eine gescheiterte Impersonation. Die 401 der S1-Gegenprobe trägt `statuscode 997` und die Meldung
`Current user is not logged in`, die kommt aus dem Kern von Nextcloud. Die 401 von `carol` trägt
`statuscode 401` und eine **leere** Meldung, genau die Form, die die Vorprüfung der App erzeugt. Wer
nur auf "401" schaut, hält beide für dasselbe und beweist mit S2 nichts.

**Kontrolle zum Pfad.** Derselbe Pfad ohne OCS-Präfix,
`http://127.0.0.1:8091/index.php/apps/integration_openproject/api/v1/configuration`, antwortet
**HTTP 404** mit leerem Körper. Die Fläche von Weg 0 liegt also ausschließlich unter
`/ocs/v2.php/apps/integration_openproject`, wie der Block `'ocs' => [` in `appinfo/routes.php` sagt,
und ein Client, der den Anwendungs-Präfix nimmt, findet nichts.

#### S3: der Zwei-Konten-Negativbeweis auf Weg 0 (D-05)

**Behauptung:** `alice` findet über die Suchfläche von Weg 0 das Arbeitspaket aus dem privaten Projekt
von `bob` nicht, und `bob` findet es.

**Die Kette, die dieser Weg wirklich hat, besteht aus zwei Gliedern, und beide gehören in den Satz.**
Auf Weg 0 entscheidet zuerst **Nextcloud**, wer der Nutzer ist: die AppAPI-Impersonation setzt den
Namen, und die App liest ihn als `$this->userId`. Erst danach entscheidet **OpenProject**, was dieser
Nutzer sehen darf, denn die App stellt die Suche unter dem persönlichen `token` genau dieses Nutzers.
Ein Satz, der nur das zweite Glied nennt, liest wie eine Aussage über OpenProject allein und wäre für
diesen Bericht zu wenig. Beide Glieder sind unten mit je einem eigenen Messwert belegt.

**Messweg.** Ein Aufruf durch Caddy gegen `http://127.0.0.1:8091` unter reiner
AppAPI-Impersonation, mit `OCS-APIRequest: true`, `Accept: application/json`, `EX-APP-ID`,
`EX-APP-VERSION` und `AUTHORIZATION-APP-API`, **ohne** App-Passwort im Prozess und ohne Cookie. Das
Suchwort ist `SPIKE-OD-8471` aus 5.3, das an keiner anderen Stelle dieser Instanz vorkommt.

| Konto | Zustand in OpenProject | Aufruf | Messwert | Treffer |
|-------|------------------------|--------|----------|---------|
| `alice` | `opa`, **kein** Mitglied von `spike-privat-b` | `GET /ocs/v2.php/apps/integration_openproject/api/v1/work-packages?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | **HTTP 200**, `application/json`, 74 Bytes, OCS-Umschlag mit `ocs.data = []` | **0** |
| `bob` | `opb`, Mitglied | derselbe Aufruf | **HTTP 200**, `application/json`, 4746 Bytes, OCS-Umschlag mit einem Objekt in `ocs.data` | **1**: `id 38`, `subject SPIKE-OD-8471 privat` |

**Die Zeile von `bob` ist die erste Gegenprobe**, und ohne sie wäre die leere Antwort von `alice` auch
ein Tippfehler im Suchwort. Sie liegt hier nicht als Behauptung vor, sondern als Treffer mit Id und
Betreff, und die Id `38` ist dieselbe, die 5.3 beim Anlegen vergeben bekam.

**Die zweite Gegenprobe, ohne die die Null von `alice` auch eine kaputte Verbindung wäre.** Derselbe
Aufruf, dieselbe Fläche, dieselben Kopfzeilen, nur mit dem Suchwort `Demo` aus den Seed-Daten:

| Konto | Messwert | Treffer | Ist `38` darunter |
|-------|----------|---------|-------------------|
| `alice` | **HTTP 200**, 35239 Bytes | **14** | **nein** |
| `bob` | **HTTP 200**, 36308 Bytes | **14** | **nein** |

`alice` bekommt also über genau diese Fläche 14 Arbeitspakete geliefert, ihr Zugang trägt und ihre
Suche findet Daten. Nur das eine Arbeitspaket, das ihr nicht gehört, ist nicht darunter. Die Null in
der Tabelle oben ist damit ein Berechtigungsbefund und kein Verbindungsfehler.

**Die dritte und vierte Gegenprobe belegen die zwei Glieder der Kette, jede an ihrem eigenen Glied,
und zwar auf derselben Route:**

| Gegenprobe | Messwert | Welches Glied sie belegt |
|------------|----------|--------------------------|
| derselbe Aufruf als `bob`, `APP_SECRET` durch 64 Null-Zeichen ersetzt | **HTTP 401**, 106 Bytes, `statuscode 997`, `Current user is not logged in` | **Nextcloud entscheidet die Identität**: ohne gültige Impersonation gibt es keinen Nutzer, und die Suche läuft nie |
| derselbe Aufruf als `carol` (nie verbunden) | **HTTP 401**, 77 Bytes, `statuscode 401`, **leere** Meldung | **die App prüft am Nutzer**: das ist `validatePreRequestConditions()`, dieselbe Form wie in S2 |

Damit ist die Suche unter drei verschiedenen Identitäten gefahren und liefert drei verschiedene
Ergebnisse: Daten, keine Daten, keine Antwort. Die Fläche ist an keiner Stelle nutzerunabhängig.

**Der Parameter `isSmartPicker`, und warum er kein Beiwerk ist.** Ohne ihn antworten **beide** Konten
mit 200, `application/json`, 74 Bytes und **null** Treffern, auch `bob`. Nach dem
Ungemessen-Fallback wäre S3 in dieser Form leer gewesen. Die Ursache ist nicht geraten, sondern
gemessen und im Quellcode der installierten Fassung 3.1.1 belegt:

```php
// lib/Service/OpenProjectAPIService.php:311-316 (searchRequest)
if ($onlyLinkableWorkPackages) {
    $filters[] = [
        'linkable_to_storage_url' =>
            ['operator' => '=', 'values' => [urlencode($this->getNCBaseUrl())]]
    ];
}
```

Der Controller füllt genau diesen Schalter, und zwar mit dem umgekehrten Wert des Anfrageparameters:
`!$isSmartPicker` in `lib/Controller/OpenProjectAPIController.php:148`, bei
`bool $isSmartPicker = false` als Vorgabe (Zeile 137). Die Vorgabe der Fläche verlangt also, dass das
Arbeitspaket zu einer in OpenProject **registrierten** Nextcloud-Ablage verlinkbar ist. In dieser
Instanz gibt es keine solche Ablage: `GET /api/v3/storages` antwortet **200** mit `total 0` und
`count 0` (131 Bytes, Aufbauzugang `Basic apikey:<OP_API_TOKEN>` des Kontos `admin`, ausdrücklich
kein Messweg von S3). Der Filter trifft damit für jedes Konto gleich nichts.

**Der Zusammenhang mit 5.4 ist der eigentliche Befund dieser Zeile:** die Ablage entsteht auf Weg A,
dem Assistentenweg, und Weg A ist in dieser Topologie gemessen nicht gangbar. Die Vorgabe-Suche von
Weg 0 hängt also an genau dem Einrichtungsschritt, der hier fehlt und den der openDesk-Bootstrap-Job
geht. Für OD-04 ist das eine Zeile, die man nicht raten will: `isSmartPicker=true` ist der Modus ohne
Ablagenbindung, die Vorgabe der Modus mit ihr, und wer die Vorgabe nimmt, bekommt in einer Umgebung
ohne registrierte Ablage eine leere Liste ohne Fehlermeldung.

**Was der Parameter nicht verschiebt, und deshalb bleibt S3 gültig:** er entscheidet, welche
Arbeitspakete überhaupt in Frage kommen, nicht wessen Berechtigungen gelten. Beide Läufe von S3
tragen ihn gleich, der Unterschied zwischen 0 und 1 Treffer ist ausschließlich der Unterschied
zwischen den zwei Konten, und die 14 gleichen Treffer der `Demo`-Kontrolle zeigen, dass er auch für
`alice` Daten durchlässt.

**Urteil:** erreicht, und die Berechtigungsgrenze hält auf Weg 0 wortwörtlich so wie auf Weg 1 in
2.2. Kein Aufruf dieses Abschnitts ist schreibend: gefahren ist ausschließlich
`GET /api/v1/work-packages`, Arbeitspaket 38 ist unverändert.

#### S4: die Erneuerung ohne Browsersitzung, nach künstlichem Ablauf

**Behauptung:** Nach einem künstlich in die Vergangenheit gesetzten Ablauf antwortet derselbe
OCS-Aufruf im Modus `oauth2` wieder mit Daten, ohne Browsersitzung, und `token_expires_at` steht
danach in der Zukunft. **Das ist die Messung, an der Weg 0 hängt.**

**Der künstliche Ablauf ist ausdrücklich Methode und nicht Nebenwirkung.** Der Wert `0` ist dafür der
sichere Wert, und zwar aus zwei Gründen, die beide im Quellcode der installierten Fassung stehen:
`isAccessTokenExpired()` zieht 60 Sekunden Sicherheitsabstand ab, ein Wert kurz in der Vergangenheit
wäre also unsicher, und `0` ist zugleich der Vorgabewert, mit dem die Methode selbst liest.

```php
// lib/Service/OpenProjectAPIService.php:1726-1733
public function isAccessTokenExpired(string $userId): bool {
    $expiresAt = $this->config->getUserValue($userId, Application::APP_ID, 'token_expires_at', 0);
    // Consider token expired 60 seconds early
    // to avoid race conditions caused by various factors
    $tokenExpirySafetyMargin = 60;
    $expiresAt = (int)$expiresAt - $tokenExpirySafetyMargin;
    return time() > $expiresAt;
}
```

**Messweg und die drei Zahlen, auf die es ankommt.** Alle drei sind mit
`occ user:setting bob integration_openproject token_expires_at` gelesen beziehungsweise gesetzt, der
Aufruf dazwischen ist derselbe wie in S3, als `bob`:

| Schritt | Zeitpunkt (Unix) | `bob.token_expires_at` | Aufruf und Messwert |
|---------|------------------|------------------------|---------------------|
| Ausgangszustand, gelesen | 1787943289 | **1787949020**, also 5731 s in der Zukunft | kein Aufruf |
| künstlich gesetzt, zurückgelesen | 1787943305 | **0** | kein Aufruf |
| Hauptlauf | 1787943305 | (während des Aufrufs) | `GET /ocs/v2.php/apps/integration_openproject/api/v1/work-packages?searchQuery=SPIKE-OD-8471&isSmartPicker=true` als `bob`: **HTTP 200**, `application/json`, **4746 Bytes**, ein Treffer, `id 38`, `subject SPIKE-OD-8471 privat` |
| Zustand danach, gelesen | 1787943305 | **1787950505**, also 7200 s in der Zukunft | kein Aufruf |

**Die Differenz ist kein Zufallswert, sondern die Bestätigung eines schon gemessenen:**
1787950505 minus 1787943305 ist genau **7200**, dasselbe `expires_in`, das 2.2 am Token-Endpunkt von
OpenProject gemessen hat und das 17-05 nach der Einrichtung als Restlaufzeit gelesen hat. Damit nennen
drei voneinander unabhängige Messwege denselben Wert.

**Der zweite Beleg dafür, dass wirklich erneuert wurde, steht im Zustand selbst.** Nicht nur die
Ablaufzeit ist neu, das Tokenpaar ist ausgetauscht:

| Schlüssel | vor dem Hauptlauf | nach dem Hauptlauf |
|-----------|-------------------|--------------------|
| `token` | Länge 43, Präfix `dbHz` | Länge 43, Präfix `7Gvk` |
| `refresh_token` | Länge 43, Präfix `bHRR` | Länge 43, Präfix `eXhd` |

Beide Werte sind ersetzt, also hat OpenProject ein neues Paar ausgegeben, genau die Rotation aus
`use_refresh_token`, die 2.2 auf Weg 1 direkt am Token-Endpunkt gemessen hat. Von den Werten stehen
hier nur Länge und Vier-Zeichen-Präfix (T-17-01).

**In diesem Aufruf war keine Browsersitzung im Spiel, und das ist der Punkt der ganzen Behauptung.**
Der Aufruf lief unter reiner AppAPI-Impersonation über Caddy, mit `OCS-APIRequest: true`, `EX-APP-ID`,
`EX-APP-VERSION` und `AUTHORIZATION-APP-API` und sonst nichts: **kein Cookie** (`curl` ohne `-b` und
ohne `-c`), **kein App-Passwort im Prozess**, und der Nutzer `bob` hatte zu diesem Zeitpunkt keine
Nextcloud-Sitzung offen. Die Erneuerung hat also der Server aus dem gespeicherten `refresh_token`
gefahren, und niemand hat einen Browser dafür gebraucht.

**Die Gegenprobe, ohne die der Hauptlauf nichts beweist.** Ohne sie wäre die 200 oben auch mit einem
zwischengespeicherten Token erklärbar. Gefahren ist deshalb dieselbe Kette mit einem unbrauchbaren
`refresh_token`, im selben Lauf und siebzehn Sekunden später:

| Schritt | Messwert |
|---------|----------|
| `occ user:setting bob integration_openproject refresh_token <43 Nullen>` | gesetzt; `token` bleibt unverändert (Präfix `7Gvk`) |
| `occ user:setting bob integration_openproject token_expires_at 0`, zurückgelesen | **0** |
| derselbe OCS-Aufruf als `bob` | **HTTP 401**, `application/json`, **77 Bytes**, `{"ocs":{"meta":{"status":"failure","statuscode":401,"message":""},"data":""}}` |
| Zustand danach | `token_expires_at` bleibt **0**, `token` unverändert `7Gvk`, `refresh_token` die 43 Nullen |

**Der Weg dieser 401 durch den Code ist derselbe wie bei `carol` in S2, und das ist konsistent und
kein Zufall:** `getAccessToken()` versucht die Erneuerung, `requestOAuthAccessToken()` scheitert, die
Methode gibt eine leere Zeichenkette zurück, und `validatePreRequestConditions()` antwortet darauf mit
`new DataResponse('', Http::STATUS_UNAUTHORIZED)`
(`lib/Controller/OpenProjectAPIController.php:43-49`). Deshalb trägt sie `statuscode 401` und eine
leere Meldung und nicht die `997` des Kerns.

**Dass wirklich eine Erneuerung versucht wurde, steht zusätzlich im Protokoll**, und die Zeile ist
gemessen und nicht hergeleitet:

```
# docker compose exec nextcloud, aus data/nextcloud.log, gekürzt
level 3, 2026-08-28T18:55:23+00:00, user bob, app integration_openproject
"Failed to refresh token: Client error: `POST http://op.localtest.me:8082/oauth/token`
 resulted in a `400 Bad Request` response: {"error":"invalid_grant", ...}"
```

**Der Kontrast zum Hauptlauf ist selbst ein Messwert:** im Zeitfenster des Hauptlaufs (18:55:0x)
enthält `nextcloud.log` **null** Zeilen, im Zeitfenster der Gegenprobe zwei (eine `level 2` mit
`OpenProject OAuth error`, eine `level 3` mit der Zeile oben). Die geglückte Erneuerung ist also
stumm, die gescheiterte laut. Wer S4 nur am Log prüfen wollte, hätte den Hauptlauf für einen
Nichtlauf gehalten; deshalb sind die drei Zustandswerte die Messung und das Log der Zusatzbeleg.

**Der Quellcodebeleg, der sagt, warum diese Messung überhaupt gelingen darf, und wo sie endet.** Die
Erneuerung ohne Oberfläche ist kein Nebeneffekt, sie steht als Absicht im Kommentar der
Upstream-Entwickler, in `lib/Service/OpenProjectAPIService.php:1764-1765`:

```php
// For OAuth2 setup, only try to refresh the expired token.        // Zeile 1764
// Token exchange needs to be initiated from the UI.               // Zeile 1765
```

Wortwörtlich: im Modus `oauth2` erneuert die App serverseitig, im Modus `oidc` sagt sie selbst, dass
der Austausch von der Oberfläche her angestoßen werden muss. **Genau diese Asymmetrie ist der
Unterschied zwischen S4 und S5.** S4 belegt hier die erste Hälfte gemessen; die zweite Hälfte, das
Verhalten im Modus `oidc` nach Ablauf, ist Plan 17-07. Ein Bericht, der aus S4 auf den OIDC-Betrieb
schließt, überdehnt genau die Stelle, an der die Quelle selbst eine Grenze zieht.

**Zwei Zustände, die dieser Abschnitt hinterlässt, und beide gehören ausgesprochen.** Die
Weg-0-Verbindung von `bob` ist nach der Gegenprobe **absichtlich kaputt**: sein `refresh_token` ist
der Nullwert und sein `token_expires_at` steht auf 0. Das ist gewollt und der Preis der Gegenprobe;
der Zustand verschwindet mit dem Nextcloud-Band beim `down -v`. **`alice` ist unberührt**, gemessen
nach der Gegenprobe: `occ user:setting alice integration_openproject token_expires_at` antwortet
weiter `1787949009`. Plan 17-07 braucht ein verbundenes Konto, und das ist `alice`.

**Nachtrag vom 2026-08-29: derselbe Befund noch einmal, diesmal ohne jeden künstlichen Eingriff.**
Der Hauptlauf oben hat den Ablauf gestellt, und das ist die eine Stelle, an der die Messung angreifbar
bleibt: `0` ist zugleich der Vorgabewert von `isAccessTokenExpired()`, und ein Kritiker dürfte fragen,
ob ein von Hand gesetzter Zustandswert überhaupt dasselbe auslöst wie eine wirklich verstrichene Frist.
Diese Frage ist inzwischen beantwortet, und zwar durch einen Lauf, der gar nicht als S4-Messung geplant
war. Beim Nachprüfen der S6-Zahlen am Folgetag war der `token_expires_at` von `alice` aus Plan 17-05
(`1787949009`) **von selbst** verstrichen: zum Zeitpunkt des Aufrufs (`1787968632`) lag er **19623
Sekunden in der Vergangenheit**, also weit jenseits des Sicherheitsabstands von 60 Sekunden. An diesem
Konto ist **kein** `occ user:setting` gefahren worden, weder vorher noch nachher.

| Schritt | Messwert |
|---------|----------|
| `token_expires_at` von `alice` vor dem Aufruf, aus 17-05 und seither unangetastet | `1787949009`, also `now - 19623` |
| OCS-Aufruf als `alice`, `?searchQuery=Upload%20presentations&isSmartPicker=true`, wieder ohne Cookie und ohne App-Passwort | **HTTP 200**, `application/json; charset=utf-8`, **2542 Bytes**, ein Treffer `id 12` |
| `occ user:setting alice integration_openproject token_expires_at` danach | **`1787975808`**, also `now + 7176`, wieder die vollen rund 7200 Sekunden |

**Damit steht S4 auf zwei Beinen statt auf einem: einmal mit gestelltem und einmal mit wirklich
verstrichenem Ablauf, und beide Male mit demselben Ausgang.** Der künstliche Ablauf ist als Messweg
also nicht nur zulässig, sondern gemessen deckungsgleich mit dem natürlichen. Die drei Zahlen dieses
Nachtrags sind zugleich der Beleg, dass die Erneuerung nicht an einer Besonderheit des Wertes `0`
hängt.

**Eine Buchhaltungsfolge, die hier stehen muss, damit ein Wiederholungslauf sie nicht falsch liest:**
`alice` trägt seit diesem Aufruf **nicht mehr** den Wert `1787949009` aus Zeile 12 von 5.5.2, sondern
`1787975808`. Zeile 12 bleibt als Messwert ihres Zeitpunkts richtig und wird nicht geändert. Was
unverändert gilt, ist die Aussage dahinter: die Verbindung von `alice` ist unversehrt, und sie ist es
nach diesem Nachtrag sogar belegter als vorher, weil sie gerade eben eine Erneuerung durchlaufen hat.
Plan 17-07 findet ein verbundenes und frisch erneuertes Konto vor.

#### S5a, S5b und S5c: das Verhalten im Modus `oidc` nach Ablauf, und welcher der drei Pfade bricht

**Behauptung:** Die serverseitige Token-Erneuerung, die S4 im Modus `oauth2` belegt, hält im
OIDC-gebundenen Betrieb nicht, und der Aufruf fällt nach Ablauf des zwischengespeicherten Tokens auf
401. Offen sind drei Fragen: welcher der drei Ereignispfade aus K5 dabei bricht (S5a, S5b), und ob
`IUserSession::isLoggedIn()` unter AppAPI-Impersonation überhaupt `true` liefert oder der Bruch schon
davor liegt (S5c).

**Gemessen am 2026-08-29, ja, alle drei.** Der Loglevel stand vor dem ersten Lauf auf `Debug (0)`
(`occ log:manage --level 0`), weil die Zeilen, die die Pfade unterscheiden, `logger->debug` sind und
der Vorgabewert `Warning (2)` sie verschluckt. Ohne diesen Schritt wäre jeder der sechs Läufe unten als
nackte 401 ohne Ursache im Bericht gelandet.

**Die zwei Konten dieses Abschnitts, weil kein Messwert ohne seinen Nutzernamen gilt.** `alice` ist das
Nextcloud-Konto aus 17-05 mit dem gespeicherten `oauth2`-Tokenpaar. Daneben steht das Konto, das
`user_oidc` bei der ersten Anmeldung über Keycloak selbst anlegt, und seine Id ist nicht `alice`,
sondern der Streuwert `3855a8f7d81aae5de814f2a6d77bd149591983992337ec676fb84ebda333cfe3` mit dem
Anzeigenamen `Alice Spike`; die Tabellen kürzen ihn zu `3855a8f7...`. Diese Unterscheidung ist kein
Detail: wer S5 unter `alice` misst und das Ergebnis dem OIDC-Konto zuschreibt, misst zwei verschiedene
Kontenzustände und hält sie für einen.

**Die sechs Läufe.** Jeder Lauf ist derselbe OCS-Aufruf wie in S3 und S4
(`GET /ocs/v2.php/apps/integration_openproject/api/v1/work-packages?searchQuery=SPIKE-OD-8471&isSmartPicker=true`),
unter reiner AppAPI-Impersonation, ohne Cookie und ohne App-Passwort, jeweils nach
`occ user:setting <konto> integration_openproject token_expires_at 0`. `authorization_method` steht in
allen sechs auf `oidc`.

| # | `sso_provider_type` | `token_exchange` | `store_login_token` | Konto | HTTP, Bytes | wörtliche Log-Zeile (Messwert) | Zustand danach | Urteil |
|---|---|---|---|---|---|---|---|---|
| 1 (S5a) | `external` | `0` | `1` | `3855a8f7...` | **401**, 77 | `[ExternalTokenRequestedListener] received request`, dann `[TokenService] Get token from the session`, dann `[TokenService] getToken: no session data`, dann `Token event has not been caught by 'user_oidc'` | kein `token`, `token_expires_at` bleibt `0` | der Sitzungspfad bricht, und zwar am fehlenden Sitzungstoken |
| 2 (S5a) | `external` | `0` | `0` | `3855a8f7...` | **401**, 77 | `[ExternalTokenRequestedListener] received request`, dann `Failed to get token: Failed to get external token, login token is not stored` | unverändert | derselbe Pfad, andere Bruchstelle: die Vorbedingung greift vor der Sitzungsfrage |
| 3 (S5b) | `external` | `1` | `0` | `3855a8f7...` | **401**, 77 | `[ExchangedTokenRequestedListener] received request for audience: openproject`, dann `Failed to get token: Failed to exchange token, storing the login token is disabled. It can be enabled in config.php` | unverändert | `TokenService.php:318`, live reproduziert |
| 4 (S5b) | `external` | `1` | `1` | `3855a8f7...` | **401**, 77 | `[TokenService] Starting token exchange`, `[TokenService] Get token from the session`, `[TokenService] getToken: no session data`, `[TokenService] Failed to exchange token, no login token found in the session` | unverändert | `TokenService.php:328`, live reproduziert, und das ist die in `research/SUMMARY.md` vermutete Bruchstelle |
| 5 (Kontrolle) | `nextcloud_hub` | `0` | `1` | `3855a8f7...` | **401**, 77 | `[InternalTokenRequestedListener] received request for audience: openproject`, dann `[TokenService] Failed to get token from Oidc provider app, oidc app is not installed` | unverändert | der Pfad stellt die Sitzungsfrage nicht und bricht an einer ganz anderen Stelle, siehe unten |
| 6 (Kontrolle) | `external` | `0` | `1` | `alice` | **401**, 77 | `Token has expired.`, `Refreshing access token.`, dann `[ExternalTokenRequestedListener] received request`, `[TokenService] getToken: no session data`, `Token event has not been caught by 'user_oidc'` | `token` unverändert (Länge 43, Präfix `Jm2D`), `token_expires_at` bleibt `0` | derselbe Aufruf, dasselbe Konto und derselbe künstliche Ablauf wie in S4, nur der Modus ist anders |

Der Körper der 401 ist in allen sechs Zeilen derselbe und 77 Bytes lang:
`{"ocs":{"meta":{"status":"failure","statuscode":401,"message":""},"data":""}}`. Das ist genau die
Antwortform aus `validatePreRequestConditions()`, die 17-05 für `carol` und 17-06 für die
S4-Gegenprobe gemessen hat; nach dem Kriterium aus dem Kopf dieses Berichts ist sie antwortender
App-Code und kein Erreichbarkeitsproblem.

**Zeile 6 ist die Zeile, an der Weg 0 kippt, und sie steht neben der S4-Zeile derselben Kette.**
Dasselbe Konto, derselbe Aufruf, derselbe gestellte Ablauf, nur `authorization_method` unterscheidet
sich:

| | Modus `oauth2` (S4, 17-06) | Modus `oidc` (S5, dieser Plan) |
|---|---|---|
| Aufruf | **200**, ein Treffer, 4746 Bytes | **401**, 77 Bytes, `statuscode 401`, leere Meldung |
| `token_expires_at` danach | `1787950505`, also **+7200 s** | bleibt **`0`** |
| `token` danach | neues Paar, anderes Präfix | **unverändert** |
| Protokollspur | `Failed to refresh token` nur in der Gegenprobe, der geglückte Lauf ist stumm | vier Zeilen, die die Ursache benennen |

Damit ist der Kommentar der Upstream-Entwickler in
`lib/Service/OpenProjectAPIService.php:1764-1765` nicht mehr nur zitiert, sondern beidseitig gemessen:
im Modus `oauth2` erneuert die App serverseitig, im Modus `oidc` verlangt sie eine Sitzung, die eine
ExApp unter Impersonation nicht hat.

##### S5c: die Vorbedingung, die vor allen drei Pfaden steht, ist erfüllt

Die entscheidende Beobachtung ist die, die man leicht übersieht, weil sie eine Anwesenheit statt einer
Abwesenheit ist: **in jedem der sechs Läufe erscheint eine Listener-Zeile.** Die Prüfung
`if (!$this->userSession->isLoggedIn()) { return; }`, die in allen drei Listenern vor der ersten
Log-Zeile steht, hat also `true` geliefert. `OC::tryAppAPILogin` löst unter AppAPI-Impersonation eine
Nutzersitzung auf, die `IUserSession::isLoggedIn()` als angemeldet zählt.

**S5c ist damit beantwortet, und die Antwort ist der eine der beiden Ausgänge aus Annahme A9, der die
Diagnose der Ausgangsrecherche bestätigt statt sie zu ersetzen:** der Bruch liegt **nicht** vor der
Sitzungsfrage, sondern genau an ihr. Der Sitzungsspeicher trägt unter Impersonation kein Token
(`SESSION_TOKEN_KEY` leer), und das protokolliert `user_oidc` wörtlich als
`[TokenService] getToken: no session data`.

**Eine Zeile aus demselben Protokoll, die man nicht mit S5c verwechseln darf.** In den Läufen erscheint
außerdem, aus einem anderen Aufrufweg desselben Zeitfensters,
`[TokenService] checkLoginToken: user not logged in`. Sie stammt nicht aus einem der drei Listener und
sagt über `isLoggedIn()` im Ereignispfad nichts: die Listener-Zeile im selben Lauf beweist das
Gegenteil für den Pfad, um den es geht. Wer nur nach der Zeichenkette `not logged in` greift, liest
S5c genau falsch herum.

##### Die drei Ereignispfade aus K5, vollständig, mit dem getroffenen Pfad markiert

| Pfad | `sso_provider_type` | `token_exchange` | Ereignis und Listener | Braucht eine Sitzung? | In dieser Messung |
|---|---|---|---|---|---|
| 1 | `nextcloud_hub` | (nicht gelesen) | `InternalTokenRequestedEvent`, `InternalTokenRequestedListener` ruft `TokenService::getTokenFromOidcProviderApp($userId, ...)` mit einer Nutzer-Id | **nein**, dieser Pfad bricht an der Sitzungsfrage nicht | Lauf 5: der Listener läuft und stellt die Sitzungsfrage nicht, bricht aber hier an `oidc app is not installed`. **Ungemessen bleibt, ob er ein Token liefern würde**, weil die Server-App `oidc` (Nextcloud Hub als Anbieter) in dieser Umgebung nicht installiert ist |
| 2 | `external` | falsch | `ExternalTokenRequestedEvent`, `ExternalTokenRequestedListener`: ohne `store_login_token` `GetExternalTokenFailedException`, sonst `TokenService::getToken()` aus `SESSION_TOKEN_KEY` | **ja** | **getroffen**, Läufe 1, 2 und 6 |
| 3 | `external` | wahr | `ExchangedTokenRequestedEvent`, `TokenService::getExchangedToken()`: verlangt `store_login_token` (`TokenService.php:316-322`), danach `getToken()` aus der Sitzung (`TokenService.php:325-333`) | **ja** | **getroffen**, Läufe 3 und 4 |

Beide sitzungsgebundenen Pfade sind also getroffen und beide brechen, jeder mit seiner eigenen,
wörtlich unterscheidbaren Meldung. Der sitzungsfreie Pfad ist angelaufen, aber seine eigentliche Frage
bleibt hier offen; er steht in dieser Tabelle vollständig, damit der Bericht ihn nicht verschweigt und
auch nicht mehr behauptet, als gemessen ist.

**Eine Diskrepanz, die beim Nachfahren Zeit kostet und deshalb hier steht.** Die Meldung aus Lauf 3
sagt wörtlich `It can be enabled in config.php`. Der Quellcode liest den Wert aber als App-Konfigwert
(`TokenService.php:316`, `appConfig->getValueString(..., 'store_login_token', '0', lazy: true)`), und
gesetzt wurde er hier mit `occ config:app:set user_oidc store_login_token --value=1`. Der Weg über
`config.php` ist nicht der einzige und für ein Skript nicht der richtige.

##### Die Gegenprobe: derselbe Aufruf mit einer echten Sitzung aus der Keycloak-Anmeldung

Ohne diese Gegenprobe wäre jede 401 oben auch mit einer kaputten Keycloak-Kopplung erklärbar. Gefahren
ist deshalb derselbe Aufruf mit dem Sitzungscookie aus einer echten Anmeldung des Kontos `3855a8f7...`
über Keycloak, bei sonst identischer Konfiguration (`external`, `token_exchange 0`,
`store_login_token 1`):

| Beobachtung | Messwert |
|---|---|
| HTTP, Bytes | **401**, **341** Bytes, also ein **anderer** Körper als die 77 oben |
| Körper | `ocs.data.error` mit `"errorIdentifier":"urn:openproject-org:api:v3:errors:Unauthenticated"` |
| Sitzungsfrage | `[TokenService] getToken: token is still valid, it expires in 300 and refresh expires in 1800`, also **Sitzungsdaten vorhanden** |
| Erneuerung in `user_oidc` | `[TokenService] Refreshing the token: http://kc.localtest.me:8083/realms/spike/protocol/openid-connect/token`, dann `[TokenService] ---- Refresh token success`, dann `[TokenService] Store token in the session` |
| Übernahme in `integration_openproject` | `New token expires at 2026/08/29 02:38:56`, und danach steht am Konto ein `token` der Länge **1387** in JWT-Form mit `token_expires_at 1787971136` |
| Wo es endet | `OpenProject error : Client error: GET http://op.localtest.me:8082/api/v3/users/me resulted in a 401 Unauthorized response` |

**Die Gegenprobe gelingt an der Stelle, um die es geht, und sie liefert keine Daten, und beides gehört
in denselben Satz.** Sie gelingt an der Sitzungsfrage: dieselbe Konfiguration, dasselbe Konto,
derselbe Aufruf, und `getToken()` findet Daten statt `no session data`. Damit ist die einzige
Variable zwischen Hauptlauf und Gegenprobe das Sitzungscookie, und die Ursache der 401 in den Läufen 1
bis 6 ist gemessen und nicht erschlossen. Sie liefert keine Daten, weil OpenProject in dieser
Umgebung an dieselbe Keycloak-Instanz **nicht** gebunden ist: ein eigener Keycloak-Client für
OpenProject als Dienstkonto ist in `REQUIREMENTS.md` ausdrücklich Out of Scope, der Client
`openproject` in der Realm ist ausschließlich Zielgruppe des Austauschs. Deshalb weist OpenProject das
sonst gültige Token mit `urn:openproject-org:api:v3:errors:Unauthenticated` ab.

**Der Hauptlauf trägt damit den Vermerk: gegengeprobt auf die Sitzungsfrage, nicht gegengeprobt auf die
Datenlieferung.** Was S5 behauptet, ist die Sitzungsfrage, und die ist gegengeprobt. Was S5 nicht
behauptet und hier auch nicht belegt ist: dass ein OIDC-gebundenes Weg 0 mit einer Sitzung Daten
liefert.

##### Der Befund, der die Behauptung von S5 am schärfsten fasst

Zwei Läufe desselben Kontos, ohne Cookie, mit derselben Konfiguration, unterschieden nur dadurch, ob
der zwischengespeicherte Token noch gilt:

| Lauf, beide unter reiner Impersonation als `3855a8f7...` | `token_expires_at` beim Aufruf | HTTP, Bytes | `user_oidc` im Protokoll |
|---|---|---|---|
| Zwischenspeicher **gültig** (`1787971136`, Aufruf um `1787970877`) | 259 s in der Zukunft | **401**, **341** | **keine Zeile**, kein Ereignis, kein Listener |
| Zwischenspeicher **abgelaufen** (auf `0` gestellt) | abgelaufen | **401**, **77** | vier Zeilen, endend in `no session data` |

Der Grund steht in `getAccessToken()` an `v3.1.1`, Zeile 1748: liegt ein Token vor und ist es nicht
abgelaufen, gibt die Methode es zurück, ohne `user_oidc` überhaupt zu fragen. **Weg 0 trägt im Modus
`oidc` also genau so lange, wie der zwischengespeicherte Token gilt, und fällt danach auf 401.** Das
ist die Behauptung S5 in ihrer schärfsten Form, und sie ist mit einem Paar von Läufen belegt, das sich
in einer einzigen Zahl unterscheidet. Die 341 Bytes der ersten Zeile sind dabei kein Erfolg, sondern
die Abweisung durch OpenProject aus der Gegenprobe oben; die Aussage dieser Tabelle ist allein, dass
`user_oidc` im ersten Fall gar nicht befragt wird.

##### Was aus dieser Messung nach draußen geht, und was nicht

Derselbe Aufbau ist die Live-Reproduktion, an die D-08 den Kommentar zu
`nextcloud/user_oidc#925` gebunden hat. Sie ist gelungen: die Meldungen aus
`TokenService.php:318` und `:328` stehen wörtlich im Protokoll, und die Vorbedingung
`isLoggedIn()` ist gemessen statt vermutet. Der Entwurf liegt deshalb als
`docs/contrib/user-oidc-925-kommentar.md` im Repository, **unversendet**.

**Gesendet hat ihn niemand, und senden darf ihn ausschließlich der Owner.** Das Issue selbst
ist dabei richtig einzuordnen, sonst liest der Kommentar wie eine Fehlermeldung zu einem
erledigten Feature: `#925` ist die Anfrage, aus der die heutige Implementierung entstanden
ist, und der Entwurf ergänzt einen Fall, den sie nicht abdeckt, nämlich eine ExApp ohne
PHP-Anteil.

#### S6: die Byte-Kosten und der Feldsatz einer Antwort

**Behauptung:** Eine Antwort der Suchfläche trägt in kompakter Form die Felder, aus denen ein späteres
Werkzeug projizieren würde.

**Gemessen, ja, und die Zahl steht mit ihrer Bezugsgröße in Abschnitt 3.** Gemessen ist dieselbe
Antwort wie in S3, unter `bob` und vor der Gegenprobe von S4: **4746 Bytes** wie ausgeliefert, ohne
jeden Leerraum, davon **3895 Bytes in 49 HAL-Relationen** und **585 Bytes in 24 Feldern**. Die
Bezugsgröße derselben Instanz über die API v3, mit dem als solchen gekennzeichneten Aufbauzugang:
dieselbe Auskunft roh **15831 Bytes** und mit `select` **88 Bytes**.

**Die Gegenprobe zu S6** ist eine zweite Antwort unter einem anderen Konto, `alice` gegen ein
Arbeitspaket, das `opa` sehen darf: **2542 Bytes**, 27 Relationen, 22 Felder. Sie belegt, dass die
Bytezahl keine Eigenschaft der Fläche ist, sondern von Berechtigung und Modulsatz abhängt, und sie
verhindert, dass aus einer Einzelmessung ein Budget wird. Feldsatz, Relationenliste, die
`select`-Vergleichswerte und die Einordnung stehen vollständig in Abschnitt 3, weil sie dort für OD-04
gebraucht werden und hier nur als Messwert von S6 zählen.

#### Die Egress-Kontrollmessung

**Behauptung:** Der ExApp-Container erreicht OpenProject direkt, also bliebe Weg 1 als Rückfall offen.

Der Aufruf nimmt den Compose-Dienstnamen und nicht `op.localtest.me`, weil der ExApp-Container den
`extra_hosts`-Eintrag nicht hat: er wird vom Deploy-Daemon erzeugt und nicht von der Compose-Datei.

| Aufruf aus dem laufenden ExApp-Container | Messwert |
|------------------------------------------|----------|
| `GET http://openproject/api/v3` | **HTTP 400**, `text/plain`, 31 Bytes, wörtlich `Invalid host_name configuration`, `remote_ip 172.29.43.133` |
| derselbe Aufruf mit `Host: op.localtest.me:8082` | **HTTP 401**, `application/hal+json`, 153 Bytes, `urn:openproject-org:api:v3:errors:Unauthenticated`, `You need to be authenticated to access this resource.` |
| `GET http://op.localtest.me:8082/api/v3` | **kein Ergebnis**, `Connection refused`, Code `000` |
| `getent hosts` im ExApp-Container | `openproject` ist `172.29.43.133`, `op.localtest.me` ist `::1` |

**Messwert: Egress ist vorhanden.** Die zweite Zeile ist der eigentliche Beleg, und sie ist stärker als
eine 200 wäre: die Antwort trägt die Fehlerkennung der API v3 von OpenProject, also hat wirklich
OpenProject geantwortet und nicht irgendein Dienst. Die erste Zeile ist die Host-Prüfung von Rails und
schon selbst eine Antwort, also auch ein Erreichbarkeitsbeleg; nach dem Kriterium dieses Berichts wird
sie nach der Form beurteilt und nicht nach der 400.

Die dritte und vierte Zeile erklären zusammen, warum der Dienstname zu nehmen war: `op.localtest.me`
löst im ExApp-Container nach `::1` auf, das ist der Container selbst, und dort hört nichts. Das ist
dieselbe AAAA-Falle wie in 5.2 und 2.2, hier zum dritten Mal und in einem dritten Container gemessen.

**Einordnung, ohne die diese Zeile falsch gelesen wird:** im lokalen Docker-Netz ist eine Antwort
**erwartbar**, weil alle Container in einem Netz hängen und nichts sie trennt. Diese Messung beweist
über eine Behördeninstallation **nichts**: dort entscheiden Netzrichtlinien, Egress-Filter und
Proxy-Zwang, ob eine ExApp einen zweiten Host erreicht, und keine dieser Bedingungen ist hier
nachgebildet. Ein Satz "Egress vorhanden" ohne diesen Absatz liest wie eine Aussage über openDesk und
wäre Pitfall 3.

**Was daraus für die Egress-Kontrolle festzuhalten ist:** die ExApp **müsste** für Weg 1 einen zweiten
Host erreichen, für Weg 0 nicht. Weg 0 kommt mit einer einzigen Gegenstelle aus, und das ist die
Nextcloud, die sie ohnehin braucht; jede Verbindung zu OpenProject baut Nextcloud auf. Das ist der
Betriebsunterschied zwischen den zwei Wegen, der in einer abgeschotteten Umgebung zählt, und er ist
hier gemessen und nicht hergeleitet.

#### Die OCS-Fläche, aus der installierten Fassung gezählt

17 Routen, gelesen im Block `'ocs' => [` von `appinfo/routes.php` der installierten Fassung 3.1.1.
Präfix aller Zeilen: `/ocs/v2.php/apps/integration_openproject`.

| Verb | Pfad | Controller-Methode | Vorprüfung? | Rolle in diesem Bericht |
|------|------|--------------------|-------------|--------------------------|
| GET | `/fileinfo/{fileId}` | `files#getFileInfo` | n/a | nicht Teil der API-v1-Fläche |
| POST | `/filesinfo` | `files#getFilesInfo` | n/a | nicht Teil der API-v1-Fläche |
| GET | `/api/v1/notifications` | `getNotifications` | ja | nicht gemessen, kein Bedarf für OD-02 |
| DELETE | `/api/v1/work-packages/{id}/notifications` | `markNotificationAsRead` | ja | **schreibend, nicht ausgelöst** |
| GET | `/api/v1/url` | `getOpenProjectUrl` | **nein** (K3) | **S1**, gemessen |
| GET | `/api/v1/avatar` | `getOpenProjectAvatar` | nein | die einzige Methode mit `NoCsrfRequired`, nicht gemessen |
| GET | `/api/v1/work-packages` | `getSearchedWorkPackages` | ja | **S3** und **S6**, Plan 17-06 |
| POST | `/api/v1/work-packages` | `linkWorkPackageToFile` | ja | **schreibend, nicht ausgelöst** |
| GET | `/api/v1/work-packages/{id}/file-links` | `getWorkPackageFileLinks` | ja | für OD-04 der Kern des Unterscheidungsmerkmals |
| GET | `/api/v1/statuses/{id}` | `getOpenProjectWorkPackageStatus` | ja | nicht gemessen |
| GET | `/api/v1/types/{id}` | `getOpenProjectWorkPackageType` | ja | nicht gemessen |
| DELETE | `/api/v1/file-links/{id}` | `deleteFileLink` | ja | **destruktiv, nicht ausgelöst** |
| GET | `/api/v1/projects` | `getAvailableOpenProjectProjects` | ja | nicht gemessen |
| POST | `/api/v1/projects/{id}/work-packages/form` | `getOpenProjectWorkPackageForm` | ja | POST, fachlich lesend, **nicht ausgelöst**, um die Regel nicht aufzuweichen |
| GET | `/api/v1/projects/{id}/available-assignees` | `getAvailableAssigneesOfAProject` | ja | nicht gemessen |
| POST | `/api/v1/create/work-packages` | `createWorkPackage` | ja | **schreibend, nicht ausgelöst** |
| GET | `/api/v1/configuration` | `getOpenProjectConfiguration` | ja | **S2**, gemessen |

**Die vier nicht auszulösenden Routen sind namentlich** `POST /api/v1/work-packages`,
`POST /api/v1/create/work-packages`, `DELETE /api/v1/file-links/{id}` und
`DELETE /api/v1/work-packages/{id}/notifications`, dazu als fünfte, freiwillig ausgeschlossene
`POST /api/v1/projects/{id}/work-packages/form`. Das Messprotokoll dieses Plans enthält keinen Aufruf
auf eine davon: gefahren sind ausschließlich `GET /api/v1/url` und `GET /api/v1/configuration` sowie,
außerhalb der Fläche, `/ocs/v2.php/cloud/capabilities`.

**Die drei Lücken bleiben bestätigt:** es gibt **keine Route für ein einzelnes Arbeitspaket per Id**,
**keine für Kommentare** und **keine für "meine Arbeit"**. Was es dafür gibt, und was
`ARCHITECTURE.md` nicht führt, ist `GET /api/v1/work-packages/{id}/file-links`, also genau die Kette
Arbeitspaket zu Datei, die `research/FEATURES.md` als Unterscheidungsmerkmal nennt.

#### S0 bis S6, Stand nach diesem Plan

| # | Behauptung | Stand |
|---|-----------|-------|
| **S0** | Diese ExApp installiert und antwortet auf 33.0.7 wie auf 34.0.3 | **gemessen, ja.** Abschnitt 1.3, mit Gegenprobe (64 Nullen, 401/997) |
| **S1** | `GET /api/v1/url` antwortet unter reiner AppAPI-Impersonation mit OCS-JSON und der Adresse | **gemessen, ja.** 200, OCS-Umschlag, `data = http://op.localtest.me:8082`, als `alice`; Gegenprobe 64 Nullen 401 |
| **S2** | Die Berechtigung hängt am Nutzer, nicht an der App | **gemessen, ja.** `carol` 401 mit leerer Meldung aus der Vorprüfung, `alice` und `bob` je 200 mit Daten; die zwei 401-Formen sind unterscheidbar |
| **S3** | Konto A sieht in der Suche kein Arbeitspaket, das nur Konto B sehen darf | **gemessen, ja.** `alice` 200 mit 0 Treffern, `bob` 200 mit genau einem (`id 38`); Gegenproben: `Demo` liefert `alice` 14 Treffer ohne die 38, 64 Nullen 401/997, `carol` 401 mit leerer Meldung |
| **S4** | Nach künstlichem Ablauf antwortet der nächste Aufruf wieder mit Daten, ohne Browsersitzung | **gemessen, ja, und zweimal.** Gestellt an `bob`: `token_expires_at` 1787949020, künstlich 0, danach 1787950505 (7200 s), Aufruf dazwischen 200 mit einem Treffer, Tokenpaar ausgetauscht, kein Cookie und kein App-Passwort; Gegenprobe mit unbrauchbarem `refresh_token`: **401** samt `invalid_grant` im Protokoll. **Natürlich verstrichen an `alice`** (Nachtrag 29.08., kein `occ`-Eingriff): Ablauf 19623 s alt, Aufruf **200** mit einem Treffer, danach 1787975808 (7176 s). Der gestellte und der echte Ablauf sind gemessen deckungsgleich |
| **S5a** | Im Modus `oidc`, Pfad `external` ohne Austausch, fällt der Aufruf nach Ablauf auf 401 | **gemessen, ja.** 401 mit 77 Bytes und leerer Meldung, `token_expires_at` bleibt `0`, Token unverändert. Mit `store_login_token 1`: `[ExternalTokenRequestedListener] received request` und `[TokenService] getToken: no session data`; mit `0`: `Failed to get external token, login token is not stored` |
| **S5b** | Derselbe Bruch auf dem Pfad `external` **mit** Austausch, mit zwei unterscheidbaren Meldungen | **gemessen, ja, beide wörtlich.** `Failed to exchange token, storing the login token is disabled. It can be enabled in config.php` (`TokenService.php:318`) und `Failed to exchange token, no login token found in the session` (`TokenService.php:328`) |
| **S5c** | Liefert `isLoggedIn()` unter AppAPI-Impersonation `true`, oder bricht es schon davor? | **gemessen: `true`.** In jedem der sechs Läufe erscheint eine Listener-Zeile, also hat `if (!$this->userSession->isLoggedIn()) { return; }` nicht gegriffen. Der Bruch liegt an der Sitzungsfrage und nicht davor; die Diagnose aus `research/SUMMARY.md` ist damit bestätigt und nicht ersetzt. Gegenprobe mit echter Keycloak-Sitzung: derselbe Aufruf findet Sitzungsdaten (`token is still valid, it expires in 300`), gegengeprobt ist damit die Sitzungsfrage und nicht die Datenlieferung |
| **S6** | Eine Antwort trägt die Felder für ein späteres Werkzeug in kompakter Form | **gemessen.** 4746 Bytes als `bob`, ohne Leerraum, davon 3895 in 49 Relationen und 585 in 24 Feldern; Bezugsgröße API v3 roh 15831 gegen 88 Bytes mit `select`; Gegenprobe `alice` 2542 Bytes mit 27 Relationen. Vollständig in Abschnitt 3 |

Der Ausgangszustand für S4 ist mit Plan 17-05 hergestellt und gelesen worden: `alice` und `bob` trugen
je einen `refresh_token` und ein `token_expires_at` rund 7200 Sekunden in der Zukunft, und der Modus
ist `oauth2`, also der Zweig, in dem die App nach
`lib/Service/OpenProjectAPIService.php:1764-1765` serverseitig erneuert. Auf diesem Zustand ist S4
gefahren, und `bob` trägt danach absichtlich eine kaputte Verbindung; `alice` ist unberührt und ist
das verbundene Konto, mit dem Plan 17-07 arbeitet.

### 2.2 Weg 1: PKCE, `expires_in`, Erneuerung ohne Browsersitzung, Zwei-Konten-Negativbeweis

**Gemessen am 2026-08-28 (D-04, voller Consent-Fluss), lokal gegen die laufende Instanz OpenProject
17.7.2 aus dem Kopfblock, ausschließlich über `http://op.localtest.me:8082`.** Der Client ist die
OAuth-Anwendung `nc-mcp-spike-weg1` aus Abschnitt 5.3: **nicht vertraulich** (Häkchen "Confidential"
aus), Scope nur `api_v3`, Rückadresse `http://127.0.0.1:8099/callback`, Feld
`Client Credentials User ID` leer. Dass der Client nicht vertraulich ist, ist die Voraussetzung der
ersten Messung und keine Nachlässigkeit: `force_pkce` gilt wortwörtlich nur für nicht vertrauliche
Clients (K2 Punkt 1), ein vertraulicher Client hätte die falsche Frage beantwortet.

Kein Aufruf dieses Abschnitts benutzt den API-Schlüssel des Kontos `admin`, mit dem der Grundzustand
aus 5.3 entstanden ist. Jede Zeile nennt das Konto, unter dem sie lief.

**Nebenbefund vorweg: die Metadatenlücke ist auch lokal da, und sie ist ein Metadatenmangel und kein
Fähigkeitsmangel.** Beide Wohlbekannt-Dokumente der laufenden Instanz, mit `curl` vom Host geholt,
je Status 200:

```
GET /.well-known/oauth-authorization-server   -> 200
{"issuer":"http://op.localtest.me:8082",
 "authorization_endpoint":"http://op.localtest.me:8082/oauth/authorize",
 "token_endpoint":"http://op.localtest.me:8082/oauth/token",
 "introspection_endpoint":"http://op.localtest.me:8082/oauth/introspect",
 "scopes_supported":["api_v3","scim_v2","mcp","bcf_v2_1"],
 "response_types_supported":["code"],
 "grant_types_supported":["authorization_code","client_credentials","refresh_token"],
 "service_documentation":"https://www.openproject.org/docs/system-admin-guide/authentication/oauth-applications/?go_to_locale=en"}

GET /.well-known/oauth-protected-resource     -> 200
{"resource":"http://op.localtest.me:8082","resource_name":"OpenProject",
 "authorization_servers":["http://op.localtest.me:8082"],
 "scopes_supported":["scim_v2","mcp","bcf_v2_1","api_v3"],
 "bearer_methods_supported":["header"],
 "resource_documentation":"https://www.openproject.org/docs/api/?go_to_locale=en"}
```

Weder ein `registration_endpoint` noch ein `code_challenge_methods_supported` steht darin. Ein Client,
der sich allein nach diesen Dokumenten richtet, verzichtet also auf PKCE und wird abgewiesen: der
Messwert unten belegt beides in derselben Instanz. Der Grund liegt nicht in der Fähigkeit, sondern in
ihrer Bekanntmachung: `force_pkce` steht unbedingt in `config/initializers/doorkeeper.rb:90` am Tag
`v17.7.2` (K2). Diese Instanz ist dabei nicht der Sonderfall, die Dokumente der öffentlichen
Community-Instanz tragen dieselbe Lücke (17-RESEARCH.md, "Die Endpunkte und die Metadatenlücke").
Damit ist der Nebenbefund kein lokales Artefakt, und er geht als **Frage 9 in Abschnitt 4** auf die
ISV-Liste: das fehlende `code_challenge_methods_supported` ist der konkretere und dankbarere Beitrag
für den Community-Kanal als jede Beschwerde, weil die Fähigkeit vorhanden ist und nur die Ansage
fehlt.

**Zum Wort `client_credentials` im Dokument oben, und es ist der zweite Ort dieses Berichts, an den
der Griff aus Pitfall 2 gehört.** Der Grant steht in `grant_types_supported` der laufenden Instanz;
das ist ein wörtliches Zitat des Serverdokuments und keine Einladung. **Kein Aufruf dieses Abschnitts
hat diesen Grant benutzt**, und er könnte auch nichts liefern, was diese Phase braucht: das Feld
`Client Credentials User ID` der Anwendung ist leer geblieben (Abschnitt 5.3), und ohne einen Nutzer
darin gibt OpenProject auf diesem Grant kein Token im Namen eines Menschen aus. Ein Token aus
`client_credentials` wäre genau der Dienstkonto-Weg, der den Satz "der Assistent sieht niemals mehr
als der angemeldete Nutzer" unauffällig unwahr macht (Pitfall 1, T-17-03). Der Griff nach
`client_credentials` findet in diesem Bericht deshalb zwei Stellen, dieses Zitat samt diesem Absatz und
den Absatz in 5.3; jeder Treffer darüber hinaus ist ein Befund.

**Der Messweg des Hauptlaufs, in vier Schritten, alle mit `curl -4` vom Host und einem Cookie-Speicher
außerhalb des Repositoriums.** Verifier und Challenge kommen aus dem bestehenden Weg dieses Projekts
(`pkce()` in `scripts/oauth_flow_check.py:160-164`, per Import aufgerufen, keine Zeile geändert und
nichts neu erfunden); der Verifier ist 86 Zeichen lang, die Challenge nach S256 43 Zeichen.

| Schritt | Aufruf | Status | Was belegt ist |
|---------|--------|--------|----------------|
| 1 | `GET /login` | 200 | die Seite trägt zwei Formulare, beide mit `authenticity_token` (86 Zeichen); genommen wurde das des Formulars `user-login--form` |
| 2 | `POST /login` mit `username=opb`, Passwort aus `.env.spike-opendesk`, `authenticity_token` | 302 | Ziel ist **nicht** `/my/page`, sondern `/two_factor_authentication/request`; die Kette endet nach zwei weiteren 302 auf `/my/page`, und die Seite nennt oben rechts `Bob Spike` |
| 3 | `GET /oauth/authorize` mit `client_id`, `response_type=code`, `redirect_uri`, `scope=api_v3`, `state`, `code_challenge`, `code_challenge_method=S256` | 200 | die Zustimmungsseite, wortwörtlich `Authorize nc-mcp-spike-weg1 to use your account opb?` und `Full API v3 access`; das Formular trägt `code_challenge` und `code_challenge_method` als versteckte Felder weiter |
| 4 | `POST /oauth/authorize` mit denselben Parametern plus `authenticity_token` und `commit=Authorize`, ohne Weiterleitungen zu folgen | 302 | `Location: http://127.0.0.1:8099/callback?code=<43 Zeichen>&state=<der gesendete Wert>`; das `state` der Antwort ist Zeichen für Zeichen das gesendete |

Der Browser-Rückfall des Plans wurde **nicht** gebraucht: der Formularweg trug im ersten Versuch. Auf
dem Port 8099 hörte dabei nichts, und das musste es auch nicht, weil der Code aus dem
`Location`-Kopf gelesen wird und nicht aus einer Zustellung (T-17-02).

**Der Messwert, das Einlösen des Codes.** `POST /oauth/token`, mit `curl -d` und damit
`Content-Type: application/x-www-form-urlencoded` (Pflicht wegen `enforce_content_type`,
`doorkeeper.rb:55`), Parameter `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`,
`code_verifier`, und **ohne** `client_secret`, weil der Client öffentlich ist. Ebenfalls ohne jeden
Cookie-Speicher.

| Feld der Antwort | Gemessener Wert |
|------------------|-----------------|
| HTTP-Status | **200** |
| `token_type` | `Bearer` |
| `scope` | `api_v3` |
| `expires_in` | **7200**, Einheit Sekunden, also zwei Stunden |
| `created_at` | `1787938654` (Unix-Sekunden, 2026-08-28) |
| `access_token` | Länge **43** Zeichen, Präfix `rN3W` |
| `refresh_token` | Länge **43** Zeichen, Präfix `xK-Z` |
| Konto, unter dem der Lauf lief | **`opb`** |

**`expires_in` stimmt mit der Erwartung aus der Quelle überein.** Erwartet waren 7200 aus
`access_token_expires_in 2.hours` (`doorkeeper.rb:61-64`), gemessen sind 7200. Die Admin-Dokumentation
sagt dasselbe ("expire after two hours (default)"). Code, Dokumentation und Messwert nennen denselben
Wert, damit ist er belastbar. Der Wert ist trotzdem gemessen und nicht zitiert worden, weil
`custom_access_token_expires_in` im Initializer auskommentiert vorliegt (Zeile 73-75) und ein
Betreiber ihn setzen kann; in dieser Instanz hat es niemand getan.

**Der Nutzername ist nicht nur behauptet, er ist aus dem Token gemessen.** `GET /api/v3/users/me` mit
`Authorization: Bearer <access_token>` und **ohne** Cookie antwortet 200 und nennt `login opb`, `id 6`,
`admin` nicht gesetzt, `status active`. Das ist genau die Id, die 5.3 für Konto B nennt. Zwei
Gegenproben dazu, weil eine 200 auch von einer offenen Instanz kommen könnte: ein Bearer-Wert aus 43
Nullen antwortet 401 mit `errorIdentifier urn:openproject-org:api:v3:errors:Unauthenticated`, und
ohne den Kopf `Authorization` antwortet derselbe Aufruf ebenfalls 401.

**Ein 415 an diesem Endpunkt ist kein PKCE-Befund, und das ist gemessen statt vermutet.** Derselbe
Endpunkt, mit `Content-Type: application/json` und einem JSON-Körper aufgerufen, antwortet **415**
mit leerem Körper `{}`. Wer `enforce_content_type` übersieht, liest diese 415 als Abweisung des
Flusses; sie ist eine Abweisung der Verpackung. Die Zeile steht hier, damit ein Wiederholungslauf den
Unterschied kennt, bevor er ihn falsch deutet.

#### Die Gegenprobe, ohne die der Hauptlauf nichts beweist: derselbe Client ohne PKCE

Dieselbe Sitzung, dasselbe Konto `opb`, derselbe öffentliche Client, dieselben Parameter, nur **ohne
code_challenge** und ohne `code_challenge_method`:

```
GET /oauth/authorize?client_id=<Client>&response_type=code
   &redirect_uri=http://127.0.0.1:8099/callback&scope=api_v3&state=<zufällig>
   -> HTTP 400
   Text der Seite, vollständig: "An authorization error has occurred. Code challenge is required."
```

**Die Abweisung sitzt an `/oauth/authorize` und nicht erst an `/oauth/token`.** Der Lauf sieht die
Zustimmungsseite nie, es entsteht kein Autorisierungscode, und der `Location`-Kopf fehlt. Damit ist
belegt, dass der Hauptlauf oben nicht auch ohne PKCE funktioniert hätte: derselbe Aufruf mit
`code_challenge` in derselben Sitzung antwortete 200 und lieferte einen Code, ohne
`code_challenge` antwortet er 400 und liefert keinen. Die Antwort ist eine gerenderte HTML-Fehlerseite
mit dem Text oben und kein JSON, ein `error`-Feld gibt es an dieser Stelle also nicht; der Fehlertext
ist der Befund.

Das ist die Zeile, die die Metadatenlücke von oben teuer macht: das Dokument bewirbt PKCE nicht, der
Server verlangt es unbedingt. Ein Client, der sich nach dem Dokument richtet, sieht die 400 und keinen
Hinweis darauf, was ihm fehlt, es sei denn er liest den Text der Seite.

#### Die Erneuerung ohne Browsersitzung, und was dabei wirklich passiert

**Kein Cookie im Spiel.** Der Aufruf lief mit `curl -d` und ausdrücklich **ohne** `-b` und ohne `-c`,
also ohne jeden Cookie-Speicher, in einem Prozess, der keine Sitzung dieser Instanz kennt und nie eine
gekannt hat. Ohne diese Angabe würde der Lauf nichts über "ohne Browsersitzung" beweisen, weil ein
mitgeschickter Sitzungs-Cookie das Ergebnis alleine erklären könnte.

```
POST /oauth/token   (Content-Type: application/x-www-form-urlencoded)
   grant_type=refresh_token
   refresh_token=<Wert aus dem Hauptlauf>
   client_id=<Client>
   -> HTTP 200
   token_type Bearer | expires_in 7200 | scope api_v3
   access_token   Länge 43, Präfix IwAN   (verschieden vom vorherigen)
   refresh_token  Länge 43, Präfix E7kb   (verschieden vom vorherigen)
```

Ein neues `access_token` **und** ein neues `refresh_token`, wie `use_refresh_token`
(`doorkeeper.rb:115`) es erwarten lässt. Dass das erneuerte Token dieselbe Person trägt, ist nicht
angenommen, sondern gemessen: `GET /api/v3/users/me` mit dem neuen Token und ohne Cookie antwortet 200
und nennt `login opb`, `id 6`. Und das alte `access_token` ist sofort tot: derselbe Aufruf mit dem
Token aus dem Hauptlauf antwortet nach der Erneuerung **401**.

**Die zweite Gegenprobe fiel anders aus als erwartet, und das ist der interessanteste Befund dieses
Abschnitts.** Erwartet war, dass der verbrauchte `refresh_token` fehlschlägt. Gemessen hat er beim
ersten Wiedergebrauch **200** geliefert, mit einem zweiten, vollständig gültigen Tokenpaar. Ein
Bericht, der das als "Gegenprobe bestanden" abgehakt hätte, hätte die Instanz falsch beschrieben, und
zwar in einer Richtung, die für einen künftigen Client wichtig ist. Also ist der Mechanismus
nachgemessen worden, mit zwei Ketten, die sich in genau einem Schritt unterscheiden, unmittelbar
hintereinander im selben Lauf, damit verstrichene Zeit als Erklärung ausfällt:

| Kette | Erneuerung | Wird das **neue** `access_token` einmal benutzt | Alter `refresh_token` danach erneut |
|-------|-----------|------------------------------------------------|-------------------------------------|
| A | 200, neues Paar | ja, `GET /api/v3/users/me` -> 200 | **400** `invalid_grant` |
| B | 200, neues Paar | nein, gar nicht | **200**, ein weiteres vollständiges Paar |

**Der Auslöser der Entwertung ist damit gemessen: nicht die Erneuerung selbst und nicht die Zeit,
sondern der erste Gebrauch des neu ausgegebenen `access_token`.** Der Beleg aus der Instanz, der dazu
passt, steht in der laufenden Datenbank: `/app/db/structure.sql:4383` führt die Spalte
`previous_refresh_token` auf `oauth_access_tokens`. Diese Spalte ist die Bedingung, unter der
Doorkeeper die Entwertung des vorherigen `refresh_token` aufschiebt statt sie sofort auszuführen.
Wortwörtlich behauptet dieser Bericht über den fremden Code nur, dass die Spalte existiert; die
Verknüpfung mit dem Verhalten ist die Messung oben und keine Lesart des Quelltexts.

**Praktische Folge, und sie gehört zu OD-04 und nicht in diese Phase:** ein Client, der erneuert und
das neue Token wegwirft, ohne es zu benutzen, kann mit demselben `refresh_token` beliebig viele Paare
ziehen. Wer den Fluss so baut, dass nach der Erneuerung sofort ein Aufruf mit dem neuen Token folgt,
schließt das von selbst.

**Die Gegenprobe mit einem erfundenen Wert und mit einem wirklich entwerteten Wert, beide mit Status
und Fehlerfeld:**

| Aufruf | Status | `error` | Bedeutung |
|--------|--------|---------|-----------|
| `grant_type=refresh_token` mit einem Wert aus 43 Nullen | **400** | `invalid_grant` | ein erfundener Wert wird abgewiesen, der 200 des Hauptlaufs kommt also nicht davon, dass der Endpunkt alles annimmt |
| derselbe Aufruf mit dem entwerteten `refresh_token` der Kette A | **400** | `invalid_grant` | der verbrauchte Wert ist nach dem ersten Gebrauch des Nachfolgetokens endgültig tot, dreimal nachgefahren, dreimal 400 |

Der `error_description`-Text ist beide Male der Doorkeeper-Sammeltext, wortwörtlich "The provided
authorization grant is invalid, expired, revoked, does not match the redirection URI used in the
authorization request, or was issued to another client." Er unterscheidet die Ursachen nicht. Ein
Nebenbefund dazu, den dieser Bericht nur festhält und nicht erklärt: derselbe Fehler kam in einem Lauf
auf Deutsch und in einem anderen auf Englisch zurück, bei identischem Aufruf ohne Kopf
`Accept-Language`. Warum die Sprache wechselt, ist **ungemessen**.

#### Die vier Messwerte, die D-04 wörtlich verlangt, in einer Tabelle

| Messwert | Wie gemessen | Erwartung aus der Quelle | Gemessener Wert | Gegenprobe |
|----------|--------------|--------------------------|-----------------|------------|
| Nimmt `/oauth/authorize` PKCE an | Schritte 1 bis 4 oben, Konto `opb`, `code_challenge_method=S256`, Code eingelöst | 200 und ein Token, aus `force_pkce` (`doorkeeper.rb:90`) | **ja**: 200 auf der Zustimmungsseite, 302 mit `code` (43 Zeichen), 200 am Token-Endpunkt | derselbe Client **ohne code_challenge**, dieselbe Sitzung: **400** an `/oauth/authorize`, "Code challenge is required.", kein Code |
| `expires_in` | Feld der Antwort von `POST /oauth/token` | `7200`, aus `access_token_expires_in 2.hours` (`doorkeeper.rb:61-64`) | **7200 Sekunden** | Code, Admin-Dokumentation und Messwert nennen denselben Wert; `custom_access_token_expires_in` ist in dieser Instanz nicht gesetzt |
| Trägt die Erneuerung ohne Browsersitzung | `grant_type=refresh_token` an `/oauth/token`, **kein Cookie-Speicher**, kein `-b`, kein `-c` | neues Paar, aus `use_refresh_token` (`doorkeeper.rb:115`) | **ja**: 200, neues `access_token` und neues `refresh_token`, `expires_in` wieder 7200, `login opb` aus dem neuen Token | erfundener Wert: 400 `invalid_grant`. Entwerteter Wert: 400 `invalid_grant`. Der Zeitpunkt der Entwertung ist mit zwei Ketten gemessen (Tabelle oben) |
| Zwei-Konten-Negativbeweis (D-05) | `GET /api/v3/work_packages/38` mit dem Token von `opb` und mit dem von `opa`, dazu eine erfundene Id | 404 mit `urn:openproject-org:api:v3:errors:NotFound`, nicht 403 | **404** für `opa`, **200** für `opb`, und die 404 ist von der auf eine nicht existierende Id nicht zu unterscheiden | der Lauf unter `opb` liefert 200 mit dem richtigen Betreff; ohne ihn wäre die 404 auch eine falsche Id. Dazu die erfundene Id 999999999 als zweite Gegenprobe |

#### Der Zwei-Konten-Negativbeweis auf Weg 1 (D-05)

Das zweite Token entstand auf demselben Weg wie das erste: eigener Cookie-Speicher, eigener Verifier,
eigene Zustimmungsseite, Schritte 1 bis 4 unverändert. Beide Läufe endeten mit 200 am Token-Endpunkt,
`expires_in` 7200, `scope api_v3`, `access_token` je 43 Zeichen. Ein Nebenbefund aus dem Lauf von
`opa`: die Anmeldung landete auf `/?first_time_user=true`, es war die erste Anmeldung dieses Kontos
überhaupt, und der Consent-Fluss trug trotzdem im ersten Versuch.

**Wer die Tokens tragen, ist aus den Tokens gemessen und nicht aus dem Skript geschlossen.**
`GET /api/v3/users/me` mit `Authorization: Bearer` und ohne Cookie: das eine Token nennt `login opb`,
`id 6`, das andere `login opa`, `id 5`. Beide `admin` nicht gesetzt. Das sind genau die zwei Ids, die
Abschnitt 5.3 für Konto B und Konto A nennt, und Mitglied des privaten Projekts `spike-privat-b`
(id 3) ist laut 5.3 **nur** `opb`.

| Aufruf | Konto | Status | `errorIdentifier` | Bedeutung |
|--------|-------|--------|-------------------|-----------|
| `GET /api/v3/work_packages/38` | `opb` (Mitglied) | **200** | keiner | die Id ist richtig und das Arbeitspaket existiert: `subject` ist `SPIKE-OD-8471 privat`, `project` ist `Spike Privat B`. Ohne diese Zeile wäre jede 404 unten auch mit einer falschen Id erklärbar |
| `GET /api/v3/work_packages/38` | `opa` (kein Mitglied) | **404** | `urn:openproject-org:api:v3:errors:NotFound` | die Berechtigungsgrenze hält auf Weg 1, unter dem Token des Kontos selbst und nicht unter einem Dienstkonto |
| `GET /api/v3/work_packages/999999999` | `opa` | **404** | `urn:openproject-org:api:v3:errors:NotFound` | dieselbe Antwort wie in der Zeile darüber, und zwar Byte für Byte: je 166 Bytes, gleicher SHA-256 (`96f26f0149c7be10...`), `cmp` meldet keinen Unterschied. OpenProject verrät die Existenz also nicht |

Die `message` ist in beiden 404 wortwörtlich "The work package you are looking for cannot be found or
has been deleted." Kein 403 an keiner Stelle, und kein Unterschied zwischen "gibt es nicht" und "darfst
du nicht".

**Dieselbe Grenze, zwei Ebenen höher gemessen, weil eine Einzelressource allein eine Ausnahme sein
könnte:**

| Aufruf | `opb` | `opa` |
|--------|-------|-------|
| `GET /api/v3/projects/3` | 200 | **404**, `urn:openproject-org:api:v3:errors:NotFound` |
| `GET /api/v3/projects/3/work_packages` | 200, `total 1`, Ids `[38]` | **404**, dieselbe Fehlerkennung |
| `GET /api/v3/work_packages?pageSize=100` | 200, `total 34`, enthält 38 | 200, `total 33`, enthält 38 **nicht** |

Die letzte Zeile ist die aussagekräftigste, weil sie nicht auf eine Id zielt, sondern die Liste
vergleicht: derselbe Endpunkt, dieselbe Seitengröße, ein Arbeitspaket Unterschied, und der Unterschied
ist genau das private. Ein Berechtigungsleck, das eine Einzelabfrage abweist und die Liste nicht,
wäre hier sichtbar geworden.

**Dieselbe Eigenschaft, dieselbe Sprache wie beim DAV-Nachweis dieses Projekts.**
`docs/spike-dav.md` belegt für Nextcloud-Dateien: bob kennt den genauen Pfad von alices Datei, nichts
als die Berechtigungsprüfung steht dazwischen, und die Antwort ist "`404`, never `200`". Für
OpenProject-Arbeitspakete gilt auf Weg 1 wortwörtlich dasselbe: `opa` kennt die genaue Id, und die
Antwort ist 404 und nie 200, ohne Unterschied zu einer Id, die es nicht gibt. Beide Negativbeweise
lassen sich damit in einem Satz führen, und beide gelten unter dem Konto selbst und nicht unter einem
Dienstkonto.

#### Abschluss von 2.2: Leistung, Kosten, und was der lokale Aufbau nicht reproduziert

**Was Weg 1 gemessen leistet.** Ein eigener Autorisierungscode je Nutzer trägt vollständig: PKCE ist
Pflicht und die Pflicht ist mit ihrer Gegenprobe belegt, das Token lebt gemessene 7200 Sekunden, die
Erneuerung trägt ohne jeden Cookie und ohne Browsersitzung, und die Berechtigungsgrenze des
angemeldeten Nutzers hält bis auf die Ebene der Liste, ohne dass irgendwo ein Dienstkonto oder ein
Administratorschlüssel im Spiel wäre.

**Was Weg 1 kostet.** Einen Zustimmungsschritt im Browser je Nutzer, der nicht wegzuautomatisieren ist,
weil `/oauth/authorize` eine OpenProject-Sitzung verlangt (`resource_owner_authenticator`,
`doorkeeper.rb:35-39`); einen zweiten OAuth-Client, den ein Betreiber in der OpenProject-Verwaltung
von Hand anlegen muss, weil sich zu 17.7.2 kein dokumentierter Weg zum Seeden einer OAuth-Anwendung
finden ließ und `registration_endpoint` in den Metadaten fehlt; und ein zweites Tokenlager neben dem
bestehenden, samt der Erneuerungsregel aus dem Befund oben.

**Was der lokale Aufbau ausdrücklich nicht reproduziert, und deshalb steht in diesem Abschnitt kein
Satz, der "in openDesk" sagt und auf einen der Messwerte oben zeigt.** In openDesk gibt es wegen
`OPENPROJECT_OMNIAUTH__DIRECT__LOGIN__PROVIDER: "keycloak"` kein lokales Anmeldeformular; genau dieses
Formular ist aber der zweite Schritt des gemessenen Messwegs oben. Der Zustimmungsfluss hat dort einen
zusätzlichen Umleitungsschritt über Keycloak, und dieser Schritt ist hier **ungemessen**. Ebenfalls
ungemessen ist die Scope-Pflicht für ein OIDC-JWT (`scope`-Anspruch mit `api_v3`, Breaking Change in
OpenProject 16.0.0): im lokalen OAuth-Modus, in dem alle Messwerte oben entstanden sind, ist sie
unsichtbar, weil OpenProject die Tokens selbst ausgibt. Beide Punkte gehören auf die ISV-Liste in
Abschnitt 4 und nicht in die Messwerttabelle.

**Aufräumen, und es ist gegengeprobt.** Alle in diesem Abschnitt entstandenen Tokens sind nach der
letzten Messung über `POST /oauth/revoke` widerrufen worden, zwanzig Werte, je Status 200. Die
Gegenprobe: `GET /api/v3/users/me` mit dem Token von `opb` und mit dem von `opa` antwortet danach je
**401**. Die Cookie-Speicher und die Zwischendateien lagen unter dem Temporärverzeichnis und niemals im
Repositorium; sie sind gelöscht. Kein Wert steht in diesem Bericht, nur Längen, Vier-Zeichen-Präfixe,
Statuscodes und Feldnamen (T-17-01).

### 2.3 Die SSRF-Grenze und was sie wirklich abdeckt

**Gemessen (D-06), im laufenden ExApp-Container, mit demselben Resolver, den die Produktion benutzt, und ohne eine Zeile Produktionscode zu ändern.** Der Container ist `nc_app_mcp_connector`, Zustand `running`, Bildmarke `127.0.0.1:5001/mcp_connector:0.1.11`, Netz `nc-mcp-spike-od-net`. Die Messung importiert `mcp_connector.oauth.cimd` und ruft es auf; sie legt keine Test-Datei an, ändert keinen Import und schreibt nichts in `src/`.

**Erste Zeile, die Auflösung der Nachbardienste.** `cimd._system_addresses(<name>, 80)`:

```
_system_addresses('nextcloud', 80)   -> ['172.29.43.129']
_system_addresses('caddy', 80)       -> ['172.29.43.10']
_system_addresses('appapi-harp', 80) -> ['172.29.43.131']
_system_addresses('openproject', 80) -> raised gaierror
```

Die drei laufenden Nachbardienste stehen unter ihrem Compose-Dienstnamen für private Adressen aus `172.29.43.0/24`, genau wie erwartet. Der Name `openproject` löst nicht auf, und das ist kein Fehlschlag der Messung, sondern der Zustand der Stufe: das Profil `op` ist in diesem Plan nicht gestartet, und Docker gibt einem Dienst ohne laufenden Container keinen DNS-Eintrag. Diese Zeile ist ausdrücklich mitgemessen und mitgeschrieben, weil sie sonst in der dritten Zeile als scheinbare Sperrung wiederkehrt.

**Zweite Zeile, dieselben Adressliterale durch `cimd.target_allowed()`.** Erwartung `False`, gemessen `False`, samt der beiden Flags, an denen es liegt:

```
target_allowed(172.29.43.129) -> False   [nextcloud,    is_private=True, is_global=False]
target_allowed(172.29.43.10)  -> False   [caddy,        is_private=True, is_global=False]
target_allowed(172.29.43.131) -> False   [appapi-harp,  is_private=True, is_global=False]
target_allowed(172.29.43.10)  -> False   [Literal desselben /24]
target_allowed(172.29.43.128) -> False   [Literal desselben /24]
target_allowed(172.29.43.254) -> False   [Literal desselben /24]
```

Die drei Literale am Ende sind der Ersatz für den Namen, der heute nicht auflöst: die Adresse, die `openproject` bekommen wird, liegt in demselben `/24`, und für dieses `/24` ist die Antwort an beiden Rändern und in der Mitte gemessen. Damit steht der Befund für OpenProject fest, ohne dass dieser Plan Stufe B hochfahren muss.

Der Negativkatalog dazu ist der bestehende aus `tests/unit/test_oauth_cimd.py` (Zeilen 179 bis 202) und kein neu erfundener. Im selben Container gefahren: 12 von 12 Adressen des Katalogs abgelehnt, 3 von 3 Adressen der Positivliste zugelassen, keine unerwartete Abweichung. Der Katalog trägt die drei gemessenen Lücken, an denen ein einzelnes Flag nicht reicht (`100.64.0.1`, `64:ff9b::7f00:1`, `224.0.0.1`); die Prüfung ist deshalb eine Konjunktion aus sieben Fragen und nicht ein Flag.

**Dritte Zeile, `cimd.resolve_addresses()`, also die ganze Grenze.** Erwartung `None`, gemessen `None`, und die Logzeile sagt, welche der beiden Ursachen zutrifft:

```
resolve_addresses('nextcloud', 80)   -> None    LOG: a document target was refused: an address of it is not public
resolve_addresses('caddy', 80)       -> None    LOG: a document target was refused: an address of it is not public
resolve_addresses('appapi-harp', 80) -> None    LOG: a document target was refused: an address of it is not public
resolve_addresses('openproject', 80) -> None    LOG: a document target did not resolve: gaierror
```

Die vierte Zeile ist der Grund, warum die Unterscheidung im Protokoll steht: derselbe Rückgabewert `None`, aber eine andere Ursache. Drei Namen wurden von der Regel abgelehnt, einer war überhaupt nicht auflösbar. Ein Bericht, der nur `None` notiert, hätte einen Resolver-Fehlschlag als Sperrung gelesen.

Dazu die Regel, die den Befund über die Einzeladresse hinaus trägt: `resolve_addresses` verwirft den **ganzen Namen**, sobald **eine** seiner Adressen abgelehnt wird (`cimd.py`, Docstring: "Not 'take the good one'"). Ein Name, der auf eine öffentliche und eine private Adresse zeigt, ist damit vollständig gesperrt und nicht teilweise erlaubt.

**Gegenprobe, ohne die der Messwert nichts beweist.** Im selben Lauf, im selben Container, mit demselben Resolver, zwei öffentliche Namen:

```
resolve_addresses('one.one.one.one', 443) -> ['1.0.0.1', '1.1.1.1', '2606:4700:4700::1111', '2606:4700:4700::1001']
resolve_addresses('example.com', 443)     -> ['172.66.147.243', '104.20.23.154', '2606:4700:10::ac42:93f3', '2606:4700:10::6814:179a']
```

Beide liefern eine Adressliste. Damit ist das dreifache `None` oben nicht mit einem kaputten Resolver im Container erklärbar, und die Sperrung ist die Regel und nicht die Umgebung.

**Die Einordnung, und sie ist der eigentliche Wert dieser Messung.** Die Grenze sitzt nicht auf dem Weg zu einem fremden Host, sondern auf dem Weg zum Client-Id-Metadatendokument eines fremden OAuth-Clients. `cimd.py` sagt das im eigenen Modul-Docstring: es ist die erste und bislang einzige Stelle dieses Projekts, an der eine Anfrage das Ziel einer ausgehenden Anfrage von uns wählt; jeder andere Aufruf geht an die konfigurierte Nextcloud, weil die Basis-URL aus `NC_MCP_URL` kommt und nie aus einer Anfrage. Der in dieser Phase gemessene Zugriffsweg auf OpenProject berührt diese Grenze überhaupt nicht, weil es keine zweite Basis-URL gibt: Weg 0 läuft über Nextcloud, und Nextcloud ist die konfigurierte Basis. Wer aus dem Messwert oben liest, dieser Connector könne OpenProject im Cluster nicht erreichen, liest eine Aussage über einen Weg, den es heute nicht gibt.

**Der Entwurfsbefund für OD-04.** Er verlangt keine Codeänderung in dieser Phase und ist die Entscheidung, die v2.0 zu treffen hat. Wer `target_allowed` für eine zweite Basis-URL wiederverwendet, sperrt jede Cluster-Installation aus: die Messung oben ist genau der Fall, und sie fällt in einer openDesk-Installation nicht anders aus als hier, weil ein Dienst im selben Cluster immer eine private Adresse trägt. Wer sie nicht wiederverwendet, braucht eine eigene, ausdrücklich begründete Prüfung für eine URL, die aus den Admin-Einstellungen und niemals aus einer Anfrage kommt: die Begründung ist der Unterschied zwischen einer Adresse, die ein Angreifer wählt, und einer, die ein Administrator einträgt. Beide Wege sind vertretbar, ein stilles Wiederverwenden ist es nicht.

### 2.4 Welcher Weg trägt, als Folge dieser Messungen

Dieser Abschnitt zieht eine Folgerung und führt kein Argument. Jeder Satz zeigt auf eine Messzeile aus
Abschnitt 2.1, Abschnitt 2.2 oder Abschnitt 2.3, und wo eine Messung nicht weit genug reicht, steht das
im selben Satz und nicht in einer Fußnote. Die Überschriften `### 2.4` und `### 2.5` sind Ankerpunkte:
1.4, 3.3 und Abschnitt 4 verweisen namentlich auf sie, wer sie umbenennt, macht diese Verweise falsch.

**Was Weg 0 gemessen leistet, in der Reihenfolge der Behauptungen.** Die Fläche antwortet unter reiner
AppAPI-Impersonation mit App-Code und nicht mit einer Loginseite: S1 in Abschnitt 2.1 liefert 200 mit
OCS-Umschlag und `ocs.data = http://op.localtest.me:8082` als `alice`, und die Gegenprobe mit einem
`APP_SECRET` aus 64 Nullen antwortet 401 mit `statuscode 997`. Die Berechtigung hängt am Nutzer und
nicht an der App: S2 misst `carol` (nie verbunden) mit 401 und **leerer** Meldung aus
`validatePreRequestConditions()` gegen `alice` mit 200 und 1702 Bytes und `bob` mit 200 und 1700 Bytes,
und die zwei 401-Formen sind unterscheidbar. Die Grenze zwischen zwei Konten hält auf dieser Fläche:
S3 liefert `alice` 200 mit 0 Treffern und `bob` 200 mit genau einem (`id 38`), während dieselbe `alice`
auf das Suchwort `Demo` 14 Treffer bekommt, unter denen die 38 nicht ist. Die serverseitige Erneuerung
trägt ohne Browsersitzung, und zwar zweimal: S4 an `bob` nach künstlichem Ablauf (200 mit einem
Treffer, `token_expires_at` danach 7200 Sekunden weiter, Tokenpaar ausgetauscht, kein Cookie und kein
App-Passwort) und an `alice` nach 19623 Sekunden **natürlich** verstrichenem Ablauf, ohne jeden
`occ`-Eingriff (200, 2542 Bytes, danach 7176 Sekunden weiter). Die Antwort trägt die Felder, aus denen
ein Werkzeug projizieren würde: S6 misst 4746 Bytes als `bob`, davon 3895 in 49 Relationen und 585 in
24 Feldern. Dazu der Betriebswert aus derselben Messreihe: Weg 0 kommt mit **einer** Gegenstelle aus,
weil jede Verbindung zu OpenProject von Nextcloud aufgebaut wird (Egress-Kontrollmessung in
Abschnitt 2.1).

**Wo Weg 0 gemessen kippt, und wo er nicht widerlegt, sondern ungemessen ist.** Im Modus `oidc` fällt
der Aufruf nach Ablauf des zwischengespeicherten Tokens auf 401 mit 77 Bytes, in allen sechs Läufen von
S5, und die Bruchstelle ist die Sitzungsfrage und nicht die Impersonation: S5c misst, dass in jedem
Lauf die Listener-Zeile hinter `isLoggedIn()` erscheint, S5a und S5b tragen dazu die wörtlichen
Meldungen `getToken: no session data` und `Failed to exchange token, no login token found in the
session`. Solange das zwischengespeicherte Token **gültig** ist, kippt gar nichts: der Lauf in 5.6.5
gegen ein `token_expires_at` 259 Sekunden in der Zukunft erzeugt **keine einzige** Zeile der App
`user_oidc`, die App fragt den Anbieter also nicht. Gemessen ist damit, dass Weg 0 im Modus `oidc`
genau so lange trägt, wie das zwischengespeicherte Token gilt, und dass die Erneuerung auf den zwei
Pfaden `external` bricht; ob nach der Erneuerung Daten kämen, ist an derselben Stelle **ungemessen**,
weil OpenProject in dieser Umgebung nicht an dieselbe Keycloak gebunden ist und der Lauf mit Sitzung
deshalb an OpenProjects `Unauthenticated` endet (341 Bytes). Der dritte Pfad, `sso_provider_type =
nextcloud_hub`, ist der einzige sitzungsfreie: Lauf 5 zeigt den `InternalTokenRequestedListener` und
**keine** Zeile über eine Sitzung, er bricht hier an `oidc app is not installed`, weil die Server-App
fehlt, die Nextcloud selbst zum Anbieter macht. Ein Satz "Weg 0 trägt unter OIDC nicht" ginge deshalb
um genau diesen Pfad über die Messung hinaus; er steht als **ungemessen** in 2.5 und nicht als
widerlegt.

**Die Stelle, an der die Weg-0-Fläche für den Zweck von OD-04 unerprobt ist, und sie gehört in diesen
Satz und nicht in eine Fußnote.** Von den 17 OCS-Routen ist
`GET /api/v1/work-packages/{id}/file-links` die einzige, die eine Id eines Arbeitspakets annimmt, und
sie ist zugleich die Kette Arbeitspaket zu Datei, die `research/FEATURES.md` als Unterscheidungsmerkmal
dieser App führt. Belegt sind ihre Existenz und ihre Signatur aus `appinfo/routes.php` der
installierten Fassung 3.1.1; **gemessen ist an ihr nichts**, weil die Instanz gemessen keine
registrierte Ablage hat (`GET /api/v3/storages` antwortet 200 mit `total 0` und `count 0`, 5.5.1). Wer
Weg 0 wählt, wählt ihn mit dieser offenen Stelle, und der Grund dafür hängt an derselben Ursache wie
Weg A des Einrichtungswegs (2.5).

**Was Weg 1 gemessen leistet.** PKCE ist Pflicht, und die Pflicht steht mit ihrer Gegenprobe da:
Abschnitt 2.2 misst mit `code_challenge` 200 auf der Zustimmungsseite und einen Code von 43 Zeichen,
ohne `code_challenge` in derselben Sitzung **400** mit dem Text `Code challenge is required.` und ohne
jeden Code. Das Token lebt gemessene `expires_in` **7200** Sekunden, derselbe Wert, den 2.1 über die
Restlaufzeiten der zwei Weg-0-Konten unabhängig bestätigt. Die Erneuerung trägt ohne Browsersitzung: 200
mit neuem Paar, gefahren ohne `-b` und ohne `-c`, und das neue Token nennt an `GET /api/v3/users/me`
wieder `login opb`, `id 6`. Der Zwei-Konten-Negativbeweis hält bis auf die Ebene der Liste: `opb` 200
auf `/api/v3/work_packages/38`, `opa` 404 mit derselben Fehlerkennung und Byte für Byte derselben
Antwort wie auf eine erfundene Id, und dieselbe Liste trägt für `opb` `total 34` mit der 38 und für
`opa` `total 33` ohne sie.

**Was Weg 1 gemessen kostet.** Einen Zustimmungsschritt im Browser je Nutzer, der nicht
wegzuautomatisieren ist, weil `/oauth/authorize` eine OpenProject-Sitzung verlangt und die
Zustimmungsseite wortwörtlich `Authorize nc-mcp-spike-weg1 to use your account opb?` fragt (2.2);
einen zweiten OAuth-Client, den ein Betreiber von Hand anlegen muss, weil das Dokument
`/.well-known/oauth-authorization-server` der laufenden Instanz gemessen **keinen**
`registration_endpoint` nennt; ein zweites Tokenlager samt der Erneuerungsregel aus dem Befund, dass
der alte `refresh_token` erst mit dem ersten Gebrauch des neuen `access_token` stirbt (Kette A 400,
Kette B 200); und eine zweite Gegenstelle im Egress, denn die Egress-Kontrollmessung in Abschnitt 2.1
misst den zweiten Host als eigene Verbindung des ExApp-Containers (400 `Invalid host_name
configuration`, mit `Host`-Kopf 401 in `application/hal+json`).

**Was die SSRF-Messung für einen künftigen zweiten Zugriffsweg bedeutet.** Abschnitt 2.3 misst im
laufenden ExApp-Container, dass `resolve_addresses()` jeden Nachbardienst unter seinem Compose-Namen
verwirft (dreimal `None` mit der Logzeile `an address of it is not public`), während `one.one.one.one`
und `example.com` im selben Lauf Adresslisten liefern. Die Folgerung daraus ist keine über heute,
sondern eine über OD-04: die Grenze sitzt heute ausschließlich am Metadatendokument eines fremden
OAuth-Clients, und der in dieser Phase gemessene Zugriffsweg berührt sie nicht, weil Weg 0 über die
konfigurierte Nextcloud läuft. Wer für einen zweiten Zugriffsweg `target_allowed` unbesehen
wiederverwendet, sperrt jede Cluster-Installation aus, und die Messung oben ist genau dieser Fall; wer
sie nicht wiederverwendet, braucht eine eigene, ausdrücklich begründete Prüfung für eine URL, die aus
den Admin-Einstellungen und niemals aus einer Anfrage kommt.

**Die Folgerung, mit ihrer Bedingung im selben Satz.** Läuft `integration_openproject` im Modus
`oauth2`, trägt Weg 0 den Zugriff, den OD-04 braucht, gemessen vollständig (S1 bis S4 und S6) und
zugleich billiger als Weg 1, weil er ohne Zustimmungsschritt je Nutzer, ohne zweiten OAuth-Client und
mit einer einzigen Gegenstelle auskommt; läuft es im Modus `oidc`, trägt Weg 0 gemessen so lange, wie
das zwischengespeicherte Token gilt, und für die Zeit danach hat diese Phase auf zwei der drei Pfade
einen gemessenen Bruch und auf dem dritten keinen Messwert. Weg 1 trägt in beiden Fällen, weil er die
Betriebsart von `integration_openproject` nicht berührt, und er trägt gemessen mit einem Negativbeweis,
der so scharf ist wie der DAV-Nachweis dieses Projekts; er kostet dafür genau die vier Posten aus dem
Absatz oben. Eine Wahl zwischen beiden trifft dieser Bericht nicht: sie ist OD-04 und fällt nach dem
ISV-Call.

**Zwei offene Fragen tragen diese Folgerung mit, und beide sind ausdrücklich nicht gemessen.** Erstens
die Betriebsart, die openDesk wirklich fährt: ob `integration_openproject` dort im Modus `oauth2` oder
`oidc` läuft und, wenn `oidc`, auf welchem der drei Pfade, ist aus Quellen nicht entscheidbar (1.4) und
steht als **Frage 7** in Abschnitt 4. Von dieser Antwort hängt ab, welcher der zwei Zweige des Absatzes
oben überhaupt gilt. Zweitens die Stabilitätszusage der OCS-Fläche: die 17 Routen sind aus
`appinfo/routes.php` der installierten Fassung 3.1.1 gezählt (Abschnitt 2.1), das ist ein Messwert über
diese Fassung und keine Zusage über die nächste. Der Rückkanal dazu ist offen (D-11): der Forumsbeitrag
hat am 28.08. eine Antwort von `christianlupus` bekommen, eine Zusage über die Stabilität der Fläche
steht darin nicht, und die Konto-Anfrage an die OpenProject-Community liegt als unversendeter Entwurf.
Ein tragender Weg 0 und eine offene Stabilitätsfrage sind kein Widerspruch: gemessen ist, was die
Fläche heute tut, nicht was sie morgen zusagt.

### 2.5 Was ungemessen blieb, und warum die Messung nicht möglich war

Diese Tabelle sammelt **jeden** Punkt, den dieser Bericht als `ungemessen` führt, damit der Leser sie
an einer Stelle findet und nicht über sieben Abschnitte hinweg zusammensuchen muss. Kein Punkt steht
hier als `verworfen`: eine nicht durchgeführte Messung widerlegt nichts (D-03,
ROADMAP-Erfolgskriterium 3). Die Spalte "Was es bräuchte" ist eine Kostenschätzung und keine Anleitung,
weil eine Anleitung einen Versuch voraussetzte, den diese Phase nicht unternommen hat.

| Punkt | Zustand | Grund, warum die Messung nicht möglich war | Was es bräuchte |
|-------|---------|--------------------------------------------|-----------------|
| Weg A des Einrichtungswegs (Ablagen-Assistent von OpenProject, derselbe Weg, den der openDesk-Bootstrap-Job geht), 2.1 und 5.4 | **ungemessen** | Gemessen am 2026-08-28: `NextcloudCompatibleHostValidator` weist alle vier Namen ab, unter denen Nextcloud hier zu erreichen wäre (`safe_ip? = nil`, Erlaubnisliste leer), während die zwei Netzaufrufe danach beide 200 liefern. Der Schlüssel `OPENPROJECT_SSRF__PROTECTION__IP__ALLOWLIST` trägt `writable: false` und ist nur über die Umgebung des Containers setzbar; D-03 verbietet den Eingriff, und er hätte den in 5.3 aufgebauten Grundzustand riskiert | Die Erlaubnisliste in `compose.spike-opendesk.yml` setzen (mindestens `127.0.0.0/8` und `172.16.0.0/12`, OpenProject-Container neu erzeugen) und einen Namen, der aus dem Browser **und** serverseitig aus dem OpenProject-Container an dieselbe Nextcloud führt (Caddy-Site-Block auf `:8091`, `extra_hosts`, Trusted-Domain). Der Ausgang des zweiten Schritts ist offen, weil `SsrfProtection` über `Resolv::DNS` auflöst und damit ohne `/etc/hosts` (DI-17-03) |
| `GET /api/v1/work-packages/{id}/file-links`, die für OD-04 wertvollste Route, 3.3 und 5.5.1 | **ungemessen**, belegt sind nur Existenz und Signatur | Die Route setzt eine registrierte Ablage voraus. `GET /api/v3/storages` antwortet gemessen 200 mit `total 0` und `count 0`; ohne Ablage gäbe ein Aufruf eine leere Liste zurück, die über das Verhalten der Route nichts aussagt. Dieselbe fehlende Ablage ist der Grund, warum die Suche in S3 ohne `isSmartPicker=true` für **beide** Konten null Treffer liefert | Eine registrierte Ablage, und die anzulegen ist genau Weg A aus der Zeile darüber. Solange Weg A ungemessen bleibt, bleibt auch diese Route ungemessen (DI-17-04) |
| Der OIDC-Pfad `sso_provider_type = nextcloud_hub`, der einzige sitzungsfreie, 2.1 und 5.6.4 | **ungemessen**, ob er ein Token liefert; **gemessen**, dass er die Sitzungsfrage nicht stellt | Lauf 5 zeigt `[InternalTokenRequestedListener] received request for audience: openproject` und danach keine Zeile über eine Sitzung, bricht aber an `[TokenService] Failed to get token from Oidc provider app, oidc app is not installed`. Der Pfad verlangt, dass Nextcloud selbst der Anbieter ist (Server-App `oidc`), und die ist hier nicht installiert; sie zu installieren wäre der zweite Aufbau derselben Art, die `REQUIREMENTS.md` als Out of Scope führt | Server-App `oidc` installieren, darin einen Client `openproject` anlegen, `sso_provider_type` und `targeted_audience_client_id` darauf zeigen lassen und OpenProject an diesen Anbieter binden. Der letzte Schritt ist der teure und der ausgeschlossene (DI-17-05) |
| Die Datenlieferung von Weg 0 im Modus `oidc` **mit** Sitzung, 2.1 und 5.6.5 | **ungemessen** | Die Gegenprobe belegt die Sitzungsfrage (`token is still valid, it expires in 300`) und endet danach an OpenProject mit `401 Unauthorized` auf `/api/v3/users/me`, weil diese OpenProject-Instanz nicht an dieselbe Keycloak gebunden ist | OpenProject an dieselbe Realm binden. Genau das ist in `REQUIREMENTS.md` Out of Scope (kein eigener Keycloak-Client für OpenProject als Dienstkonto) |
| Die Betriebsart, die openDesk fährt (`oauth2` oder `oidc`, und wenn `oidc`, welcher Pfad), 1.4 | **ungemessen**, aus Quellen nicht entscheidbar | Die Einrichtung macht der Job `opendesk-openproject-bootstrap`, dessen Logik in einem eigenen Image liegt; im Deployment-Projekt stehen nur seine Eingaben. Das legt den Zwei-Wege-OAuth2-Weg nahe, ist aber Indiz und nicht Beleg | Eine Auskunft von ZenDiS oder eine openDesk-Installation. Steht als **Frage 7** in Abschnitt 4 |
| Ist `app_api` im openDesk-Nextcloud-Image enthalten und eingeschaltet, 1.2 und 1.4 | **ungemessen**, aus Quellen nicht entscheidbar | Das Image wird aus einem anderen, hier nicht mitgelesenen Projekt gebaut; der Tarball-Griff über das Deployment-Projekt kann eine mitgelieferte Serverapp im Image grundsätzlich nicht sehen | Zugriff auf das Image oder eine Auskunft. Steht als **Frage 6** in Abschnitt 4 |
| Ob openDesk zusätzlich eine SSRF-Erlaubnisliste setzt, 5.4 | **ungemessen** | Auch hier ist die Quelle der Bootstrap-Job und nicht das Deployment-Projekt | Dieselbe Auskunft wie oben; hängt an Frage 7 |
| Wann openDesk auf Nextcloud 34 oder höher geht, 1.3 und 1.4 | **ungemessen**, Terminfrage | In keiner öffentlichen Quelle beantwortet; sie ist erst durch den Befund aus 1.2 entstanden | Auskunft von ZenDiS. Steht als **Frage 5** in Abschnitt 4 |
| Ob ein Betreiber eine Dritt-ExApp neben der Suite aufnähme und wer das entscheidet, 1.4 | **ungemessen** | Betriebs- und Verfahrensfrage, öffentlich nicht dokumentiert. Kein Quellcode und kein Helmfile kann sie beantworten | Das Gespräch selbst. Steht als **Frage 1** in Abschnitt 4 |
| Warum `app_api` an `stable34` keine Oberflächenvorlage für `kubernetes-install` mitbringt, 1.2 und 1.4 | **ungemessen in der Absicht** | Gemessen sind die Zahlen (acht Vorlagen, keine mit `kubernetes-install`, drei geänderte Zeilen gegenüber `stable33`); ob das Absicht oder Rückstand ist, sagt keine Quelle | Eine Auskunft aus dem AppAPI-Kanal. Nebenfrage zu **Frage 5** |
| Der zusätzliche Umleitungsschritt über Keycloak im Zustimmungsfluss von Weg 1 in openDesk, 2.2 | **ungemessen** | In openDesk gibt es wegen `OPENPROJECT_OMNIAUTH__DIRECT__LOGIN__PROVIDER: "keycloak"` kein lokales Anmeldeformular, und genau dieses Formular ist Schritt 2 des gemessenen Messwegs | Eine openDesk-Installation oder ein an Keycloak gebundenes OpenProject |
| Die Scope-Pflicht für ein OIDC-JWT (`scope`-Anspruch mit `api_v3`, Breaking Change in OpenProject 16.0.0), 2.2 | **ungemessen** | Im lokalen OAuth-Modus, in dem alle Weg-1-Messwerte entstanden sind, ist sie unsichtbar, weil OpenProject die Tokens selbst ausgibt | Ein OIDC-gebundenes OpenProject, also derselbe Aufbau wie zwei Zeilen darüber |
| Ob es eine obere Zeitgrenze für den alten `refresh_token` gibt und ob openDesk diese Doorkeeper-Einstellung mitbringt, 2.2 | **ungemessen** | Gemessen ist der Auslöser der Entwertung (der erste Gebrauch des neuen `access_token`), nicht eine Zeitgrenze; eine Zeitgrenze zu messen hieße, den Lauf über Stunden zu strecken | Ein Lauf über die Lebensdauer hinaus und die Doorkeeper-Konfiguration der openDesk-Instanz (DI-17-02) |
| Warum derselbe Doorkeeper-Fehler einmal auf Deutsch und einmal auf Englisch zurückkam, 2.2 | **ungemessen** | Identischer Aufruf ohne `Accept-Language`, zwei Sprachen. Der Bericht hält den Befund fest und erklärt ihn nicht | Ein gezielter Lauf über die Spracheinstellung des Kontos und den `Accept-Language`-Kopf. Ohne Folge für die vier Messwerte von D-04 |
| Der native MCP-Endpunkt von OpenProject 17.7.2 (`mount API::Mcp => "/mcp"`) | **ungemessen** | Belegt sind Route, Verwaltungsseite, Scope `mcp` und ein Seed-Schritt aus dem laufenden Container, dazu 500 auf einen unauthentifizierten Aufruf. Werkzeugliste, Authentifizierungsweg, Berechtigungsdurchgriff und ob openDesk ihn einschaltet sind **nicht** gemessen; eine Aussage darüber wäre eine Behauptung über fremden Code | Eine eigene Messreihe gegen diesen Endpunkt, die den Stufenschnitt dieser Phase überschritten hätte (DI-17-01) |
| Elf der 17 OCS-Routen von Weg 0, 2.1 | **nicht gemessen**, teils absichtlich nicht ausgelöst | Vier Routen sind schreibend oder destruktiv und werden nach der Regel dieses Berichts nicht ausgelöst, eine fünfte (`POST .../work-packages/form`) ist freiwillig ausgeschlossen; die übrigen (`notifications`, `avatar`, `statuses/{id}`, `types/{id}`, `projects`, `available-assignees`) hat OD-02 nicht gebraucht | Ein Messplan für OD-04, der je Route eine eigene Behauptung samt Gegenprobe formuliert |
| Warum das dokumentierte Seed-Passwort von OpenProject abwich, 5.3 | **nicht untersucht** | Gemessen ist der Zustand (`User.check_password?` falsch, `failed_login_count` 6, `force_password_change` true, Konto nicht gesperrt) und die Auflösung per `rails runner`. Die Ursache ist nicht untersucht und steht deshalb als offener Punkt und nicht als Vermutung | Ein zweiter erster Start derselben Bildmarke mit protokolliertem Seed-Lauf. Ohne Folge für die Messungen, weil keiner der beiden Wege am Passwort des Administrators hängt |
| Ob eine ExApp in einer Behördeninstallation einen zweiten Host erreicht, 2.1 | **ungemessen** | Die Egress-Kontrollmessung lief im lokalen Docker-Netz, in dem eine Antwort erwartbar ist, weil alle Container in einem Netz hängen. Netzrichtlinien, Egress-Filter und Proxy-Zwang sind hier nicht nachgebildet | Eine Messung in der Zielumgebung. Bis dahin ist die Zahl ein Wert über diese Topologie und über keine andere |

**Die zwei Zeilen, die zusammenhängen, und der Preis, den sie beziffern.** Weg A und `file-links`
hängen an derselben Ursache: `file-links` braucht eine registrierte Ablage, eine Ablage anzulegen ist
Weg A, und Weg A scheitert in dieser Topologie gemessen am Namenscheck von OpenProject. Das ist der
Preis der Entscheidung des Owners vom 28.08. für Variante B, und er steht hier beziffert statt
verschwiegen. Gemessen ist damit, dass die App im Modus `oauth2` gegen eine lokale Instanz arbeitet,
und **nicht**, dass der openDesk-Bootstrap-Weg durchläuft.

**Was von S5 auch bei gelungenen Läufen ungemessen bleibt, in drei Sätzen, damit es niemand aus den
sechs Läufen herausliest.** Erstens: der lokale Aufbau baut den Anmeldezwang über Keycloak nur nach,
mit einer eigenen Realm, einer eigenen Client-Kombination und einem `sso_provider_type`, den dieser
Bericht selbst gesetzt hat; ein Satz, der aus S5 auf openDesk schließt, überspringt Frage 7. Zweitens:
der Pfad `nextcloud_hub` ist angelaufen und nicht zu Ende gemessen, er stellt die Sitzungsfrage
nachweislich nicht und bricht an einer ganz anderen Stelle. Drittens: die Datenlieferung mit einer
Sitzung ist nicht gegengeprobt, weil die Gegenprobe an OpenProject endet, und dieser Bericht behauptet
deshalb nicht, dass ein OIDC-gebundenes Weg 0 mit Sitzung Daten liefert.

## 3. API-Form (Vorarbeit für OD-04, kein Requirement dieser Phase)

**Teilweise gemessen am 2026-08-28.** Dieser Abschnitt trifft **keine** Entscheidung. Er sammelt, was
die gemessene Fläche von Weg 0 an Feldern und Bytes liefert und was ein Werkzeug nach dem Entwurf von
OD-04 davon bräuchte. Der Werkzeugschnitt ist OD-04 und gehört in v2.0; diese Phase erzeugt keinen
Code (D-12), und die Reihenfolge ist ausdrücklich: erst die Messwerte, dann in 17-09 das Urteil über
den Weg, dann irgendwann der Schnitt.

### 3.1 Die Byte-Kosten einer Weg-0-Antwort (S6)

Gemessen an derselben Antwort wie S3, unter demselben Konto: `bob`, ein Treffer, Arbeitspaket 38.
Zeitlich liegt die Messung **vor** der Gegenprobe von S4, deshalb steht hier `bob` und nicht `alice`.

| Messwert | Wert |
|----------|------|
| Antwort wie ausgeliefert | **4746 Bytes** |
| Leerraum darin | **keiner**: 0 Zeilenumbrüche, 0 Tabulatoren, 0 doppelte Leerzeichen. Die Antwort ist also schon minifiziert, PHPs `json_encode` schreibt keinen Leerraum |
| Anteil reiner Maskierung | 182 maskierte Schrägstriche (`\/`); ohne diese Maskierung neu kodiert sind es **4564 Bytes** |
| das Arbeitspaket allein, ohne OCS-Umschlag | **4490 Bytes** |
| davon `_links` | **3895 Bytes** in **49** Relationen, also **87 Prozent** des Objekts |
| davon die eigentlichen Felder | **585 Bytes** in **24** Feldern |

**Die eine Zahl, die dieser Abschnitt festhält, ist nicht 4746, sondern 3895 von 4490.** Der Aufwand
einer Weg-0-Antwort liegt fast vollständig im HAL-Relationenblock und nicht in den Daten, die ein
Werkzeug zeigen würde.

**Der Feldsatz, vollständig.** 25 Schlüssel auf oberster Ebene, das sind die 24 Felder plus `_links`;
`_embedded` fehlt in dieser Antwort ganz.

```
_type, id, displayId, subject, description, lockVersion,
startDate, dueDate, derivedStartDate, derivedDueDate, duration, ignoreNonWorkingDays,
estimatedTime, derivedEstimatedTime, derivedRemainingTime, spentTime,
percentageDone, derivedPercentageDone, scheduleManually,
position, storyPoints, hasProjectAttributes, createdAt, updatedAt
```

Die 49 Relationen in `_links`, ebenfalls vollständig:

```
self, schema, update, updateImmediately, move, copy, pdf, generate_pdf, atom,
project, parent, ancestors, type, status, priority, author, assignee, responsible, version,
category, projectPhaseDefinition, sprint, backlogBucket, targetVersions,
attachments, addAttachment, fileLinks, addFileLink,
activities, addComment, previewMarkup, relations, addRelation, availableRelationCandidates,
addChild, changeParent, watchers, watch, addWatcher, removeWatcher, availableWatchers,
timeEntries, logTime, showCosts, customActions, meetings,
github_pull_requests, gitlab_merge_requests, gitlab_issues
```

Eine Relation zum Löschen ist in dieser Antwort **nicht** enthalten. Der Satz steht hier, weil die
Liste vollständig sein soll und eine Abwesenheit sonst wie eine Auslassung des Berichts aussieht.

**Der Feldsatz ist nicht konstant, und das ist der wichtigere Befund an dieser Stelle.** Die
Kontrollmessung unter `alice` gegen ein Arbeitspaket, das `opa` sehen darf (Suchwort
`Upload presentations`, ein Treffer, Seed-Projekt):

| Messwert | `bob`, Arbeitspaket 38 | `alice`, Seed-Arbeitspaket 12 |
|----------|------------------------|-------------------------------|
| Antwort wie ausgeliefert | 4746 Bytes | **2542 Bytes** |
| Relationen in `_links` | 49, 3895 Bytes | **27**, 1772 Bytes |
| Felder | 24, 585 Bytes | **22**, 588 Bytes |
| Felder nur hier | `position`, `storyPoints`, `spentTime` | `remainingTime` |
| Relationen nur hier | 23, darunter `update`, `updateImmediately`, `addComment`, `addWatcher`, `addFileLink`, `move`, `copy`, `logTime`, `sprint`, `backlogBucket` | 1: `projectPhase` |

Die **Felder** kosten in beiden Antworten praktisch dasselbe (585 gegen 588 Bytes), die
**Relationen** unterscheiden sich um fast das Doppelte. Beide Ursachen sind sichtbar: `bob` ist im
eigenen Projekt schreibberechtigt und bekommt deshalb `update`, `addComment`, `addWatcher` und die
übrigen 20 Schreibrelationen mitgeliefert, und in seinem Projekt sind Module aktiv, die `storyPoints`
und `sprint` erst erzeugen. **Eine Bytezahl je Arbeitspaket ist damit keine Budgetgröße, sondern eine
Zahl mit zwei Abhängigkeiten: Berechtigung des Nutzers und aktive Module des Projekts.** Wer daraus
ein Token-Budget rechnet, rechnet mit dem günstigsten Fall.

### 3.2 Die Bezugsgröße, ohne die die Zahl wertlos wäre

Eine Bytezahl allein sagt nichts. Gegengerechnet ist deshalb dieselbe Instanz über die API v3, mit dem
**Aufbauzugang** `Basic apikey:<OP_API_TOKEN>` des Kontos `admin`. Der Zugang ist hier ausdrücklich
als solcher gekennzeichnet: er ist **kein** Messweg über Berechtigungen und taucht in keinem
Messwert von S3 oder S4 auf. Er ist genau dann zulässig, wenn nur die Größe einer Antwort verglichen
wird, und genau das passiert hier.

| Aufruf gegen `http://op.localtest.me:8082` | Status | Bytes |
|--------------------------------------------|--------|-------|
| `GET /api/v3/work_packages/38`, roh | 200 | **8115** |
| dasselbe mit `?select=id,subject` | 200 | **8115**, also **unverändert** |
| `GET /api/v3/work_packages?filters=[id=38]`, roh | 200 | **15831** |
| dasselbe mit `select=total,elements/id,elements/subject` | 200 | **88** |
| dasselbe mit `select=total,elements/id,elements/subject,elements/project,elements/status,elements/type,elements/self` | 200 | **361** |
| dasselbe mit `select=...,elements/updatedAt` | **400** | 310, `urn:openproject-org:api:v3:errors:InvalidSignal` |

**Zwei gemessene Befunde in dieser Tabelle, die kein Zitat ersetzt.** Erstens: `select` wirkt an der
**Sammlung** und nicht an der Einzelressource. Am Endpunkt `/api/v3/work_packages/38` ändert der
Parameter die Antwort um kein einzelnes Byte, an `/api/v3/work_packages` schrumpft dieselbe Auskunft
von 15831 auf 88 Bytes. Zweitens: die zulässigen Auswahlen zählt der Server im Fehlertext selbst auf,
wortwörtlich `Unterstützte Auswahlen sind self, project, status, type, author, assignee, responsible,
_type, id, displayId, subject, startDate, dueDate, date, *`. `updatedAt` ist nicht darunter, und ein
Client, der es auswählen will, bekommt 400 und nicht eine stille Teilantwort.

**Die Werte aus der Recherche stehen hier als Kontext und nicht als eigener Messwert:** für
`community.openproject.org` sind ein Arbeitspaket roh **3691 Bytes** und mit `select` **216 Bytes**
notiert. Die Größenordnung passt zu den 88 und 361 Bytes oben; die absolute Zahl der rohen Antwort
liegt in dieser Instanz höher (8115), weil ein anderer Modulsatz und andere Felder mitkommen. Genau
deshalb ist der Vergleich nur als Größenordnung geführt.

**Und die Zeile, die für Weg 0 zählt:** die OCS-Fläche von `integration_openproject` hat **keinen**
`select`-Parameter. Die Methode nimmt gemessen `searchQuery`, `fileId` und `isSmartPicker`
(`lib/Controller/OpenProjectAPIController.php:134-138`) und sonst nichts. Wer über Weg 0 liest, kann
die 4746 Bytes also nicht am Server kleiner machen; wer über die API v3 liest, kann es.

### 3.3 Was die OCS-Fläche für OD-04 hergibt und was nicht

Die vollständige Routentabelle steht in 2.1, gezählt aus `appinfo/routes.php` der installierten
Fassung 3.1.1: 17 OCS-Routen. Für den Entwurf von OD-04 sind daraus drei Lücken und ein Fund
entscheidend, und alle vier sind an der installierten Fassung belegt und nicht aus einer Dokumentation
übernommen.

| Bedarf aus dem OD-04-Entwurf | Lage auf der OCS-Fläche |
|------------------------------|--------------------------|
| ein einzelnes Arbeitspaket per Id lesen | **keine Route.** Erreichbar nur als Suche mit einem Filter, und der Suchweg hängt an `isSmartPicker` beziehungsweise an einer registrierten Ablage (2.1) |
| Kommentare eines Arbeitspakets lesen | **keine Route.** `_links.activities` und `_links.addComment` stehen im Antwortkörper, die Fläche selbst bietet dafür nichts |
| "meine Arbeit", also die Arbeitspakete des angemeldeten Nutzers | **keine Route.** Es gibt `GET /api/v1/notifications`, und das ist etwas anderes |
| die Kette Arbeitspaket zu Datei | **`GET /api/v1/work-packages/{id}/file-links` existiert.** Das ist genau das Unterscheidungsmerkmal, das `research/FEATURES.md` nennt, und es ist die einzige Route, die eine Id eines Arbeitspakets annimmt |
| Suche nach Text | `GET /api/v1/work-packages?searchQuery=...`, gemessen in S3 |
| Zustand und Typ eines Arbeitspakets auflösen | `GET /api/v1/statuses/{id}` und `GET /api/v1/types/{id}`, nicht gemessen |
| Projekte auflisten | `GET /api/v1/projects`, nicht gemessen |

`GET /api/v1/work-packages/{id}/file-links` ist in diesem Plan **nicht** aufgerufen worden: die Route
setzt eine registrierte Ablage voraus, und die gibt es in dieser Instanz gemessen nicht (5.5.1). Der
Befund ist damit die Existenz der Route und ihre Signatur, nicht ihr Verhalten. Das steht hier als
`ungemessen` mit Grund und ist ein Kandidat für einen Folgeplan oder für OD-04.

**Keine Entscheidung, und zwar ausdrücklich.** Ob ein künftiges Werkzeug `openproject_browse` über
Weg 0 oder über Weg 1 liest, welche Felder es projiziert, ob es `wp:<id>` für `fetch` einführt und wie
es mit den drei Lücken umgeht, entscheidet OD-04 nach dem Urteil aus 2.4, und 2.4 gehört Plan 17-09.
Dieser Abschnitt liefert dafür Zahlen und Routen, keine Wahl.

**Der Satz, der am Ende dieses Abschnitts stehen soll, weil er die Richtung der Sparsamkeit festlegt.**
Die Diät macht hier der **Server** über `select`, gemessen 15831 gegen 88 Bytes an derselben Auskunft,
und nicht eine Projektion in unserem Code. Eine Projektion bei uns spart Ausgabe an das Sprachmodell,
aber keinen einzigen Byte auf der Leitung und keine Arbeit in OpenProject; ein `select` spart beides.
Für Weg 0 ist das zugleich der gemessene Nachteil: dort gibt es kein `select`, und eine Antwort trägt
zu 87 Prozent Relationen, die niemand angefragt hat.

## 4. Fragenliste für den ISV-Call am 14.09. (OD-03)

**Stand 2026-08-29, neun Fragen.** Die Reihenfolge ist festgelegt und nicht kosmetisch: vier Stellen
dieses Berichts zeigen auf Nummern. Abschnitt 1.4 verweist auf die Fragen 1, 5, 6 und 7, Abschnitt 1.3
auf Frage 5, Abschnitt 2.2 auf Frage 9 und Abschnitt 2.5 auf Frage 7. Wer hier umsortiert, macht diese
Verweise falsch.

Jede Frage trägt einen Absatz `Grund:`, und dieser Grund nennt die **Folge** einer Antwort und nicht
das Interesse an ihr. Eine Frage ohne Folge ist Neugier und kostet im Gespräch dieselbe Zeit wie eine
mit Folge. Die Fragen 1 bis 4 sind die Pflichtfragen aus OD-01, die Fragen 5 bis 9 sind erst in dieser
Phase entstanden.

**Was diese Phase beantwortet hat, steht nicht mehr auf der Liste.** Drei Fragen der Ausgangsrecherche
sind entfernt und werden nicht vorsichtshalber mitgeführt; sie stehen am Ende in der Tabelle
`Nicht mehr auf der Liste`, jede mit dem Beleg, der sie erledigt hat. Der Grund für das Streichen ist
nicht Ordnungsliebe: die Gesprächszeit am 14.09. ist die knappe Größe, und eine Frage, deren Antwort
schon gemessen im Bericht steht, lädt eine Auskunft ein, die wir nicht brauchen, und verdrängt eine,
die wir brauchen.

**Der Adressat ist nicht überall derselbe, und das steht bei jeder Frage dabei.** Der Termin am 14.09.
ist mit Nextcloud (Fabrice Mous, Strategic Markets and Initiatives) und nicht mit ZenDiS. Die Fragen 1
bis 5 sind dort trotzdem richtig aufgehoben, weil sie das Verhältnis des ISV-Programms zu openDesk
betreffen und weil Nextcloud den Weg zu ZenDiS kennt; die Mail an ZenDiS ist am 28.08. zusätzlich
hinausgegangen und läuft parallel. Die Fragen 8 und 9 sind Entwicklerfragen, und ihre eigentlichen
Kanäle sind `nextcloud/user_oidc` und OpenProject. Sie stehen hier, weil Frage 8 eine Lücke im
Baukasten des souveränen Arbeitsplatzes benennt und nicht eine in unserem Entwurf, und weil beide im
Gespräch belegen, dass hier gemessen und nicht gelesen wurde.

### Die vier Pflichtfragen aus OD-01

1. **Wie wird eine Drittanbieter-Komponente in openDesk aufgenommen: wer entscheidet darüber, nach
   welchen Kriterien, und in welchem zeitlichen Rahmen?**

   Grund: Das ist der eine Punkt aus 1.4, den kein Quellcode und kein Helmfile beantworten kann, weil
   er ein Verfahren und keine Datei ist. Die Folge einer Antwort ist ein Schnitt in der Roadmap und
   nicht eine Einzelheit: lautet sie "nur als Teil der Distribution", heißt die nächste Phase nicht
   "OpenProject-Werkzeuge", sondern "Aufnahmefähigkeit herstellen", und OD-04 rückt nach hinten.
   Lautet sie "eine Dritt-ExApp neben der Suite ist vorgesehen", ist die Reihenfolge umgekehrt. Ohne
   diese Antwort ist jede Reihenfolge geraten, und geraten wird sie zwei Phasen lang.

2. **Ist die Installation einer External App in openDesk vorgesehen, und wenn ja, auf welchem Weg?**

   Grund: Der Befund, der die Frage erzwingt, ist gemessen und in 1.1 und 1.2 belegt. Der App Store ist
   abgeschaltet (`appstore: enabled: false`, Zeile 79 bis 80 der Nextcloud-Werte an Tag `v1.18.0`), und
   im ganzen Deployment-Projekt an demselben Tag kommt AppAPI nicht vor: über 349 entpackte Dateien
   null Treffer für `app_api`, `appapi`, `external app` und `exapp`, bei einer Gegenprobe, die
   `integration_openproject` in drei Dateien findet und damit zeigt, dass die Suche nicht ins Leere
   greift. Was als Daemon-Typ bliebe, ist `manual-install` in seinen zwei Varianten. Die Folge trifft
   den Kern dieses Produkts: die Ein-Klick-Erzählung existiert in einer openDesk-Installation nicht,
   die Installation ist dort eine Betreiberhandlung im Helmfile. Auch ein "heute nicht vorgesehen" ist
   eine verwertbare Antwort, weil es den Aufwand sichtbar auf die Betreiberseite legt, statt ihn in
   einer Vermutung zu verstecken.

3. **Was bedeutet die AGPL-Lizenz des Kerns für eine Enterprise-Positionierung in openDesk: welche
   Teile dürfen bezahlt sein, und welche erwartet die Distribution frei?**

   Grund: Das ist eine Verhandlungs- und keine Recherchefrage, und sie ist die einzige der neun, die
   kein Messwert je beantworten kann. Der Anlass ist konkret: die Produktkarte im Dossier sieht ein
   Audit-Log mit SIEM-Ausleitung als bezahltes Add-on vor, und ein Audit-Log in einem
   AGPL-Repository kann kein exklusives kommerzielles Unterscheidungsmerkmal sein, weil jeder Betreiber
   es weitergeben darf. Dazu der Befund aus 1.1, der die Frage praktisch macht: openDesk trägt in
   derselben Datei bereits einen Schalter für Protokollierung (`adminAudit`, Zeile 77 bis 78). Die
   Folge einer Antwort ist der Zuschnitt des Bezahlten: liegt es im Protokoll selbst, oder liegt es in
   Governance, Ausleitung und Richtlinien und das Protokoll läuft frei mit. Das ändert die Produktkarte
   und nicht ein Feature.

4. **Talk und Kontakte sind in openDesk abgeschaltet. Was heißt das für die Beschreibung dieser App und
   für einen openDesk-Zuschnitt: eigene Fassung, Fähigkeitsprüfung zur Laufzeit, oder diese Familien
   dort gar nicht bewerben?**

   Grund: Der Zustand ist aus der Quelle belegt und nicht vermutet, alles in derselben Datei an Tag
   `v1.18.0`: `contacts: enabled: false` (Zeile 61 bis 62), `spreed: enabled: false` (Zeile 75 bis 76),
   dazu `comments` (81 bis 82) und `circles` (83 bis 84). Zwei der neun Werkzeugfamilien dieser App
   liegen dort dunkel, und dieser Befund trifft unabhängig vom Ausgang des ganzen OpenProject-Teils zu.
   Die Folge ist eine Wahl zwischen drei Wegen, die unterschiedlich teuer sind: eine eigene
   openDesk-Fassung der App (teuer, zweiter Wartungsstrang), eine Fähigkeitsprüfung zur Laufzeit
   (billig, die Technik dafür liegt in `capabilities.py` bereits vor), oder die Familien in einer
   openDesk-Beschreibung nicht bewerben (billig, kostet Erzählung). Nachfrage mit eigener Folge: ist die
   Abschaltung eine Vorgabe der Distribution oder eine Voreinstellung, die ein Betreiber ändern darf?
   Ist sie änderbar, ist die Fähigkeitsprüfung nicht nur die billigste, sondern auch die einzig
   richtige Antwort, weil dieselbe App dann beide Fälle bedienen muss.

### Die fünf Fragen, die diese Phase neu erzeugt hat

5. **Wann geht openDesk auf Nextcloud 34 oder höher?**

   Grund: Das ist die stärkste Frage dieser Phase, weil sie aus einer Absage eine Terminfrage macht.
   Der Aufhänger ist in 1.2 belegt: `app_api` an `stable34` zählt in der Hilfe des
   Registrierungskommandos den Wert `kubernetes-install` auf, `stable33` zählt ihn nicht auf, und die
   Datei, die ihn umsetzt, antwortet an `stable34` mit HTTP 200 und 803 Zeilen und an `stable33` mit
   HTTP 404. Die Phasenrecherche hat an demselben Zweig zusätzlich vier Freigabearten für den Dienst und
   vier eigene CI-Abläufe (`tests-deploy-k8s*.yml`) gelesen, die es an `stable33` nicht gibt. openDesk
   1.18.0 pinnt Nextcloud auf 33.0.7, und die Messumgebung dieser Phase bestätigt aus der laufenden
   Instanz, dass dort `app_api` 33.0.0 liegt (S0, 1.3). Die Folge: Versionspin und Kubernetes-Hürde sind
   dieselbe Hürde, und beide fallen mit demselben Schritt. Ein Datum verwandelt damit die zweite Hürde
   von OD-01 in eine Wartezeit. Nebenfrage aus demselben Abschnitt: `stable34` bringt für
   `kubernetes-install` keine Vorlage in der Admin-Oberfläche mit, der Weg ist nur über
   `occ app_api:daemon:register --k8s` erreichbar. Ist das Absicht oder Rückstand? Die Antwort sagt,
   ob der Weg betriebsreif gemeint ist oder erst angelegt.

6. **Enthält das openDesk-Nextcloud-Image `app_api`, und ist die App dort eingeschaltet?**

   Grund: Das ist die eine echte Rest-Unbekannte von OD-01 (1.4), und sie ist aus Quellen nicht
   entscheidbar: das Image wird aus einem anderen, hier nicht mitgelesenen Projekt gebaut, und der
   Tarball-Griff über das Deployment-Projekt kann eine mitgelieferte Serverapp im Image grundsätzlich
   nicht sehen. `app_api` ist seit Nextcloud 30 mitgeliefert, und in der Messumgebung dieser Phase
   liegt sie auf 33.0.7 als `app_api 33.0.0` vor und trägt die gemessene Kette aus Registrierung,
   Deploy-Daemon und Nutzerimpersonation (S0). Die Folge trennt zwei ganz verschiedene Aufgaben: ist die
   App im Image und eingeschaltet, ist der Rest eine Daemon-Frage und hängt an Frage 5. Fehlt sie oder
   ist sie aus, ist eine Installation eine Änderung am Image, also eine ZenDiS-Entscheidung und keine
   Betreiberhandlung, und dann hängt alles an Frage 1.

   Nachfrage, dieselbe Frage für die Nachbarkomponente: **ist der MCP-Endpunkt, den OpenProject selbst
   mitbringt, in openDesk eingeschaltet?** Belegt ist seine Existenz an der Fassung, die auch openDesk
   fährt: `mount API::Mcp => "/mcp"` in `/app/config/routes.rb:48` des laufenden Containers 17.7.2,
   dazu eine Verwaltungsseite (`:676`), ein eigener OAuth-Bereich `mcp` im Doorkeeper-Initializer
   (`:136`) und ein Seed-Schritt beim ersten Start; ein unauthentifizierter Aufruf antwortet 500, also
   eine antwortende Route und keine 404. Über sein Verhalten, seinen Authentifizierungsweg und seine
   Berechtigungstreue ist in dieser Phase **nichts** gemessen, und der Bericht behauptet dazu nichts.
   Grund für die Nachfrage: ist der Endpunkt dort an, gibt es für Arbeitspakete einen dritten Weg, den
   die Weg-0-gegen-Weg-1-Tabelle dieses Berichts nicht führt, nämlich zwei MCP-Server nebeneinander im
   selben Assistenten. Diese Möglichkeit gehört vor den Entwurf von OD-04 und nicht danach.

7. **In welchem Modus läuft `integration_openproject` in openDesk, `oauth2` oder `oidc`?**

   Grund: An dieser Frage hängt von allen neun am meisten, und der Unterschied, der sie teuer macht,
   ist in dieser Phase gemessen und nicht mehr nur zitiert (2.1). Im Modus `oauth2` erneuert die App
   das Nutzertoken serverseitig: derselbe Aufruf nach abgelaufenem Token antwortet **200** mit einem
   Treffer, `token_expires_at` steht danach 7200 Sekunden in der Zukunft, das Tokenpaar ist
   ausgetauscht, und im Aufruf war kein Cookie, keine Browsersitzung und kein App-Passwort (S4, einmal
   mit gestelltem und einmal mit natürlich verstrichenem Ablauf). Im Modus `oidc` antwortet derselbe
   Aufruf desselben Kontos nach Ablauf **401** mit 77 Bytes, und `user_oidc` protokolliert wörtlich
   `[TokenService] getToken: no session data` (S5a bis S5c). Die schärfste Fassung des Befundes: Weg 0
   trägt im Modus `oidc` genau so lange, wie der zwischengespeicherte Token gilt, und fällt danach auf
   401. Die Folge: die Antwort entscheidet, ob OD-04 auf Weg 0 gebaut werden kann oder ob es dort einen
   zweiten Weg braucht. Aus Quellen ist sie nicht entscheidbar (1.4), weil die Einrichtung der Job
   `opendesk-openproject-bootstrap` macht und dessen Logik in einem eigenen Image liegt; das
   Deployment-Projekt zeigt nur seine Eingaben, und die legen den Zwei-Wege-OAuth2-Weg nahe, ohne ihn
   zu belegen.

   Drei Nachfragen, jede mit eigener Folge, alle nur nötig, wenn die Antwort `oidc` heißt oder den
   Bootstrap-Job berührt:

   - **Falls `oidc`: mit welchem `sso_provider_type`?** Von den drei Ereignispfaden stellt genau einer
     die Sitzungsfrage nicht (`nextcloud_hub`), und er ist in dieser Phase angelaufen, aber nicht zu
     Ende gemessen: er bricht an `oidc app is not installed`, weil er Nextcloud selbst als Anbieter
     verlangt. Folge: fährt openDesk diesen Pfad, ist eine eigene Messung lohnend; fährt es `external`,
     ist Weg 0 dort nach Tokenablauf gemessen tot.
   - **Liefert der Bootstrap-Job die Nextcloud-Ablage in OpenProject fertig eingerichtet aus?** Folge:
     `GET /api/v1/work-packages/{id}/file-links` ist die einzige Route der ganzen OCS-Fläche, die eine
     Id eines Arbeitspakets annimmt, und zugleich das Unterscheidungsmerkmal dieser App gegenüber einem
     allgemeinen OpenProject-Client (3.3). Ohne registrierte Ablage gibt sie nichts zurück; in dieser
     Messumgebung antwortet `GET /api/v3/storages` mit `total 0` (5.5.1), und deshalb ist die Route hier
     ungemessen geblieben. Ist sie in openDesk vorkonfiguriert, ist die für uns wertvollste Route dort
     die einzige, die sofort trägt.
   - **Setzt openDesk in OpenProject eine Erlaubnisliste für den SSRF-Schutz?** Folge: der dokumentierte
     Einrichtungsweg über den Ablagen-Assistenten ist in unserer Loopback-Topologie gemessen nicht
     gangbar, weil OpenProject jeden Namen abweist, unter dem Nextcloud hier erreichbar wäre (5.4). In
     einem Cluster tragen beide Seiten private Adressen, und die Frage ist deshalb dieselbe, nur mit
     anderem Vorzeichen.

8. **Gibt es einen vorgesehenen Weg, wie eine AppAPI-ExApp ohne PHP-Anteil ein audience-korrektes Token
   für eine Schwesterkomponente derselben Suite bekommt, ohne Browsersitzung?**

   Grund: Diese Frage ist der stärkste fachliche Beitrag, den diese Phase in ein Gespräch mitbringt,
   und sie steht auf drei Messwerten statt auf einer Vermutung. Erstens: die Vorbedingung ist erfüllt,
   `IUserSession::isLoggedIn()` liefert unter AppAPI-Impersonation `true`, denn in allen sechs Läufen
   von S5 erscheint die Zeile des jeweiligen Listeners, die hinter genau dieser Prüfung steht (S5c).
   Zweitens: der Bruch liegt eine Stufe später, der Sitzungsspeicher trägt unter Impersonation kein
   Anmeldetoken, und `user_oidc` schreibt das wörtlich als `getToken: no session data`. Drittens:
   `user_oidc` bietet den Austausch nur als PHP-Ereignis an, seine `appinfo/routes.php` hat keine
   einzige Route, die ein Token zurückgibt. Die Folge: das ist eine Lücke im Baukasten des souveränen
   Arbeitsplatzes und nicht eine in unserem Entwurf, und sie trifft jede ExApp, die für den
   angemeldeten Nutzer gegen eine zweite Komponente derselben Suite handeln will. Kanal: der Entwurf
   eines Kommentars an `nextcloud/user_oidc#925` liegt unversendet in `docs/contrib/`, gesendet wird er
   ausschließlich vom Owner.

9. **Warum bewerben die AS-Metadaten von OpenProject `code_challenge_methods_supported` nicht, obwohl
   `force_pkce` unbedingt im Doorkeeper-Initializer steht?**

   Grund: Der Schaden ist gemessen und nicht befürchtet (2.2). Das Dokument
   `/.well-known/oauth-authorization-server` der laufenden Instanz 17.7.2 nennt weder
   `code_challenge_methods_supported` noch einen `registration_endpoint`; dieselbe Instanz weist einen
   Aufruf ohne `code_challenge` an `/oauth/authorize` mit **400** und dem Text
   `Code challenge is required.` ab, und derselbe Aufruf mit `code_challenge` antwortet in derselben
   Sitzung 200 und liefert einen Code. Ein Client, der sich allein nach dem Dokument richtet, lässt
   PKCE also weg, bekommt eine 400 ohne maschinenlesbaren Hinweis und muss den Text einer HTML-Seite
   lesen, um den Grund zu erfahren. Die Lücke ist kein lokales Artefakt: die Dokumente der öffentlichen
   Community-Instanz tragen sie ebenso. Die Folge ist klein und billig: die Fähigkeit ist vorhanden,
   nur die Ansage fehlt, und das ist der dankbarere Beitrag als jede Beschwerde. **Vermerk:** diese
   Frage gehört eher in den OpenProject-Kanal als in den ISV-Call. Sie steht hier, damit sie nicht
   verloren geht, und sie ist im Gespräch die erste, die entfällt, wenn die Zeit knapp wird.

### Nicht mehr auf der Liste

Drei Fragen der Ausgangsrecherche sind entfernt. Sie werden nicht vorsichtshalber mitgeführt, weil eine
Frage, deren Antwort im selben Bericht steht, im Gespräch eine Antwort einlädt, die wir schon haben.

| Entfallene Frage | Woher sie kam | Warum sie entfällt |
|------------------|---------------|--------------------|
| "Ist AppAPI in openDesk aktiviert, und welcher Deploy-Daemon ist vorgesehen?" | `ARCHITECTURE.md` A.7 | Zur Hälfte beantwortet und zur anderen Hälfte präziser gefasst. Beantwortet: im Deployment-Projekt an Tag `v1.18.0` kommt AppAPI in keiner von 349 Dateien vor (1.2), und welcher Daemon auf dem gepinnten Stand überhaupt existieren kann, ist aus `RegisterDaemon.php` beider Zweige belegt. Was offen blieb, ist ausschließlich das Image, und genau das ist jetzt **Frage 6**. Die alte Fassung würde eine Auskunft einladen, die schon gemessen im Bericht steht |
| "Nimmt `/oauth/authorize` PKCE an, obwohl die Metadaten es nicht bewerben?" | `STACK.md` A.8 | Gemessen beantwortet, und zwar in beide Richtungen: mit `code_challenge` 200 und ein Code, ohne `code_challenge` 400 mit `Code challenge is required.` (2.2). Das ist keine Frage mehr, sondern ein Messwert. Der Rest der Sache, die fehlende Bekanntmachung in den Metadaten, ist **Frage 9** |
| "Veröffentlicht `integration_openproject` eine Capability, oder braucht es den Navigations-Umweg?" | `ARCHITECTURE.md` A.7 | Gemessen beantwortet: `GET /ocs/v2.php/cloud/capabilities` liefert **ohne jede Anmeldung** einen Abschnitt `integration_openproject` mit `app_version`, `groupfolder_version` und `groupfolders_enabled`, und `app_version` nennt genau die installierte Fassung 3.1.1 (2.1). Der Umweg über `/core/navigation/apps`, den Nextcloud Mail erzwingt, entfällt hier. Eine spätere Fähigkeitsprüfung bekommt die Antwort aus einem Aufruf, der ohnehin läuft |

Die drei nicht-technischen Fragen des Dossiers zum 14.09. (Verkaufsmechanik, Referenz-ISVs, Kanal des
Enterprise-Flags) sind von dieser Liste unberührt: sie kommen aus dem Validierungsplan und nicht aus
dieser Phase.

**Wo dieselbe Liste sonst noch steht (D-10).** Der Stand oben ist zusätzlich in das Dossier für den
Termin übernommen worden, `Desktop/ISV-Call-Dossier-2026-09-14.md`, Abschnitt "Technische Fragen aus
Phase 17". Das Dossier liegt außerhalb dieses Repositoriums und ist nicht versioniert; versioniert ist
dieser Abschnitt hier, und er ist bei einem Widerspruch der maßgebliche.

## 5. Rohmesswerte

**Geheimnisregel, gültig für jede Zeile dieses Abschnitts.** Diese Datei liegt in einem öffentlichen Repository. Protokolliert werden ausschließlich Statuscodes, Feldnamen, Zahlen, Längen und Präfixe. Niemals protokolliert wird ein `access_token`, ein `refresh_token`, ein Autorisierungscode, ein `client_secret` oder ein Wert des Headers `AUTHORIZATION-APP-API`: dieser Wert ist Base64 von `<user>:<APP_SECRET>` und damit genau so heikel wie das Geheimnis selbst. Tokenwerte werden auf ihre Länge und ihr Präfix reduziert. `expires_in` ist eine Zahl und darf stehen. Vor jedem Commit an dieser Datei läuft ein Griff nach den vier Zeichenketten, die dieses Projekt als Geheimnisverdacht führt: das JWT-Präfix, das Bearer-Schema mit einem Wert dahinter, und `refresh_token` sowie `client_secret` je mit einem Gleichheitszeichen. Die vier Muster stehen hier bewusst umschrieben und nicht wörtlich: sonst findet der Griff diese Zeile selbst, und ein Gate, das an seiner eigenen Regel scheitert, wird beim nächsten Lauf ignoriert statt gelesen.

Alle Unterabschnitte sind gefüllt. Die Reihenfolge von 5.1 bis 5.6 ist die des Aufbaus und die der
Pläne; wer die Rohwerte in der Reihenfolge der **Behauptungen** braucht, findet sie in 5.0.

### 5.0 Die Rohwerte in der Reihenfolge der Behauptungen

Diese Tabelle steht vor den nach Plänen geordneten Unterabschnitten und führt jede Messung genau
einmal: der Aufruf ohne Kopfzeilenwerte, der Statuscode, der Content-Type, die Antwortform, höchstens
120 Zeichen Körper und das Konto, unter dem der Aufruf lief. Die Reihenfolge ist S0 bis S6, danach
Weg 1, danach die SSRF-Grenze. Wo eine Zeile mehrere gleichartige Läufe hat, steht hier der tragende
und die Spalte Stelle nennt die vollständige Liste. Wo ein Wert nicht protokolliert wurde, steht das
so und nicht ein nachträglich erschlossener Wert.

Die Kopfzeilenwerte fehlen in jeder Zeile nach der Geheimnisregel oben: `AUTHORIZATION-APP-API`,
Cookies, `Authorization: Bearer` und jedes `client_secret` stehen nirgends, auch nicht gekürzt.

| # | Behauptung | Aufruf (ohne Kopfzeilenwerte) | Konto | Status | Content-Type | Antwortform | Körper, höchstens 120 Zeichen | Stelle |
|---|-----------|-------------------------------|-------|--------|--------------|-------------|-------------------------------|--------|
| 1 | **S0** | `GET /ocs/v2.php/cloud/user?format=json` durch Caddy, reine AppAPI-Impersonation | `alice` | **200** | nicht protokolliert | OCS-Umschlag als JSON | `ocs.meta.statuscode 200`, `ocs.data.id alice`, `ocs.data.display-name alice` | 1.3 |
| 2 | **S0**, Gegenprobe | derselbe Aufruf, `APP_SECRET` aus 64 Nullen | `alice` | **401** | nicht protokolliert | OCS-Umschlag als JSON | `{"ocs":{"meta":{"status":"failure","statuscode":997,"message":"Current user is not logged in"}...` | 1.3 |
| 3 | **S0**, Route der ExApp | `POST /exapps/mcp_connector/mcp` ohne Token | keines, unauthentifiziert | **401** | nicht protokolliert | `WWW-Authenticate` im Bearer-Schema | `error="invalid_token"`, `scope="nextcloud"`, `resource_metadata=".../.well-known/oauth-protected-resource/mcp"`; **nicht gegengeprobt** | 1.3 |
| 4 | **S0**, Werkzeugweg | `uv run pytest tests/integration/test_http_tool_call.py -m integration -q` gegen diese Topologie | `alice` | 3 Tests grün | entfällt, kein HTTP-Messwert | Testlauf | `notes_create` legt an, `notes_read` liest zurück; falsches App-Passwort abgewiesen | 1.3 |
| 5 | **S1** | `GET /ocs/v2.php/apps/integration_openproject/api/v1/url` | `alice` | **200** | `application/json; charset=utf-8`, 103 Bytes | OCS-Umschlag als JSON | `{"ocs":{"meta":{"status":"ok","statuscode":200,"message":"OK"},"data":"http://op.localtest.me:8082"}}` | 2.1 |
| 6 | **S1**, Gegenprobe | derselbe Aufruf, `APP_SECRET` aus 64 Nullen | `alice` | **401** | `application/json`, 106 Bytes | OCS-Umschlag als JSON | `{"ocs":{"meta":{"status":"failure","statuscode":997,"message":"Current user is not logged in"},"data":[]}}` | 2.1 |
| 7 | **S2** | `GET /ocs/v2.php/apps/integration_openproject/api/v1/configuration` | `carol`, nie verbunden | **401** | `application/json`, 77 Bytes | OCS-Umschlag als JSON, leere Meldung | `{"ocs":{"meta":{"status":"failure","statuscode":401,"message":""},"data":""}}` | 2.1 |
| 8 | **S2**, Gegenprobe 1 | derselbe Aufruf | `alice`, verbunden mit `opa` | **200** | `application/json`, 1702 Bytes | OCS-Umschlag als JSON | `ocs.data._type Configuration`, `hostName op.localtest.me:8082`, `maximumAttachmentFileSize 5242880` | 2.1 |
| 9 | **S2**, Gegenprobe 2 | derselbe Aufruf | `bob`, verbunden mit `opb` | **200** | `application/json`, 1700 Bytes | OCS-Umschlag als JSON | dieselben Felder wie Zeile 8, zweites Konto unabhängig | 2.1 |
| 10 | **S2**, Pfadkontrolle | `GET /index.php/apps/integration_openproject/api/v1/configuration`, also ohne OCS-Präfix | `alice` | **404** | nicht protokolliert | leerer Körper | (leer) | 2.1 |
| 11 | **S3** | `GET .../api/v1/work-packages?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | `alice`, kein Mitglied | **200** | `application/json; charset=utf-8`, 74 Bytes | OCS-Umschlag als JSON, leere Liste | `{"ocs":{"meta":{"status":"ok","statuscode":200,"message":"OK"},"data":[]}}` | 5.5.1, Zeile 3 |
| 12 | **S3**, Gegenprobe 1 | derselbe Aufruf | `bob`, Mitglied | **200** | `application/json; charset=utf-8`, 4746 Bytes | OCS-Umschlag als JSON, ein Objekt | `id 38`, `displayId "38"`, `subject "SPIKE-OD-8471 privat"`, `_type WorkPackage` | 5.5.1, Zeile 4 |
| 13 | **S3**, Gegenprobe 2 | derselbe Aufruf mit `searchQuery=Demo` | `alice` | **200** | `application/json; charset=utf-8`, 35239 Bytes | OCS-Umschlag als JSON, 14 Objekte | 14 Treffer, `id 38` **nicht** darunter | 5.5.1, Zeile 5 |
| 14 | **S3**, Gegenprobe 3 | derselbe Aufruf | `carol` | **401** | `application/json; charset=utf-8`, 77 Bytes | OCS-Umschlag als JSON, leere Meldung | `statuscode 401`, Meldung leer | 5.5.1, Zeile 8 |
| 15 | **S4**, künstlicher Ablauf | derselbe Aufruf nach `token_expires_at 0`, ohne Cookie, ohne App-Passwort | `bob` | **200** | `application/json; charset=utf-8`, 4746 Bytes | OCS-Umschlag als JSON, ein Objekt | ein Treffer `id 38`; `token_expires_at` danach `1787950505`, also 7200 s weiter | 5.5.2, Zeile 5 |
| 16 | **S4**, Gegenprobe | derselbe Aufruf mit `refresh_token` aus 43 Nullen | `bob` | **401** | `application/json; charset=utf-8`, 77 Bytes | OCS-Umschlag als JSON, leere Meldung | `statuscode 401`, Meldung leer; im Protokoll `invalid_grant` | 5.5.2, Zeile 10 |
| 17 | **S4**, natürlicher Ablauf | `GET .../api/v1/work-packages?searchQuery=Upload%20presentations&isSmartPicker=true`, kein `occ`-Eingriff | `alice` | **200** | `application/json; charset=utf-8`, 2542 Bytes | OCS-Umschlag als JSON, ein Objekt | Ablauf 19623 s alt, ein Treffer `id 12`; `token_expires_at` danach 7176 s weiter | 5.5.4 |
| 18 | **S5a**, **S5b**, **S5c** | derselbe Aufruf im Modus `oidc` nach `token_expires_at 0`, sechs Läufe über drei Pfade | `3855a8f7...` (Läufe 1 bis 5), `alice` (Lauf 6) | **401** in allen sechs | `application/json; charset=utf-8`, 77 Bytes | OCS-Umschlag als JSON, leere Meldung | `{"ocs":{"meta":{"status":"failure","statuscode":401,"message":""},"data":""}}`, in allen sechs identisch | 5.6.4 |
| 19 | **S5**, Gegenprobe mit Sitzung | derselbe Aufruf **mit** dem Sitzungscookie aus der Keycloak-Anmeldung | `3855a8f7...` | **401** | `application/json; charset=utf-8`, 341 Bytes | OCS-Umschlag als JSON mit Fehlerobjekt | `ocs.data.error` trägt `"errorIdentifier":"urn:openproject-org:api:v3:errors:Unauthenticated"` | 5.6.5 |
| 20 | **S5**, gültiger Zwischenspeicher | derselbe Aufruf ohne Cookie, `token_expires_at` 259 s in der Zukunft | `3855a8f7...` | **401** | `application/json; charset=utf-8`, 341 Bytes | wie Zeile 19 | **keine** Zeile der App `user_oidc` im Zeitfenster; die 401 kommt von OpenProject | 5.6.5 |
| 21 | **S6** | dieselbe Antwort wie Zeile 12, kein zweiter Aufruf gefahren | `bob` | **200** | `application/json; charset=utf-8`, 4746 Bytes | OCS-Umschlag als JSON | 4490 Bytes im Objekt, davon 3895 in 49 Relationen und 585 in 24 Feldern | 5.5.3 |
| 22 | **S6**, Gegenprobe | dieselbe Antwort wie Zeile 17 | `alice` | **200** | `application/json; charset=utf-8`, 2542 Bytes | OCS-Umschlag als JSON | 27 Relationen (1772 Bytes), 22 Felder (588 Bytes) | 5.5.3 |
| 23 | **S6**, Bezugsgröße | `GET /api/v3/work_packages?filters=[{"id":{"operator":"=","values":["38"]}}]`, Aufbauzugang | `admin`, Aufbau und kein Berechtigungsmesswert | **200** | nicht protokolliert, 15831 Bytes | HAL-Sammlung | dieselbe Auskunft mit `select=total,elements/id,elements/subject`: **200**, 88 Bytes | 5.5.3 |
| 24 | **Weg 1**, Zustimmung | `GET /oauth/authorize` mit `code_challenge_method=S256`, danach `POST /oauth/authorize` | `opb` | **200**, dann **302** | `text/html` (Zustimmungsseite) | HTML-Seite, dann `Location` | `Authorize nc-mcp-spike-weg1 to use your account opb?`; `Location` trägt `code` (43 Zeichen) und das gesendete `state` | 2.2 |
| 25 | **Weg 1**, Einlösen | `POST /oauth/token`, `grant_type=authorization_code`, ohne `client_secret` | `opb` | **200** | nicht protokolliert, als JSON gelesen | Tokenantwort als JSON | `token_type Bearer`, `scope api_v3`, `expires_in 7200`, `created_at 1787938654`, Tokens je 43 Zeichen | 2.2 |
| 26 | **Weg 1**, PKCE-Gegenprobe | derselbe `GET /oauth/authorize` **ohne** `code_challenge`, dieselbe Sitzung | `opb` | **400** | HTML, gerenderte Fehlerseite | HTML-Seite, kein JSON, kein `Location` | `An authorization error has occurred. Code challenge is required.` | 2.2 |
| 27 | **Weg 1**, Erneuerung | `POST /oauth/token`, `grant_type=refresh_token`, ohne jeden Cookie-Speicher | `opb` | **200** | nicht protokolliert, als JSON gelesen | Tokenantwort als JSON | `token_type Bearer`, `expires_in 7200`, `scope api_v3`, beide Tokens neu (Präfixe `IwAN`, `E7kb`) | 2.2 |
| 28 | **Weg 1**, Gegenprobe 1 | derselbe Aufruf mit einem `refresh_token` aus 43 Nullen | `opb` | **400** | nicht protokolliert, als JSON gelesen | Fehlerantwort als JSON | `error invalid_grant`, `error_description` ist der Doorkeeper-Sammeltext | 2.2 |
| 29 | **Weg 1**, Gegenprobe 2 | derselbe Aufruf mit dem entwerteten `refresh_token` der Kette A, dreimal | `opb` | **400**, dreimal | nicht protokolliert, als JSON gelesen | Fehlerantwort als JSON | `error invalid_grant`; Kette B mit ungenutztem `access_token` liefert dagegen **200** | 2.2 |
| 30 | **Weg 1**, Verpackung | derselbe Endpunkt mit `Content-Type: application/json` und JSON-Körper | `opb` | **415** | nicht protokolliert | leeres JSON-Objekt | `{}` (kein PKCE-Befund, sondern `enforce_content_type`); **nicht gegengeprobt** | 2.2 |
| 31 | **Weg 1**, Identität | `GET /api/v3/users/me` mit dem Token, ohne Cookie | `opb` | **200** | nicht protokolliert, HAL als JSON | Nutzerobjekt | `login opb`, `id 6`, `admin` nicht gesetzt, `status active` | 2.2 |
| 32 | **Weg 1**, D-05 Hauptlauf | `GET /api/v3/work_packages/38` | `opb`, Mitglied | **200** | nicht protokolliert, HAL als JSON | Arbeitspaket | `subject SPIKE-OD-8471 privat`, `project Spike Privat B` | 2.2 |
| 33 | **Weg 1**, D-05 Negativ | derselbe Aufruf | `opa`, kein Mitglied | **404** | nicht protokolliert, 166 Bytes | Fehlerobjekt der API v3 | `urn:openproject-org:api:v3:errors:NotFound`, `The work package you are looking for cannot be found...` | 2.2 |
| 34 | **Weg 1**, D-05 Kontrolle | `GET /api/v3/work_packages/999999999` | `opa` | **404** | nicht protokolliert, 166 Bytes | Fehlerobjekt der API v3 | Byte für Byte dieselbe Antwort wie Zeile 33, gleicher SHA-256 `96f26f0149c7be10...` | 2.2 |
| 35 | **Weg 1**, D-05 Liste | `GET /api/v3/work_packages?pageSize=100` | `opb`, dann `opa` | **200** / **200** | nicht protokolliert, HAL als JSON | Sammlung | `opb`: `total 34`, enthält 38; `opa`: `total 33`, enthält 38 nicht | 2.2 |
| 36 | **Weg 1**, Metadaten | `GET /.well-known/oauth-authorization-server` vom Host | keines, unauthentifiziert | **200** | nicht protokolliert, als JSON gelesen | Metadatendokument | weder `registration_endpoint` noch `code_challenge_methods_supported`; `scopes_supported` nennt `api_v3` | 2.2 |
| 37 | **Weg 1**, Aufräumen | `POST /oauth/revoke`, zwanzig Werte | `opa` und `opb` | **200**, zwanzigmal | nicht protokolliert | leere Antwort | Gegenprobe: `GET /api/v3/users/me` danach je **401** | 2.2 |
| 38 | **SSRF** | `cimd.resolve_addresses('nextcloud', 80)` im laufenden ExApp-Container | entfällt, prozessinterner Aufruf ohne HTTP | Rückgabe `None` | entfällt | Rückgabewert plus Logzeile | `a document target was refused: an address of it is not public`; gleich für `caddy` und `appapi-harp` | 2.3 |
| 39 | **SSRF**, Unterscheidung | `cimd.resolve_addresses('openproject', 80)`, Profil `op` nicht gestartet | entfällt | Rückgabe `None` | entfällt | Rückgabewert plus Logzeile | `a document target did not resolve: gaierror`, also derselbe Rückgabewert aus anderer Ursache | 2.3 |
| 40 | **SSRF**, Gegenprobe | `cimd.resolve_addresses('one.one.one.one', 443)` und `example.com` im selben Lauf | entfällt | Adressliste | entfällt | Liste von IPv4 und IPv6 | `['1.0.0.1', '1.1.1.1', '2606:4700:4700::1111', ...]`, der Resolver im Container ist also heil | 2.3 |
| 41 | **SSRF**, Katalog | Negativkatalog aus `tests/unit/test_oauth_cimd.py:179-202`, im selben Container gefahren | entfällt | 12 von 12 abgelehnt, 3 von 3 zugelassen | entfällt | Zählung | keine unerwartete Abweichung; die Lücken `100.64.0.1`, `64:ff9b::7f00:1`, `224.0.0.1` sind darin | 2.3 |
| 42 | **Egress** | `GET http://openproject/api/v3` aus dem ExApp-Container, mit `Host: op.localtest.me:8082` | entfällt, unauthentifiziert | **401** | `application/hal+json`, 153 Bytes | Fehlerobjekt der API v3 | `urn:openproject-org:api:v3:errors:Unauthenticated`; ohne den `Host`-Kopf **400** `Invalid host_name configuration` | 2.1 |

**Zwei Zeilen dieser Tabelle sind ausdrücklich kein Messwert über Berechtigungen.** Zeile 23 läuft
unter dem Aufbauzugang des Kontos `admin`, und ein Administrator sieht in OpenProject jedes Projekt;
Zeile 4 ist ein Testlauf und kein HTTP-Messwert. Beide stehen hier, weil sie sonst in 5.5.3 und 1.3
allein stünden und ein Leser sie für Messwerte der Kette hielte.

**Die Vollständigkeitsprüfung gegen die Nachweisform dieses Berichts, mit ihrem Ergebnis.** Jede Zeile
oben nennt ein Konto, und wo die Spalte `entfällt` trägt, ist das kein fehlender Wert, sondern die
Eigenschaft der Messung: die Zeilen 38 bis 41 sind prozessinterne Aufrufe im ExApp-Container ohne
HTTP und ohne Identität, Zeile 42 läuft unauthentifiziert und misst Erreichbarkeit und nicht
Berechtigung, und die Zeilen 3 und 36 fragen ein Dokument beziehungsweise eine Route ohne jedes
Zugangsdatum ab. Zwei Behauptungen dieses Berichts tragen **keine** Gegenprobe und deshalb den Vermerk
`nicht gegengeprobt`: die 401 der ExApp-Route in Zeile 3 (eine Gegenprobe wäre ein Aufruf mit gültigem
Token gewesen, den dieser Plan nicht gefahren hat) und die 415 an `/oauth/token` in Zeile 30 (sie ist
selbst schon die Kontrolle zur Verpackung). Zwei weitere Punkte sind nicht ohne Gegenprobe, sondern
ohne Messung, und stehen deshalb in 2.5 und nicht hier: der Sprachwechsel der Doorkeeper-Fehlermeldung
und die Antwortform des nativen MCP-Endpunkts von OpenProject. Die Fassungen im Kopfblock sind alle aus
der laufenden Instanz gelesen (`occ status`, `occ app:list`, `docker image inspect`, `kc.sh --version`,
`GET /api/v3`) und keine aus der Recherche übernommen.

### 5.1 Stufe B: der erste Start von OpenProject 17.7.2

Gemessen am 2026-08-28 in der Topologie `compose.spike-opendesk.yml`, Profil `op`.

**Behauptung, die geprüft wurde (aus der Recherche, nicht aus der Instanz):** der erste Start dauert 30 bis 90 Minuten, davon meist Warten, und OpenProject allein braucht mindestens 4 GB Hauptspeicher. Beide Zahlen sind in 17-RESEARCH.md als Erwartung geführt, die eine aus der Fehlerbildtabelle von Pitfall 1, die andere aus den Systemanforderungen von openproject.org.

**Messweg:** `docker compose -f compose.spike-opendesk.yml --profile op up -d openproject`, danach alle 20 Sekunden `curl` auf `http://op.localtest.me:8082/login` zusammen mit `docker inspect -f '{{.State.Status}}:{{.State.OOMKilled}}:{{.State.ExitCode}}'`, bis der erste Aufruf 200 antwortet oder der Container endet. Zeitmarken aus `docker logs -t`, Speicher aus `docker stats --no-stream`, freier Speicher der WSL2-VM aus `free -m` in einem Wegwerfcontainer.

| Messwert | Ergebnis |
|----------|----------|
| Container gestartet | 2026-08-28 16:42:37 UTC (`docker inspect -f '{{.State.StartedAt}}'`) |
| erste 200 auf `/login` | 16:44:14 UTC, also **95 Sekunden** nach der ersten Logzeile, nicht 30 bis 90 Minuten |
| Speicher des Containers nach dem Start | **1,964 GiB** von 7,603 GiB, 25,83 Prozent, nicht die erwarteten mindestens 4 GB |
| verfügbarer Speicher der WSL2-VM danach | 4036 MiB von 7785 MiB total |
| OOM-Killer | `OOMKilled: false`, `ExitCode: 0`, kein Neustart, kein zweiter Versuch |
| Platz | 925 GiB frei im Dateisystem der VM, die 20 GB der Systemanforderungen sind keine Grenze |
| Bildmarke | `openproject/openproject:17.7.2`, Digest `sha256:19a828d66e7c23322d1fbbaa974e7b712ef03c2badf1b10466ca45710e6bbbe5`, 882512785 Bytes, erstellt 2026-08-13 |

**Gegenprobe, ohne die die 95 Sekunden nichts wert wären:** eine 200 auf `/login` könnte auch von einem noch nicht fertig aufgesetzten Rails kommen, das die Seite schon ausliefert, während die Seed-Phase weiterläuft. Drei Belege dagegen, alle aus demselben Lauf:

* Die vier Aufrufe vor dem letzten antworteten 502, 502, 502 und 503. Die 200 ist also der Übergang und nicht der Anfangszustand.
* Die Seed-Phase steht namentlich und abgeschlossen im Log: die Reihe `*** Loading <modul> seed data` bis `*** Seeding data from environment variables`, und zwar **vor** der Zeile `=> Booting Puma`. Danach `Worker 0` und `Worker 1 ... booted`, beide um 16:44:13 UTC.
* Die eingebaute Datenbank der All-in-one-Bildmarke läuft im selben Container: `listening on IPv4 address "0.0.0.0", port 5432` um 16:43:38 UTC. Ein Rails mit halb gefüllter Datenbank hätte die Seed-Reihe nicht zu Ende geschrieben.

**Einordnung, damit die Zahl nicht überdehnt wird:** gemessen ist der erste Start dieser Bildmarke auf diesem Rechner, mit leeren Bänden und ohne Last. Die Zahl widerlegt die Systemanforderung von openproject.org nicht, denn die gilt für eine benutzte Instanz mit mehreren Nutzern; sie widerlegt nur die Annahme, dass dieser Aufbauschritt hier eine Stunde kostet und am Speicher dieser WSL2-VM scheitert. Das aus 17-02 mitgeführte Speicherrisiko ist damit für Stufe B **nicht eingetreten**: es war keine `.wslconfig` nötig, kein `wsl --shutdown`, und die Container der beiden fremden Projekte auf diesem Rechner liefen durch.

### 5.2 Die Namensfalle, in beide Richtungen gemessen

**Behauptung:** `op.localtest.me:8082` ist ein Name, der aus dem Browser des Entwicklers und aus dem Nextcloud-Container an dieselbe Instanz führt. Ohne das ist Weg 0 nicht einrichtbar, weil `integration_openproject` OpenProject aus dem Nextcloud-Container heraus unter genau der Adresse aufruft, die ein Mensch in `openproject_instance_url` eingetragen hat.

| Messweg | Messwert |
|---------|----------|
| `curl` vom Host auf `http://op.localtest.me:8082/login` | 200 |
| `curl` aus dem Nextcloud-Container auf denselben Namen | 200 |
| dieselbe Anfrage aus dem Container mit `%{remote_ip}` | `172.29.43.10`, die feste Adresse von Caddy in dieser Topologie |
| `curl` aus dem Container auf `http://127.0.0.1:8082/login` | scheitert, `curl: (7) Failed to connect`, Code `000` |
| veröffentlichte Ports des Dienstes `openproject` | keine, `docker port` antwortet leer |
| Bindung des Zugangs | `8082/tcp` auf `127.0.0.1:8082` am Caddy-Dienst, keine andere Adresse |

**Gegenprobe:** die zwei gleichlautenden 200 allein beweisen noch nicht, dass der `extra_hosts`-Eintrag die Arbeit tut; sie könnten auch von einer öffentlichen Auflösung von `localtest.me` kommen. Die vierte Zeile schließt das aus: `127.0.0.1:8082` bedeutet im Nextcloud-Container der Container selbst, und dort hört nichts. Die dritte Zeile nennt die Adresse, die tatsächlich benutzt wurde, und es ist die aus `extra_hosts`.

**Ein Fund, der für Plan 17-05 zählt.** `getent hosts op.localtest.me` antwortet im Nextcloud-Container mit `::1` und nicht mit `172.29.43.10`: `localtest.me` hat einen öffentlichen AAAA-Eintrag auf die IPv6-Loopbackadresse, und ein Aufruf, der IPv6 bevorzugt, landet damit im Container selbst statt bei Caddy. Der `extra_hosts`-Eintrag ist ein reiner IPv4-Eintrag, und `getent ahostsv4` liefert entsprechend `172.29.43.10`. Gemessen ist, dass der Aufrufer, auf den es ankommt, die IPv4-Adresse nimmt: derselbe Aufruf durch die PHP-Erweiterung `curl` desselben Containers, also durch den Weg, den `integration_openproject` geht, meldet `php_remote_ip=172.29.43.10` und Code 200. Sollte in 17-05 ein Aufruf von Nextcloud aus dennoch ins Leere laufen, ist dieser AAAA-Eintrag die erste Stelle, an der zu schauen ist, und nicht die Caddy-Regel.

### 5.3 Aufbau, nicht Messung

Die Überschrift dieses Unterabschnitts ist wörtlich zu nehmen: was hier steht, ist **Aufbau, nicht Messung**. Es steht hier, weil der Zwei-Konten-Negativbeweis beider Wege (D-05) Daten braucht, die die Seed-Daten von OpenProject nicht hergeben: die Seed-Instanz hat ein Projekt und wenige Arbeitspakete, und ein Negativbeweis auf einer Instanz ohne fremde, nicht zugängliche Daten ist leer und sieht trotzdem grün aus (Pitfall 3, Absatz "Die Datenlage"). Angelegt am 2026-08-28 über die API v3 von OpenProject mit `Basic apikey:<OP_API_TOKEN>` des Kontos `admin`.

| Was | Aufruf | Ergebnis |
|-----|--------|----------|
| Konto A | `POST /api/v3/users` | 201, `login opa`, Vorname Alice, `id 5`, `status active`, `admin false` |
| Konto B | `POST /api/v3/users` | 201, `login opb`, Vorname Bob, `id 6`, `status active`, `admin false` |
| privates Projekt | `POST /api/v3/projects` | 201, Name `Spike Privat B`, Identifier `spike-privat-b`, `id 3`, `public false` |
| Rolle | `GET /api/v3/roles` | `Member` ist Rollen-Id 3 |
| Mitgliedschaft, **nur** Konto B | `POST /api/v3/memberships` | 201, Prinzipal `Bob Spike`, Rolle `Member` |
| Arbeitspaket im privaten Projekt | `POST /api/v3/projects/3/work_packages` | 201, Betreff `SPIKE-OD-8471 privat`, Typ `Task`, **Id 38** |

Die Arbeitspaket-Id `38` ist eine vom Server vergebene Id und kein Geheimnis; sie steht als `OP_WP_ID` in der git-ignorierten Verbindungsdatei, damit die Folgepläne sie nicht erraten müssen. Das Suchwort `SPIKE-OD-8471` ist so gewählt, dass es an keiner anderen Stelle dieser Instanz vorkommt: ein Negativbeweis, dessen Suchwort auch in einem Seed-Datensatz steht, findet etwas und beweist das Gegenteil von dem, was er soll.

**Die Asymmetrie ist der ganze Punkt.** `GET /api/v3/memberships` gefiltert auf Projekt 3 antwortet mit `total: 1` und nennt genau `Bob Spike` mit der Rolle `Member`. Alice ist **nicht** Mitglied. Ohne diese Asymmetrie ist der Negativbeweis beider Wege leer.

**Gegenprobe des Aufbaus:** `GET /api/v3/work_packages/38` mit dem API-Schlüssel antwortet 200, und der Betreff enthält `SPIKE-OD-8471`. Damit ist belegt, dass das Arbeitspaket wirklich existiert und lesbar ist, das private Projekt also nicht bloß leer angelegt wurde. Zwei weitere Gegenproben gelten dem Schlüssel selbst, denn eine 200 könnte auch von einer offenen Instanz kommen: derselbe Aufruf mit einem Schlüssel aus 70 Nullen antwortet 401, und ohne jede Anmeldung antwortet er ebenfalls 401.

**Diese Zeilen sind ausdrücklich nicht der Negativbeweis.** Der Negativbeweis läuft in den Plänen 17-04 und 17-06 unter den Konten selbst, nicht unter dem Admin-Zugang. Der Admin-Zugang, mit dem dieser Grundzustand entstanden ist, ist **nicht Teil der gemessenen Kette**: er hat dieselbe Rolle, die in `docs/spike-dav.md` das Deck-Board hat, das eine Messung erst möglich macht und selbst nichts beweist. Ein Messwert, der unter `apikey:<OP_API_TOKEN>` des Kontos `admin` entsteht, sagt über die Berechtigungen von `opa` und `opb` nichts, weil ein Administrator in OpenProject alle Projekte sieht.

**Das Feld "Client Credentials User ID" der OAuth-Anwendung ist leer geblieben.** Der Satz steht hier, weil ein Prüfer genau danach fragt: ein Wert in diesem Feld hätte der Anwendung ein festes Konto hinterlegt, jede Antwort wäre die dieses einen Kontos gewesen, und der Satz "der Assistent sieht niemals mehr als der angemeldete Nutzer" wäre unwahr geworden, ohne dass eine einzige Messung rot geworden wäre (Pitfall 2). Ebenso ist das Häkchen "Confidential" ausgeblieben, weil `/app/config/initializers/doorkeeper.rb:90` dieser Fassung `force_pkce` setzt und der Kommentar dort PKCE ausdrücklich für nicht vertrauliche Clients verlangt; genau dieses Verhalten misst Plan 17-04. In dieser Phase wurde kein Dienstkonto angelegt und keine Umgebungsvariable gesetzt, die einen globalen Basic-Auth-Nutzer oder einen instanzweiten API-Schlüssel einführt.

Dieser Absatz ist zugleich die Stelle, an die der Griff aus Pitfall 2 gehört. Er sucht in den Dateien dieser Phase nach den drei Wegen, die den Berechtigungsdurchgriff unauffällig brechen, und er findet in diesem Bericht ausschließlich die Schreibweise `apikey:<OP_API_TOKEN>`, also den benannten Messweg des Aufbaus mit einem Platzhalter an der Stelle des Werts, und niemals einen Schlüssel selbst. Der Platzhalter steht so und nicht ausgeschrieben, damit der Griff beim nächsten Lauf gelesen und nicht übergangen wird: ein Treffer in diesem Absatz ist erwartet, jeder Treffer außerhalb ist ein Befund.

**Drei Abweichungen beim Aufbau, protokolliert statt geglättet:**

1. **Das Seed-Passwort `admin` wurde von der Instanz abgelehnt.** Der Owner konnte sich mit der dokumentierten Vorgabe `admin`/`admin` nicht anmelden: `User.check_password?` war falsch, `failed_login_count` stand auf 6, `force_password_change` auf true, das Konto war **nicht** gesperrt. Aufgelöst wurde es, indem das Passwort des Benutzers `admin` per `rails runner` auf den Wert in `OP_ADMIN_PASSWORD` gesetzt, `force_password_change` auf false und `failed_login_count` auf 0 gestellt wurde. **Warum das Seed-Passwort abwich, ist nicht untersucht** und steht hier als offener Punkt und nicht als Vermutung. Der erzwungene Passwortwechsel hat damit nicht stattgefunden; für die Messungen dieser Phase ist das ohne Folge, weil keiner der beiden Wege am Passwort des Administrators hängt.
2. **Nebenbefund aus derselben Stelle, belegbar:** die Passwortregeln dieser Fassung verlangen alle vier Zeichenklassen. Die Fehlermeldung lautet wörtlich `Password Must include characters of the following types: lowercase, uppercase, numeric, special`. Die beiden Wegwerfpasswörter der Konten `opa` und `opb` sind 20 Zeichen lang und enthalten alle vier Klassen; die Regel ist damit der Grund für ihre Form und keine Zierde.
3. **`OPENPROJECT_DEFAULT__LANGUAGE=en` regiert das Seed-Konto nicht.** Gemessen an `GET /api/v3/users`: `admin` trägt `language de`, die beiden in diesem Plan angelegten Konten tragen `language en`. Für die Messungen ist das ohne Folge, weil sie unter `opa` und `opb` laufen und die Feldnamen der API v3 ohnehin englisch sind. Wer in einem Folgeplan eine Beschriftung aus der Oberfläche abliest, muss aber wissen, unter welchem Konto er sie abliest.

### 5.4 Warum der dokumentierte Einrichtungsweg von Weg 0 in dieser Topologie nicht gangbar ist

**Behauptung:** Der Zwei-Wege-Weg über den Ablagen-Assistenten von OpenProject (Weg A der Recherche,
derselbe Weg, den der openDesk-Bootstrap-Job geht) lässt sich in diesem Loopback-Aufbau nicht gehen,
und zwar nicht wegen fehlender Erreichbarkeit, sondern wegen des SSRF-Schutzes von OpenProject.

Diese Messung ist vor dem ersten Klick entstanden, weil die Alternative gewesen wäre, dem Owner eine
Anweisung vorzulegen, die an der ersten Eingabe scheitert.

**Messweg 1, die Rückrichtung überhaupt.** Aus dem laufenden OpenProject-Container gegen die vier
Namen, unter denen Nextcloud in dieser Topologie zu erreichen wäre, je `curl -4` mit
`%{http_code}` und `%{remote_ip}`:

| Aufruf aus dem OpenProject-Container | Messwert |
|--------------------------------------|----------|
| `http://127.0.0.1:8091/status.php` | `code=000`, keine Adresse: im Container ist das der Container selbst, dort hört nichts |
| `http://caddy/status.php` | `code=200`, `remote_ip=172.29.43.10`, die feste Adresse von Caddy |
| `http://nextcloud/status.php` | `code=200`, `remote_ip=172.29.43.129`, Nextcloud direkt |
| `http://op.localtest.me:8082/login` | `code=000`: der `extra_hosts`-Eintrag steht nur im Nextcloud-Container, nicht hier |

Der Wert, den die Anweisung des Plans in das Feld Host schreiben wollte, ist `http://127.0.0.1:8091`,
und das ist genau die Zeile mit `code=000`. Das ist die Namensfalle aus 5.2, gemessen in der
**Gegenrichtung**: 5.2 hat sie für Nextcloud zu OpenProject aufgelöst, für OpenProject zu Nextcloud ist
sie offen.

**Messweg 2, der eigentliche Grund.** `NextcloudCompatibleHostValidator` der laufenden Fassung 17.7.2
prüft den Host in drei Schritten, und der erste ist kein Netzaufruf:

```ruby
# /app/modules/storages/app/validator/nextcloud_compatible_host_validator.rb:48-53
def host_allowed?(contract, attribute, value)
  host = URI.parse(value).host
  return false if host.blank?
  return true if OpenProject::SsrfProtection.safe_ip?(host)

  contract.errors.add(attribute, :ssrf_filtered)
```

```ruby
# /app/lib/open_project/ssrf_protection.rb:158-169
def allowed_ip_address?(ip_address)
  OpenProject::Configuration.ssrf_protection_ip_allowlist.any? { |addr| addr.include? ip_address }
end
...
def unsafe_ip_address?(ip_address)
  return false if allowed_ip_address?(ip_address)
```

Gemessen mit `rails runner` in derselben laufenden Instanz, also nicht aus dem Quelltext geschlossen,
sondern an ihm ausgeführt. `safe_ip?` gibt die Adresse zurück, wenn sie zulässig ist, und `nil`, wenn
nicht:

```
allowlist = []
safe_ip?("127.0.0.1")       = nil
safe_ip?("caddy")           = nil
safe_ip?("nextcloud")       = nil
safe_ip?("op.localtest.me") = nil
safe_ip?("localhost")       = nil
Resolv::DNS "caddy"         = ["172.29.43.10"]
```

**Alle fünf Namen sind unzulässig, und die Erlaubnisliste ist leer.** Der Grund steht in der
Beschreibung des Schlüssels `ssrf_protection_ip_allowlist` in
`/app/config/constants/settings/definition.rb:1221-1266`, die die vom Gem `ssrf_filter` gesperrten
Bereiche wörtlich aufzählt: `127.0.0.0/8` sperrt die Loopback-Adresse und `172.16.0.0/12` das Netz
`172.29.43.0/24` dieser Topologie. Die letzte Zeile der Messung zeigt, dass auch der Dienstname nicht
hilft: er löst nach `172.29.43.10` auf, und diese Adresse liegt in genau dem gesperrten Bereich.

**Gegenprobe, ohne die der Befund auf Erreichbarkeit geschoben werden könnte.** Die zwei Netzaufrufe,
die der Validator **nach** dem Namenscheck führen würde, sind einzeln gefahren, aus dem
OpenProject-Container gegen `http://caddy`, und **beide gelingen**:

| Validator-Aufruf | Erwartung des Validators | Messwert |
|------------------|--------------------------|----------|
| `GET /ocs/v2.php/cloud/capabilities` (Zeile 73), `Ocs-Apirequest: true` | 2xx, `ocs.data.version.major` mindestens 22 (Zeile 31) | **200**, `version.major = 33`, und der Abschnitt `integration_openproject` steht darin |
| `GET /index.php/apps/integration_openproject/check-config` (Zeile 101), `Authorization: Bearer TESTBEARERTOKEN` (Zeile 32) | 2xx, und der Kopf muss unverändert zurückkommen | **200**, Körper wörtlich `{"user_id":"","authorization_header":"Bearer TESTBEARERTOKEN"}` |

Damit ist gemessen, dass diese Instanz die zwei fachlichen Bedingungen erfüllt: sie ist ein Nextcloud
33, die App ist installiert, und die Weiterleitungsfalle aus dem Kommentar des Validators
(`op_application_not_installed` bei einer 3xx, weil Apache den `Authorization`-Kopf ohne
`mod_rewrite` verschluckt) greift hier **nicht**. Der einzige Grund, an dem der Assistent scheitert,
ist der Namenscheck davor.

**Was daran gemessen ist und was nicht.** Gemessen ist die Antwort von `safe_ip?` für fünf Namen, die
leere Erlaubnisliste, die vier Erreichbarkeitswerte und die zwei Validator-Antworten. **Nicht
beobachtet** ist die Fehlermeldung des Assistenten in der Oberfläche: dass aus `:ssrf_filtered` eine
Abweisung des Formulars wird, ist an den Zeilen 48 bis 53 der installierten Fassung gelesen und nicht
im Browser gesehen. Der Bericht behauptet deshalb nicht, wie die Meldung lautet, sondern nur, welchen
Wert die Prüfung liefert, die zu ihr führt.

**Der Schlüssel ist nicht in der Oberfläche setzbar.** `ssrf_protection_ip_allowlist` trägt in
derselben Datei `writable: false`, `default: ""` und `env_alias: "SSRF_PROTECTION_IP_ALLOWLIST"`. Ein
Administrator kann ihn also nicht in OpenProject eintragen; er kommt aus der Umgebung des Prozesses,
und das heißt in dieser Topologie: der Container muss mit einer zusätzlichen Umgebungsvariablen neu
erzeugt werden.

**Was das über openDesk sagt, und was nicht.** Über openDesk sagt es nichts Gemessenes. Die
naheliegende Erklärung, warum der Bootstrap-Job dort denselben Weg gehen kann, ist, dass Nextcloud in
einem Cluster unter einem öffentlichen Namen mit einer routbaren Adresse steht und der Schutz dort
nicht greift; ob openDesk zusätzlich eine Erlaubnisliste setzt, ist in dieser Phase **ungemessen** und
steht nicht im Deployment-Projekt, das für Abschnitt 1 gelesen wurde. Dieser Absatz ist eine
Einordnung und kein Befund, und er ist als solcher gekennzeichnet, weil ein Satz ohne diese
Kennzeichnung wie eine Aussage über eine Behördeninstallation liest (Pitfall 3).

**Folge für die Einrichtung.** Weg A ist damit nicht ohne einen Eingriff in die Messumgebung gangbar,
und Weg B, der Handweg über `occ config:app:set` plus den persönlichen Durchlauf je Konto, ist der Weg
ohne Eingriff. Welcher der beiden genommen wurde, steht in 2.1; die Entscheidung liegt beim Owner, weil
sie die Übertragbarkeit der Weg-0-Messung auf openDesk verändert und nicht nur den Aufwand.

### 5.5 Rohwerte von S3, S4 und S6 auf Weg 0

#### 5.5.1 Die Suchmessung (S3)

Gemessen am 2026-08-28, alle Aufrufe durch Caddy gegen `http://127.0.0.1:8091`, alle unter reiner
AppAPI-Impersonation und ohne App-Passwort im Prozess. Der Pfad ist in jeder Zeile
`/ocs/v2.php/apps/integration_openproject/api/v1/work-packages`, die Werte in der Spalte Aufruf sind
die Abfrageparameter. Gekürzt wird nach der Geheimnisregel oben: der Wert des Kopfes
`AUTHORIZATION-APP-API` steht in keiner Zeile.

| # | Konto | Aufruf | Status | Content-Type | Bytes | `ocs.data` |
|---|-------|--------|--------|--------------|-------|------------|
| 1 | `alice` | `?searchQuery=SPIKE-OD-8471` | 200 | `application/json; charset=utf-8` | 74 | `[]`, 0 Treffer |
| 2 | `bob` | `?searchQuery=SPIKE-OD-8471` | 200 | `application/json; charset=utf-8` | 74 | `[]`, 0 Treffer |
| 3 | `alice` | `?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | 200 | `application/json; charset=utf-8` | 74 | `[]`, 0 Treffer |
| 4 | `bob` | `?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | 200 | `application/json; charset=utf-8` | **4746** | ein Objekt: `id 38`, `displayId "38"`, `subject "SPIKE-OD-8471 privat"`, `_type WorkPackage` |
| 5 | `alice` | `?searchQuery=Demo&isSmartPicker=true` | 200 | `application/json; charset=utf-8` | 35239 | 14 Objekte, `id 38` **nicht** darunter |
| 6 | `bob` | `?searchQuery=Demo&isSmartPicker=true` | 200 | `application/json; charset=utf-8` | 36308 | 14 Objekte, `id 38` **nicht** darunter |
| 7 | `bob`, `APP_SECRET` aus 64 Nullen | `?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | 401 | `application/json; charset=utf-8` | 106 | `statuscode 997`, `Current user is not logged in` |
| 8 | `carol` | `?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | 401 | `application/json; charset=utf-8` | 77 | `statuscode 401`, Meldung leer |

Die Zeilen 1 und 2 sind der Lauf nach dem Wortlaut des Auftrags, die Zeilen 3 und 4 derselbe Lauf mit
`isSmartPicker=true`. Der Unterschied zwischen Zeile 2 und Zeile 4 ist der Grund, warum der Parameter
in 2.1 einen eigenen Absatz hat: dasselbe Konto, dasselbe Suchwort, einmal 0 und einmal 1 Treffer.

Die zugehörige Zustandsmessung an der Ursache, **nicht** unter einem der Messkonten, sondern mit dem
Aufbauzugang `Basic apikey:<OP_API_TOKEN>` des Kontos `admin`:

```
GET http://op.localtest.me:8082/api/v3/storages
-> HTTP 200, 131 Bytes, total 0, count 0, _embedded.elements leer
```

Keine registrierte Ablage, also greift der Filter `linkable_to_storage_url` für kein Arbeitspaket. Die
Zeile steht ausdrücklich in Abschnitt 5 und nicht in der Messwerttabelle von S3: sie erklärt die
Vorgabe der Fläche und ist selbst kein Messwert über Berechtigungen, weil ein Administrator in
OpenProject alles sieht.

#### 5.5.2 Der künstliche Ablauf und die Erneuerung (S4)

Gemessen am 2026-08-28, ausschließlich am Konto `bob`. Die Zustandswerte kommen aus
`occ user:setting bob integration_openproject <schlüssel>`, ausgeführt als `www-data` im
Nextcloud-Container. Tokenwerte stehen nach der Geheimnisregel nur mit Länge und
Vier-Zeichen-Präfix.

| # | Zeitpunkt (Unix) | Schritt | Rohwert |
|---|------------------|---------|---------|
| 1 | 1787943289 | `token_expires_at` gelesen | `1787949020` |
| 2 | 1787943289 | `token` gelesen | Länge 43, Präfix `dbHz` |
| 3 | 1787943289 | `refresh_token` gelesen | Länge 43, Präfix `bHRR` |
| 4 | 1787943305 | `token_expires_at 0` gesetzt, zurückgelesen | `0` |
| 5 | 1787943305 | OCS-Aufruf als `bob`, `?searchQuery=SPIKE-OD-8471&isSmartPicker=true` | **200**, `application/json; charset=utf-8`, 4746 Bytes, ein Treffer `id 38` |
| 6 | 1787943305 | `token_expires_at` gelesen | `1787950505` (Differenz zu Zeile 5: **7200**) |
| 7 | 1787943305 | `token` gelesen | Länge 43, Präfix `7Gvk` (verschieden von Zeile 2) |
| 8 | 1787943305 | `refresh_token` gelesen | Länge 43, Präfix `eXhd` (verschieden von Zeile 3) |
| 9 | 1787943322 | `refresh_token` auf 43 Nullen gesetzt, `token_expires_at 0`, zurückgelesen | `0` |
| 10 | 1787943322 | derselbe OCS-Aufruf als `bob` | **401**, `application/json; charset=utf-8`, 77 Bytes, `statuscode 401`, Meldung leer |
| 11 | 1787943323 | `token_expires_at`, `token`, `refresh_token` gelesen | `0`, Präfix `7Gvk` unverändert, Präfix `0000` |
| 12 | nach Zeile 11 | `occ user:setting alice integration_openproject token_expires_at` | `1787949009`, unverändert gegenüber 17-05 |

Die Protokollzeilen im Zeitfenster der beiden Läufe, mit `grep` über
`/var/www/html/data/nextcloud.log` gezählt: **0** Zeilen zu `18:55:0x` (Hauptlauf, Zeile 5) und **2**
Zeilen zu `18:55:23` (Gegenprobe, Zeile 10). Die zweite davon steht wörtlich in 2.1; ihr Fehlerfeld
ist `invalid_grant`, dasselbe, das 2.2 auf Weg 1 für einen erfundenen `refresh_token` gemessen hat.
Die Zeile ist vor der Übernahme in diesen Bericht gegen jeden Wert der Verbindungsdatei geprüft
worden und trägt keinen davon.

#### 5.5.3 Die Byte-Messung und die Bezugsgröße (S6)

Gemessen am 2026-08-28. Die erste Zeile ist dieselbe Antwort wie Zeile 4 von 5.5.1, es ist kein
zweiter Aufruf dafür gefahren worden. Die Zählung selbst lief über die gespeicherte Antwortdatei
außerhalb des Repositoriums.

| Gegenstand | Rohwert |
|------------|---------|
| OCS-Antwort als `bob`, ein Treffer `id 38` | 4746 Bytes, 0 Zeilenumbrüche, 0 Tabulatoren, 0 doppelte Leerzeichen, 182 Vorkommen von `\/`, 0 Vorkommen von `\u` |
| dieselbe Antwort ohne Schrägstrich-Maskierung neu kodiert | 4564 Bytes |
| das Arbeitspaket-Objekt allein | 4490 Bytes, 25 Schlüssel oberster Ebene, kein `_embedded` |
| `_links` darin | 3895 Bytes, 49 Relationen |
| die 24 Felder darin | 585 Bytes |
| OCS-Antwort als `alice`, Suchwort `Upload presentations`, ein Treffer `id 12` | 2542 Bytes, 27 Relationen (1772 Bytes), 22 Felder (588 Bytes) |

Die Bezugsgrößen derselben Instanz, alle mit dem Aufbauzugang `Basic apikey:<OP_API_TOKEN>` des Kontos
`admin` und ausdrücklich ohne Beweiskraft über Berechtigungen:

```
GET /api/v3/work_packages/38                                            -> 200,  8115 Bytes
GET /api/v3/work_packages/38?select=id,subject                          -> 200,  8115 Bytes
GET /api/v3/work_packages?filters=[{"id":{"operator":"=","values":["38"]}}]
                                                                        -> 200, 15831 Bytes
   ... &select=total,elements/id,elements/subject                       -> 200,    88 Bytes
   ... &select=total,elements/id,elements/subject,elements/project,
              elements/status,elements/type,elements/self                -> 200,   361 Bytes
   ... &select=...,elements/updatedAt                                   -> 400,   310 Bytes,
       urn:openproject-org:api:v3:errors:InvalidSignal
```

Der Filterwert ist hier lesbar geschrieben, gefahren wurde er prozentkodiert. Die 88 und die 361 Bytes
sind die einzigen Antworten dieses Plans **mit** Leerraum: der `select`-Zweig serialisiert mit einem
Leerzeichen nach dem Doppelpunkt, der reguläre Zweig ohne. Für den Vergleich mit den 4746 Bytes ist das
ohne Bedeutung und steht hier nur der Vollständigkeit halber.

#### 5.5.4 Der natürlich verstrichene Ablauf an `alice` (Nachtrag zu S4)

Gemessen am 2026-08-29 beim Nachprüfen der Zahlen aus 5.5.3. Der Lauf war nicht als Messung geplant
und ist deshalb der sauberste, den dieser Plan hat: an `alice` ist zu keinem Zeitpunkt ein
`occ user:setting` gefahren worden, weder schreibend noch zur Vorbereitung. Der Ablauf ist von selbst
verstrichen, zwischen der Einrichtung in Plan 17-05 und diesem Aufruf.

| # | Zeitpunkt (Unix) | Schritt | Rohwert |
|---|------------------|---------|---------|
| 1 | 1787968632 | Systemzeit zum Zeitpunkt des Aufrufs | `1787968632` |
| 2 | vor 1 | `token_expires_at` von `alice`, gesetzt in 17-05, seither unangetastet | `1787949009`, Differenz zu Zeile 1: **-19623** |
| 3 | 1787968632 | OCS-Aufruf als `alice`, `?searchQuery=Upload%20presentations&isSmartPicker=true`, ohne Cookie, ohne App-Passwort | **200**, `application/json; charset=utf-8`, **2542 Bytes**, ein Treffer `id 12`, `subject "Upload presentations to website"` |
| 4 | nach 3 | `occ user:setting alice integration_openproject token_expires_at` | **`1787975808`**, Differenz zu Zeile 1: **+7176** |

Die Zahl aus Zeile 2 ist dieselbe, die Zeile 12 von 5.5.2 als unverändert protokolliert hat. Zeile 12
bleibt für ihren Zeitpunkt richtig; wer den Wert heute liest, findet den aus Zeile 4. Die Antwort aus
Zeile 3 ist dieselbe, deren Byte- und Feldzahlen 5.5.3 unter `alice` führt: es ist **ein** Aufruf, der
zwei Fragen beantwortet, und kein zweiter dafür gefahren worden.

### 5.6 Stufe C: Keycloak, `user_oidc` und die Rohwerte von S5

Gemessen am 2026-08-29. Alle Aufrufe gingen durch Caddy an `http://127.0.0.1:8091` oder an
`http://kc.localtest.me:8083` (löst öffentlich auf `127.0.0.1` auf, im Nextcloud-Container über
`extra_hosts` auf `172.29.43.10`). Es gilt die Geheimnisregel vom Kopf dieses Abschnitts: kein Token,
kein Client-Secret, kein Cookie und kein Wert des Kopfes `AUTHORIZATION-APP-API` steht in einer Zeile.

#### 5.6.1 Aufbau, nicht Messung

Wie in 5.3 gilt auch hier: der folgende Aufbau ist **kein** Messwert. Er steht hier, damit ein
Wiederholungslauf ihn ohne Raten nachfährt.

| Schritt | Kommando oder Wert | Ergebnis |
|---|---|---|
| Keycloak gestartet | `docker compose -f compose.spike-opendesk.yml --profile op --profile oidc up -d` | `Keycloak 26.7.0 on JVM (powered by Quarkus 3.33.2.1) started in 15.852s` |
| Realm und Clients | `kcadm.sh` im Container, nicht `--import-realm` | Realm `spike` aktiv; Clients `nextcloud` (vertraulich, Rückadresse `http://127.0.0.1:8091/*`) und `openproject` (nur Zielgruppe) |
| Konten in der Realm | `kcadm.sh create users` plus `set-password` | `alice` und `bob`, beide aktiv, Passwörter in `.env.spike-opendesk` |
| Client-Secret | `kcadm.sh get clients/<id>/client-secret` | **86 Zeichen**; nach `.env.spike-opendesk` als `KC_CLIENT_SECRET` geschrieben und mit dem laufenden Wert verglichen |
| `user_oidc` installiert | `occ app:install user_oidc` | `user_oidc 8.11.0 installed`, `user_oidc enabled` |
| Anbieter eingerichtet | `occ user_oidc:provider spike --clientid=nextcloud --clientsecret=... --discoveryuri=http://kc.localtest.me:8083/realms/spike/.well-known/openid-configuration --scope="openid email profile"` | `occ user_oidc:providers`: `identifier spike`, `clientId nextcloud`, Scope `openid email profile`, `clientSecret` vom Werkzeug selbst als `********` ausgegeben |
| Sitzungstoken speichern | `occ config:app:set user_oidc store_login_token --value=1` | `1` |
| Loglevel **vor** dem ersten Lauf | `occ log:manage --level 0` | `Log level: Debug (0)` |
| Modus geschaltet | `occ config:app:set integration_openproject authorization_method --value=oidc`, dazu `sso_provider_type external`, `oidc_provider spike`, `targeted_audience_client_id openproject`, `token_exchange 0` | alle fünf zurückgelesen |

**Zwei Erreichbarkeitswerte, die den Namen und nicht nur die Adresse prüfen** (dieselbe Regel wie in
5.2):

```
GET http://kc.localtest.me:8083/realms/spike/.well-known/openid-configuration
  vom Host:                        HTTP 200
  aus dem Nextcloud-Container:     HTTP 200
issuer im Dokument:                http://kc.localtest.me:8083/realms/spike
```

Der `issuer` trägt denselben Namen und denselben Port wie beide Aufrufe. Genau das ist der Punkt der
Portabbildung 8083 innen wie außen.

#### 5.6.2 Zwei Aufbaufehler, die keine S5-Befunde sind

Beide sind hier protokolliert, weil sie beim Nachfahren je einen Anlauf kosten und beide wie ein
Fehler des Produkts aussehen, ohne einer zu sein.

| Fehlschlag | Wörtliche Meldung | Ursache und Auflösung |
|---|---|---|
| Keycloak startete nicht, Neustartschleife | `ERROR: Failed to start server in (development) mode` / `Provided hostname is neither a plain hostname nor a valid URL` | `KC_HOSTNAME` war als `kc.localtest.me:8083` gesetzt. 26.7.0 nimmt entweder einen Namen ohne Port oder eine vollständige URL. Aufgelöst mit `http://kc.localtest.me:8083` |
| `GET /apps/user_oidc/login/1` antwortete **404** mit einer Fehlerseite | `You must access Nextcloud with HTTPS to use OpenID Connect.` | `LoginController::isSecure()` (`LoginController.php:121-126`) verlangt https, den Debug-Modus **oder** den App-Konfigwert `allow_insecure_http`. Aufgelöst mit `occ config:app:set user_oidc allow_insecure_http --value=1 --lazy`; danach antwortet derselbe Aufruf **303** auf den Autorisierungsendpunkt der Realm |

Die zweite Zeile ist zugleich ein Befund über die Messumgebung und keiner über openDesk: dort trägt
Nextcloud https, und die Bedingung fällt gar nicht an.

#### 5.6.3 Die Nutzer-Id, unter der `user_oidc` das Konto führt

Nach einer Anmeldung des Keycloak-Kontos `alice` durch den Autorisierungscode-Fluss (Start
`GET /apps/user_oidc/login/1`, Anmeldeformular der Realm, Rückweg auf
`http://127.0.0.1:8091/apps/user_oidc/code`) endete der Rückweg mit **303** auf
`/apps/dashboard/`, und `GET /ocs/v2.php/cloud/user` mit demselben Cookie antwortete **200** mit
`"backend":"user_oidc"`.

```
occ user:list
  - admin: admin
  - alice: alice
  - 3855a8f7d81aae5de814f2a6d77bd149591983992337ec676fb84ebda333cfe3: Alice Spike
  - bob: bob
  - carol: carol
```

**Die Id weicht ab, und das ist der Grund, warum jede S5-Zeile ihren Nutzernamen nennt.** Das
Keycloak-Konto `alice` und das Nextcloud-Konto `alice` sind zwei verschiedene Konten; `user_oidc`
führt das erste unter dem Streuwert `3855a8f7d81aae5de814f2a6d77bd149591983992337ec676fb84ebda333cfe3`
mit dem Anzeigenamen `Alice Spike`.

#### 5.6.4 Die sechs Läufe von S5, Rohwerte

Jeder Lauf: `occ user:setting <konto> integration_openproject token_expires_at 0`, danach
`GET /ocs/v2.php/apps/integration_openproject/api/v1/work-packages?searchQuery=SPIKE-OD-8471&isSmartPicker=true`
unter reiner AppAPI-Impersonation, danach die Zustandswerte erneut gelesen und das Protokoll ab der
Zeilenzahl vor dem Aufruf frisch gelesen.

| # | Unix-Zeit | `sso_provider_type` / `token_exchange` / `store_login_token` | Konto | Antwort | `token` danach | `token_expires_at` danach |
|---|---|---|---|---|---|---|
| 1 | 1787970751 | `external` / `0` / `1` | `3855a8f7...` | **401**, `application/json; charset=utf-8`, **77 Bytes** | nicht vorhanden | `0` |
| 2 | 1787970764 | `external` / `0` / `0` | `3855a8f7...` | **401**, **77 Bytes** | nicht vorhanden | `0` |
| 3 | 1787970773 | `external` / `1` / `0` | `3855a8f7...` | **401**, **77 Bytes** | nicht vorhanden | `0` |
| 4 | 1787970781 | `external` / `1` / `1` | `3855a8f7...` | **401**, **77 Bytes** | nicht vorhanden | `0` |
| 5 | 1787970800 | `nextcloud_hub` / `0` / `1` | `3855a8f7...` | **401**, **77 Bytes** | nicht vorhanden | `0` |
| 6 | 1787970817 | `external` / `0` / `1` | `alice` | **401**, **77 Bytes** | Länge 43, Präfix `Jm2D`, unverändert | `0` |

Der Körper ist in allen sechs Zeilen identisch:
`{"ocs":{"meta":{"status":"failure","statuscode":401,"message":""},"data":""}}`.

**Die Protokollzeilen dieser sechs Läufe, wörtlich und mit Stufe, Zeit und Konto.** Übernommen sind
ausschließlich die Meldungen der Apps `user_oidc` und `integration_openproject`; die Kontextfelder mit
Kopfzeilen sind nicht übernommen (T-17-01), und jede Zeile ist vor der Übernahme gegen jeden Wert aus
`.env.spike-opendesk` geprüft worden.

```
# Lauf 1, external / token_exchange 0 / store_login_token 1, Konto 3855a8f7...
level 0, 2026-08-29T02:32:32+00:00, user_oidc  "[ExternalTokenRequestedListener] received request"
level 0, 2026-08-29T02:32:32+00:00, user_oidc  "[TokenService] Get token from the session"
level 0, 2026-08-29T02:32:32+00:00, user_oidc  "[TokenService] getToken: no session data"
level 3, 2026-08-29T02:32:32+00:00, integration_openproject
                                               "Token event has not been caught by 'user_oidc'"

# Lauf 2, external / 0 / 0
level 0, 2026-08-29T02:32:44+00:00, user_oidc  "[ExternalTokenRequestedListener] received request"
level 3, 2026-08-29T02:32:44+00:00, integration_openproject
   "Failed to get token: Failed to get external token, login token is not stored"

# Lauf 3, external / 1 / 0
level 0, 2026-08-29T02:32:53+00:00, user_oidc
   "[ExchangedTokenRequestedListener] received request for audience: openproject"
level 3, 2026-08-29T02:32:53+00:00, integration_openproject
   "Failed to get token: Failed to exchange token, storing the login token is disabled.
    It can be enabled in config.php"

# Lauf 4, external / 1 / 1
level 0, 2026-08-29T02:33:01+00:00, user_oidc
   "[ExchangedTokenRequestedListener] received request for audience: openproject"
level 0, 2026-08-29T02:33:01+00:00, user_oidc  "[TokenService] Starting token exchange"
level 0, 2026-08-29T02:33:01+00:00, user_oidc  "[TokenService] Get token from the session"
level 0, 2026-08-29T02:33:01+00:00, user_oidc  "[TokenService] getToken: no session data"
level 0, 2026-08-29T02:33:01+00:00, user_oidc
   "[TokenService] Failed to exchange token, no login token found in the session"
level 3, 2026-08-29T02:33:01+00:00, integration_openproject
   "Failed to get token: Failed to exchange token, no login token found in the session"

# Lauf 5, nextcloud_hub / 0 / 1
level 0, 2026-08-29T02:33:20+00:00, user_oidc
   "[InternalTokenRequestedListener] received request for audience: openproject"
level 2, 2026-08-29T02:33:20+00:00, user_oidc
   "[TokenService] Failed to get token from Oidc provider app, oidc app is not installed"
level 3, 2026-08-29T02:33:20+00:00, integration_openproject
                                               "Token event has not been caught by 'user_oidc'"

# Lauf 6, external / 0 / 1, Konto alice
level 0, 2026-08-29T02:33:37+00:00, integration_openproject  "Token has expired."
level 0, 2026-08-29T02:33:37+00:00, integration_openproject  "Refreshing access token."
level 0, 2026-08-29T02:33:37+00:00, user_oidc  "[ExternalTokenRequestedListener] received request"
level 0, 2026-08-29T02:33:37+00:00, user_oidc  "[TokenService] Get token from the session"
level 0, 2026-08-29T02:33:37+00:00, user_oidc  "[TokenService] getToken: no session data"
level 3, 2026-08-29T02:33:37+00:00, integration_openproject
                                               "Token event has not been caught by 'user_oidc'"
```

#### 5.6.5 Die Gegenprobe mit echter Sitzung und der Lauf gegen den gültigen Zwischenspeicher

```
# 1787970835, derselbe Aufruf, aber mit dem Sitzungscookie aus der Keycloak-Anmeldung,
# Konto 3855a8f7..., Konfiguration external / 0 / 1
HTTP 401, application/json; charset=utf-8, 341 Bytes
ocs.meta.statuscode 401, Meldung leer
ocs.data.error trägt "errorIdentifier":"urn:openproject-org:api:v3:errors:Unauthenticated"

level 0, user_oidc  "[TokenService] Get token from the session"
level 0, user_oidc  "[TokenService] getToken: token is expiring, proactively refreshing to keep
                     IdP session alive, expires in 80"
level 0, user_oidc  "[TokenService] Refreshing the token:
                     http://kc.localtest.me:8083/realms/spike/protocol/openid-connect/token"
level 0, user_oidc  "[TokenService] ---- Refresh token success"
level 0, user_oidc  "[TokenService] Store token in the session"
level 0, user_oidc  "[TokenService] checkLoginToken: all good"
level 0, user_oidc  "[ExternalTokenRequestedListener] received request"
level 0, user_oidc  "[TokenService] getToken: token is still valid, it expires in 300 and
                     refresh expires in 1800"
level 0, integration_openproject  "New token expires at 2026/08/29 02:38:56"
level 3, integration_openproject  "OpenProject error : Client error:
                     `GET http://op.localtest.me:8082/api/v3/users/me` resulted in a
                     `401 Unauthorized` response"
```

Zustand am Konto `3855a8f7...` unmittelbar danach: `token` mit **Länge 1387** in der Form eines JWT
(drei durch Punkte getrennte Base64url-Abschnitte, der Wert selbst steht hier nicht),
`token_expires_at` `1787971136`; `user_id` und `user_name` existieren **nicht**, weil `initUserInfo()`
an der Abweisung durch OpenProject scheitert.

```
# 1787970877, wieder ohne Cookie, reine Impersonation, Konto 3855a8f7...,
# token_expires_at 1787971136 und damit 259 s in der Zukunft
HTTP 401, application/json; charset=utf-8, 341 Bytes
ocs.data.error trägt "errorIdentifier":"urn:openproject-org:api:v3:errors:Unauthenticated"

Zeilen der App user_oidc in diesem Zeitfenster: KEINE
level 3, integration_openproject  "OpenProject error : Client error:
                     `GET http://op.localtest.me:8082/api/v3/users/me` resulted in a
                     `401 Unauthorized` response"
```

**Der Unterschied zwischen diesem Lauf und den sechs aus 5.6.4 ist eine einzige Zahl**, der Ablauf des
zwischengespeicherten Tokens, und er entscheidet, ob `user_oidc` überhaupt gefragt wird
(`getAccessToken()`, Zeile 1748). Die 341 gegen 77 Bytes sind der maschinell prüfbare Ausdruck
desselben Unterschieds.

## Reproduktion

Die Messumgebung ist nach dem letzten Lauf abgeräumt worden. Was hier steht, ist die Befehlsfolge, mit
der sie wieder entsteht, samt der Schritte, die nur über eine Oberfläche gehen, und samt dem einen
Befehl, mit dem sie wieder verschwindet.

**Stufe A, Nextcloud 33.0.7 samt ExApp:**

```
export HP_SHARED_KEY="$(openssl rand -hex 32)"
export SECRET_KEY_BASE="$(openssl rand -hex 32)"
docker compose -f compose.spike-opendesk.yml up -d --wait
bash scripts/bootstrap_spike_opendesk.sh
set -a && . ./.env.spike-opendesk && set +a
```

Beide `export` sind auch dann Pflicht, wenn nur Stufe A laufen soll: Compose interpoliert die ganze
Datei, bevor es nach Profilen filtert, gemessen am 2026-08-28 gegen Docker 29.5.2 (Kopf von
`compose.spike-opendesk.yml`). Der Bootstrap schreibt die Verbindungsdatei `.env.spike-opendesk`; sie
ist **git-ignoriert** (`.gitignore` Zeile 17), weil sie zwei funktionierende App-Passwörter, den
HaRP-Schlüssel und das `APP_SECRET` der Registrierung trägt. `.env.spike-opendesk.example` führt
ausschließlich die Variablennamen und keinen einzigen Wert; jede Geheimniszeile darin ist auskommentiert.

**Stufe B, OpenProject 17.7.2, und Stufe C, Keycloak 26.7.0:**

```
docker compose -f compose.spike-opendesk.yml --profile op up -d --wait
docker compose -f compose.spike-opendesk.yml --profile op --profile oidc up -d
```

**Die Schritte, die nur über eine Oberfläche gehen.** Zwei Stellen dieses Berichts hat der Owner im
Browser gemacht, und sie stehen deshalb nicht in der Befehlsfolge oben:

* die OAuth-Anwendungen in OpenProject, `nc-mcp-spike-weg0` und `nc-mcp-spike-weg1`, unter
  Administration, Authentication, OAuth applications. Zu 17.7.2 ließ sich kein dokumentierter Weg zum
  Seeden einer OAuth-Anwendung finden, und `registration_endpoint` fehlt in den Metadaten (2.2). Die
  Anweisungen dazu stehen in den Plänen 17-03 (Weg 1) und 17-05 (Weg 0), samt dem Hinweis, dass
  "Confidential" und "Client Credentials User ID" leer bleiben (5.3).
* der persönliche Durchlauf je Konto für Weg 0. Er ist in 17-05 ohne Browser nachgefahren worden
  (Schritte 1 bis 9 in 2.1), die Anweisung an den Owner nennt trotzdem den Browserweg, weil der
  Formularweg an zwei Stellen kippen kann.

**Wie der Zustand wieder verschwindet:**

```
docker compose -f compose.spike-opendesk.yml --profile op --profile oidc down -v
```

Das `-v` ist keine Bequemlichkeit, sondern für Keycloak Pflicht: die Realm `spike` wird mit `kcadm.sh`
erzeugt und nicht mit `--import-realm`, und ein Import überspringt eine vorhandene Realm, statt sie zu
aktualisieren. Ein zweiter Lauf auf einem behaltenen Band misst also die Konfiguration des ersten. Mit
demselben Befehl verschwinden auch die zwei Eingriffe an der Nextcloud-Instanz, der auf `Debug (0)`
gesenkte Loglevel und `allow_insecure_http`, weil beide im Nextcloud-Band liegen.

Ein Ding bleibt nach `down -v` liegen und ist keins dieser Topologie: der Deploy-Daemon benennt den
ExApp-Container global `nc_app_<appid>`, nicht projektgebunden. Wer danach die Topologie aus
`compose.exapp.yml` wieder braucht, holt sich den Namen mit ihrem eigenen Bootstrap zurück:

```
export HP_SHARED_KEY="$(sed -n 's/^HP_SHARED_KEY=//p' .env.exapp)"
docker compose -f compose.exapp.yml up -d --wait
bash scripts/bootstrap_exapp.sh
```

## Was diese Messung nicht beweist

Die Ränder stehen hier vollständig und nicht als Auswahl. Wer einen Messwert dieses Berichts über einen
dieser Ränder hinaus benutzt, benutzt ihn falsch, und zwar nachlesbar falsch.

**Sie lief gegen eine Wegwerf-Instanz und gegen genau die Fassungen aus dem Kopfblock.** Nextcloud
33.0.7 auf **SQLite** (`SQLITE_DATABASE: nextcloud` in `compose.spike-opendesk.yml`), leere Bände, ohne
Last, ohne zweiten Knoten, `integration_openproject` 3.1.1, `user_oidc` 8.11.0, OpenProject 17.7.2,
Keycloak 26.7.0. Eine andere Fassung darf sich anders verhalten: alle Zeilennummern und alle
Quellenzitate dieses Berichts gelten für diese Fassungen und für keine andere, und die OCS-Fläche ist
aus `appinfo/routes.php` **dieser** Fassung gezählt.

**Der lokale Aufbau reproduziert openDesk nicht, und zwar in fünf benannten Punkten.**

1. **Keycloak als Anmeldezwang ohne lokales Formular.** In openDesk setzt
   `OPENPROJECT_OMNIAUTH__DIRECT__LOGIN__PROVIDER: "keycloak"` das lokale Anmeldeformular außer Kraft.
   Genau dieses Formular ist Schritt 2 des gemessenen Weg-1-Messwegs (2.2). Der Zustimmungsfluss hat
   dort einen zusätzlichen Umleitungsschritt, und der ist hier ungemessen (2.5).
2. **Die Scope-Pflicht für ein OIDC-JWT.** Seit OpenProject 16.0.0 verlangt ein OIDC-Token den
   `scope`-Anspruch mit `api_v3`. Im lokalen OAuth-Modus, in dem alle Weg-1-Messwerte entstanden sind,
   ist diese Pflicht unsichtbar, weil OpenProject die Tokens selbst ausgibt (2.5).
3. **Die Datenlage.** Die Seed-Instanz hat ein Projekt und wenige Arbeitspakete; die Asymmetrie, auf
   der beide Negativbeweise stehen, ist in 5.3 von Hand angelegt worden. Eine Behördeninstanz hat
   andere Projekte, andere Rollen, andere Sichtbarkeiten, und die 14 Treffer auf das Suchwort `Demo`
   sind eine Eigenschaft der Seed-Daten und keine Aussage über eine echte Instanz.
4. **Kubernetes samt Helm und abgeschaltetem App Store.** openDesk läuft über ein Helmfile in einem
   Cluster und hat den App Store aus (1.1); diese Messung lief in vier bis sieben Docker-Containern auf
   127.0.0.1, und die vier optionalen Apps sind hier aus genau dem App Store installiert worden, den es
   dort nicht gibt (S0). Kein Kubernetes-Cluster ist beschafft und keine openDesk-Installation versucht
   worden (D-01, D-03).
5. **Die tatsächliche Betriebsart von `integration_openproject`.** Eingerichtet wurde hier Weg B über
   `occ config:app:set` plus persönlichen Durchlauf je Konto; der openDesk-Bootstrap-Job geht Weg A,
   und Weg A ist in dieser Topologie gemessen nicht gangbar und deshalb ungemessen (2.5, 5.4). Ob dort
   `oauth2` oder `oidc` läuft, ist Frage 7.

**Die Egress-Kontrollmessung beweist über eine Behördeninstallation nichts.** Sie lief im lokalen
Docker-Netz, in dem alle Container in einem Netz hängen und nichts sie trennt; eine Antwort ist dort
erwartbar. In einer Behördeninstallation entscheiden Netzrichtlinien, Egress-Filter und Proxy-Zwang, ob
eine ExApp einen zweiten Host erreicht, und keine dieser Bedingungen ist hier nachgebildet.

**Die Zahlen aus `community.openproject.org` sind Kontext und kein Messwert dieser Instanz.** Die 3691
und 216 Bytes aus 3.2 stammen aus der Recherche gegen eine fremde Instanz mit anderem Modulsatz; sie
stehen dort als Größenordnung neben den gemessenen 15831 und 88 Bytes und nirgends als Beleg.

**Drei Eingriffe halten diesen Aufbau am Laufen, und sie stehen hier, weil ein Nachbau sie sonst für
Vorgabe hält.**

* **`allow_local_remote_servers = true` in Nextcloud** (Abschnitt 2.1, "Der persönliche Durchlauf lief
  ohne Browser"): ohne diese Systemeinstellung antwortet der Rückweg von Weg 0 zwar `303`, die Verbindung steht
  aber nicht, wörtlich `Host "127.0.0.1" (op.localtest.me:80) violates local access rules`. Sie ist
  eine Lockerung **der Messumgebung** und betrifft die ausgelieferte ExApp an keiner Stelle; für eine
  openDesk-Installation ist sie ohne Bedeutung, weil dort beide Seiten routbare Adressen haben.
* **Das Passwort des OpenProject-Kontos `admin` ist per `rails runner` gesetzt worden** (5.3), weil die
  dokumentierte Vorgabe `admin`/`admin` von dieser Instanz abgewiesen wurde. **Warum das Seed-Passwort
  abwich, ist nicht untersucht**, steht als offener Punkt in 2.5 und nicht als Vermutung. Der erzwungene
  Passwortwechsel hat damit nicht stattgefunden.
* **Keycloak und `user_oidc` sind ausschließlich für S5 dazugekommen** (5.6), nicht als Teil des
  Aufbaus von Weg 0 oder Weg 1: Keycloak lief als `start-dev` auf einer Datenbank im Arbeitsspeicher,
  die Realm ist mit `kcadm.sh` erzeugt worden, und der `sso_provider_type` jedes Laufs ist von diesem
  Bericht selbst gesetzt. Keiner dieser Werte ist aus openDesk übernommen.

**Zwei Punkte, an denen der Bericht ausdrücklich weniger sagt, als ein Leser gern hätte.** Der einzige
sitzungsfreie OIDC-Pfad, `nextcloud_hub`, ist nicht widerlegt, sondern ungemessen; wer Weg 0 im
OIDC-Betrieb verwirft, verwirft ihn ohne diesen Messwert (2.5). Und die für OD-04 wertvollste Route,
`GET /api/v1/work-packages/{id}/file-links`, ist ohne registrierte Ablage nicht aufgerufen worden;
belegt sind ihre Existenz und ihre Signatur, nicht ihr Verhalten (2.5, 3.3).

**Über den nativen MCP-Endpunkt von OpenProject sagt diese Messung nichts.** OpenProject 17.7.2 bringt
ihn mit, belegt aus dem laufenden Container: `mount API::Mcp => "/mcp"` in `config/routes.rb:48`, eine
Verwaltungsseite in Zeile 676, der Scope `mcp` in `doorkeeper.rb:136` und ein Seed-Schritt beim ersten
Start. Ein unauthentifizierter Aufruf antwortet 500, ist also eine antwortende Route und keine 404.
Über seine Werkzeugliste, seinen Authentifizierungsweg, seinen Berechtigungsdurchgriff und darüber, ob
openDesk ihn einschaltet, ist **nichts** gemessen. Der Fund berührt OD-04 (es gäbe einen dritten Weg,
auf dem der Assistent beide Server nebeneinander spricht) und gehört als Frage in den ISV-Kanal, nicht
als Aussage in diesen Bericht (DI-17-01).

**Zwei weitere Eingriffe derselben Art, und sie sind Aussagen über die Messumgebung und nicht über ein
Ergebnis.** Für S5 ist der Nextcloud-Loglevel auf `Debug (0)` gesenkt worden
(`occ log:manage --level 0`), und zwar vor dem ersten Lauf: die drei Meldungen, die die Ereignispfade
unterscheiden, sind `logger->debug`, und der Vorgabewert `Warning (2)` verschluckt sie. Ebenso ist
`occ config:app:set user_oidc allow_insecure_http --value=1` gesetzt worden, weil `user_oidc` die
Anmeldung sonst mit `You must access Nextcloud with HTTPS to use OpenID Connect.` abbricht
(`LoginController.php:121-126`).

**Beides betrifft eine Wegwerf-Instanz auf 127.0.0.1 und ist ausdrücklich keine Empfehlung für
Produktion.** Ein auf `debug` gesenkter Nextcloud-Log kann Nutzerdaten und Tokenbruchstücke in eine
Datei schreiben, die für dieses Niveau nicht gedacht ist, und OpenID Connect über plain http gibt das
Sitzungstoken auf der Leitung preis. Beide Zustände verschwinden mit dem Nextcloud-Band beim
`down -v`, und die ausgelieferte ExApp ist von keinem der beiden berührt. Sie stehen hier, damit ein
Nachbau sie als Eingriff erkennt und nicht als Vorgabe übernimmt.

## Der Produktionsbaum nach dieser Phase

Erfolgskriterium 5 der Roadmap verlangt einen stillstehenden Produktionsbaum: kein neues Werkzeug, kein
neuer Client im Paket, Werkzeugoberfläche und Budget-Gate unverändert (D-12). Das ist keine Zusicherung,
sondern ein Nachweis, und er besteht aus vier Läufen am 2026-08-29, alle gegen den Stand dieses
Berichts.

Die 21-Tool-Zahl unten ist die historische Messung dieses Berichts. Die aktuelle Zahl liegt in
`tests/contract/test_tool_surface.py`.

| # | Nachweis | Kommando | Ergebnis |
|---|----------|----------|----------|
| 1 | Nichts liegt unverfolgt herum, und nichts hat sich seit dem Stand vor der Phase bewegt | `git status --short src/ appinfo/ pyproject.toml uv.lock` und `git diff --stat 90d2f68..HEAD -- src appinfo pyproject.toml uv.lock` | beide **leer**. `90d2f68` ist der letzte Commit vor `docs(17): research openDesk spike domain`, also der Stand vor der Phase. Die Phase hat 33 Dateien geändert, keine davon unter `src/` oder `appinfo/` |
| 2 | Die Werkzeugoberfläche ist unverändert | `uv run python scripts/check_tool_budget.py` | `tools/list: 15712 bytes, 21 tools, budget 18000`, Zeichen für Zeichen dieselbe Zeile wie am 2026-08-28. Keine Grenze ist angehoben worden |
| 3 | Die Vorgabesuite ist grün | `uv run pytest -q` | **2813 passed, 163 deselected** in 72,69 s. Es ist keine Test-Datei entstanden: die Spike-Messungen laufen außerhalb der Suite |
| 4 | Lint und Format sind grün | `uv run ruff check .` und `uv run ruff format --check .` | `All checks passed!` und `202 files already formatted`. `.planning/` ist von ruff ausgenommen, und das bleibt so |

Der Nachweis 2 ist der scharfe von den vieren. Ein Werkzeug, das unbemerkt dazukommt, fällt in einem
Diff über 33 Dateien nicht auf, in dieser einen Zeile aber sofort, weil sie drei Zahlen gleichzeitig
nennt. Weicht eine davon ab, ist das ein Fehlschlag von Erfolgskriterium 5 und keine Kleinigkeit.

**Die Messumgebung ist abgeräumt.** `docker compose -f compose.spike-opendesk.yml --profile op
--profile oidc down -v` hat die sechs Container mit dem Präfix `nc-mcp-spike-od` und alle fünf Bände
der Topologie entfernt. `docker ps -a` nennt danach keinen Container mit diesem Präfix,
`docker volume ls` kein Band und `docker network ls` kein Netz. Die Wegwerf-Instanz mit ihren
Wegwerf-Passwörtern, dem abgeschalteten Bruteforce-Schutz, dem auf `debug` gesenkten Loglevel und
`allow_local_remote_servers = true` existiert damit nicht mehr.

**Ein siebter Container trägt den Präfix nicht und musste deshalb eigens abgeräumt werden, und das ist
derselbe Befund wie in 17-02, nur in der Gegenrichtung.** Der Deploy-Daemon benennt den ExApp-Container
global `nc_app_<appid>` und nicht projektgebunden. Nach dem `down -v` lief er weiter, hing als einziger
noch am Netz `nc-mcp-spike-od-net` (weshalb dessen Entfernung mit `Resource is still in use` scheiterte)
und trug das Bild aus der Registry auf `127.0.0.1:5001` der Spike-Topologie. Abgeräumt mit
`docker rm -f nc_app_mcp_connector` und `docker network rm nc-mcp-spike-od-net`.

**Die vorherige ExApp-Topologie ist wieder benutzbar.** `compose.exapp.yml`, die Plan 17-02
ausdrücklich nur mit `stop` angehalten und nie mit `down -v` entfernt hat, läuft wieder
(`up -d --wait`, fünf Container gesund). Weil die Registrierung in **ihrer** Nextcloud die Phase
überdauert hatte, während ihr Container zwischenzeitlich von der Spike-Topologie ersetzt worden war,
hat der idempotente Bootstrap ihn nicht neu ausgerollt, sondern die vorhandene Registrierung gemeldet.
Der Weg dafür steht im Skript selbst: `occ app_api:app:unregister mcp_connector --force`, danach
`bash scripts/bootstrap_exapp.sh`. Gegengeprobt ist der Endzustand und nicht die Absicht:
`occ app_api:app:list` nennt `mcp_connector (MCP Connector): 0.1.11 [enabled]`, der Container hängt
wieder am Netz `nc-mcp-exapp-net`, und ein `POST http://127.0.0.1:8081/exapps/mcp_connector/mcp` ohne
Token antwortet **401** statt der 503, die der stehengebliebene Spike-Container vorher lieferte.

Die Container fremder Projekte auf diesem Rechner sind nicht angefasst worden: `findling-nextcloud` und
`nc-mcp-test` laufen unverändert seit 13 Tagen beziehungsweise zwei Wochen.

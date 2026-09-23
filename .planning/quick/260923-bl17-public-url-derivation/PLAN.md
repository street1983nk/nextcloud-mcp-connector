---
phase: quick-260923-bl17
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/mcp_connector/exapp/config_values.py
  - src/mcp_connector/entry_exapp.py
  - src/mcp_connector/exapp/ui/strings.py
  - tests/unit/test_exapp_config_values.py
  - tests/unit/test_exapp_entry.py
  - appinfo/info.xml
  - docs/exapp-install.md
  - docs/oauth-setup.md
  - docs/faq.md
  - CHANGELOG.md
autonomous: true
requirements: [BL-17]
must_haves:
  truths:
    - "Eine AIO-No-Config-Installation (kein Admin-Formwert, kein NC_MCP_PUBLIC_URL) mit NEXTCLOUD_URL=https://<custom-domain> bekommt als issuer/resource-Basis https://<custom-domain>/exapps/<APP_ID>, ohne dass ein Mensch etwas setzt"
    - "Ein gesetzter NC_MCP_PUBLIC_URL und erst recht ein gespeicherter Admin-Formwert gewinnen unveraendert ueber die Ableitung"
    - "Ein NEXTCLOUD_URL, der http auf einem Nicht-Loopback-Host ist (AppAPI-Downgrade, interner Name) oder unlesbar ist, leitet NICHTS ab: der bestehende Fail-closed-Weg (Loopback-Default, Fehlerzeile, Setup-State) bleibt"
    - "Der IssuerRefused-Rescue nennt jetzt drei Quellen (Formwert > Deploy-Variable > Ableitung) und faellt nach dem Drop einer unbrauchbaren Deploy-Variable auf die Ableitung, bevor er den Loopback-Default nimmt"
  artifacts:
    - path: "src/mcp_connector/exapp/config_values.py"
      provides: "derived_public_url(env) mit derselben Validierungs- und Normalisierungsfamilie wie _public_url (CR-01, IN-03)"
    - path: "src/mcp_connector/entry_exapp.py"
      provides: "Ableitung als drittes Kettenglied in _resolved_env plus im Rescue; A2-Kommentar ersetzt; Fehlertexte nennen drei Quellen"
    - path: "tests/unit/test_exapp_config_values.py"
      provides: "Ableitungs-Happy-Path, Normalisierung, Garbage-Faelle"
    - path: "tests/unit/test_exapp_entry.py"
      provides: "Praezedenz-, Rescue- und Fail-closed-Tests durch den echten Startpfad"
  key_links:
    - from: "src/mcp_connector/entry_exapp.py::_resolved_env"
      to: "config_values.derived_public_url"
      via: "Injektion in das resolved-Mapping, nur wenn ENV_PUBLIC_URL nach dem Overlay-Merge leer ist"
      pattern: "derived_public_url"
    - from: "config_values.derived_public_url"
      to: "config_values._public_url-Validierungskern"
      via: "geteilter Validierungskern, zwei Log-Texte"
      pattern: "_public_url|_validated"
---

# BL-17: OAuth-Public-URL aus NEXTCLOUD_URL ableiten (AIO-No-Config-Installs)

## Ziel

Der 421-Fix aus Issue #4 leitet die Allowed Hosts bereits aus `NEXTCLOUD_URL` ab
(`config.deployment_hosts`). Die Public URL, die die OAuth-Antworten formt (issuer,
resource, Endpoint-Praefixe, Consent-Redirect), muss aber weiterhin von Hand gesetzt
werden: der letzte manuelle Schritt einer AIO-One-Click-Installation (jekkels
Abschlusskommentar auf Issue #4, BL-06-Linie).

Dieser Plan macht die Ableitung `<NEXTCLOUD_URL>/exapps/<APP_ID>` zum Default. Die
explizite Konfiguration bleibt Override und gewinnt. Ergibt keine der drei Quellen eine
brauchbare absolute URL, bleibt das heutige Fail-closed-Verhalten byte fuer byte
erhalten (Loopback-Default, Fehlerzeile, sichtbarer Setup-State, IssuerRefused-Rescue).

## Belegte Ableitungsform: `<NEXTCLOUD_URL>/exapps/<APP_ID>`, nie die nackte NC-URL

Die ExApp haengt hinter HaRP unter einem Pfad der Nextcloud-Instanz, nicht unter der
Instanz-Wurzel. Die Belege aus dem Repo:

1. `scripts/bootstrap_exapp.sh:196` macht heute schon exakt diese Ableitung:
   `PUBLIC_URL="${NC_EXAPP_PUBLIC_URL:-${BASE_URL}/exapps/${APP_ID}}"`. Der Plan hebt
   dieselbe Familie in den Serverstart.
2. `docs/exapp-install.md:78`: eine HaRP-ExApp ist erreichbar unter
   `<nextcloud_url>/exapps/<appid>`, also durch die oeffentliche Nextcloud-Adresse.
3. `appinfo/info.xml:489` nennt als Beispiel fuer `NC_MCP_PUBLIC_URL` genau
   `https://cloud.example.com/exapps/mcp_connector`.
4. `docs/oauth-setup.md:32`: die Installation routet `/exapps/*` zu HaRP, HaRP strippt
   den Praefix `/exapps/mcp_connector`; jeder Link traegt den Praefix aus
   `config.public_url` (STATE.md, Phase 03: absoluter Pfad ohne Praefix zeigte auf die
   Nextcloud-Wurzel).
5. AIO setzt `NEXTCLOUD_URL` auf die oeffentliche Custom Domain:
   `'nextcloud_url' => 'https://' . getenv('NC_DOMAIN')` (belegt im Docstring von
   `config.deployment_hosts`, `src/mcp_connector/config.py:507-513`).

**Assumption A2 (Phase 05, `entry_exapp.py:559` und STATE.md:465)** sagte: keine
Ableitung, weil AppAPI `NEXTCLOUD_URL` mit http statt https und moeglicherweise als
interne Adresse setzt; ein abgeleiteter Wert waere ein stiller Default mit kaputter
Discovery. A2s Sorge wird hier nicht ignoriert, sondern beantwortet: der abgeleitete
Kandidat laeuft durch DENSELBEN Validierungskern wie ein Admin-Formwert
(`config_values._public_url`: https oder Loopback per RFC 8414, kein Fragment, keine
Credentials, Port-Range, eine Schreibweise per IN-03). Ein heruntergestuftes
`http://nextcloud-aio-...` faellt an der https-Regel und leitet nichts ab, also kein
stiller kaputter issuer. Genau im AIO-Fall, den BL-17 loesen soll, ist der Wert dagegen
`https://<custom-domain>` und ueberlebt. Der A2-Kommentar in `entry_exapp.main` wird
entsprechend ersetzt (Sorge benannt, Antwort benannt), nicht kommentarlos geloescht.

## Praezedenzkette (belegt aus dem Code)

Heutige Kette, an der die Ableitung als drittes Glied eingehaengt wird:

| # | Quelle | Beleg |
|---|--------|-------|
| 1 | Gespeicherter Admin-Formwert (`public_url` in appconfig) | `entry_exapp._resolved_env`: `{**env, **overlay}`, "a stored value wins over the variable" (IN-02, Rescue-Text `entry_exapp.py:662-675`); Overlay nur mit Werten, die `config_values._public_url` ueberleben |
| 2 | Deploy-Variable `NC_MCP_PUBLIC_URL` | `config.public_url` (`config.py:343-346`) |
| 3 | **NEU:** Ableitung `<NEXTCLOUD_URL>/exapps/<APP_ID>`, validiert wie Quelle 1 | dieser Plan; nur im ExApp-Modus (braucht `APP_ID`), nur wenn 1 und 2 nach dem Merge leer sind |
| 4 | `DEFAULT_PUBLIC_URL` (Loopback) plus Fehlerzeile und Setup-State | `config.py:128`, `entry_exapp.main:563-594`, `ui/connections.py:260` |

**Einhaengepunkt:** `entry_exapp._resolved_env`, direkt nach dem Overlay-Merge. Das ist
derselbe Mechanismus, mit dem der Admin-Overlay wirkt: der abgeleitete Wert wird als
`ENV_PUBLIC_URL` in das resolved-Mapping injiziert, und JEDER Konsument
(`metadata.py:163/184`, `provider.py:263/710/1355`, `verifier.py:198`,
`consent.py:761/811/938`, `middleware.py:272`, `ui/layout.py:426/606`,
`ui/connections.py:260`, `admin_settings.py:94` doc_url, `settings_form.py:63`,
`chain.py:242` Audience) sieht ihn automatisch, ohne dass `config.public_url` oder eine
Signatur sich aendert. Ausserhalb des ExApp-Modus laeuft `_resolved_env` gar nicht bis
dahin (early return), und ohne `APP_ID` gibt es keinen Suffix: die Ableitung ist
strukturell ExApp-only. Bonus: `_warn_when_the_host_check_is_a_trap` und
`deployment_hosts` sehen den Wert ebenfalls, konsistent zum 421-Fix.

**Rescue-Pfad (IssuerRefused, `main:610-689`):** Eine GESETZTE, aber unbrauchbare
Deploy-Variable bleibt der laute Weg: Build wirft `IssuerRefused`, der Rescue droppt den
Wert; NEU faellt er danach auf die Ableitung (dasselbe Kettenglied 3) und erst dann auf
den Loopback-Default. Ein abgeleiteter Wert kann selbst kein zweites `IssuerRefused`
ausloesen, weil die https-oder-Loopback-Regel des Validierungskerns die SDK-Regel
abdeckt (CR-01-Praevention). Der Rescue-Text (IN-02-Wortlaut) nennt kuenftig DREI
Quellen mit der Regel dazwischen. Exchange-armierter Sonderfall
(`exchange_enabled`, `main:636-660`): bleibt SystemExit(2) ohne Retry, unveraendert;
die Ableitung in `_resolved_env` verbessert dort nur den No-Config-Fall (eindeutige
statt Placeholder-Audience).

**Fail-closed unveraendert (Kernfrage c):** Leitet auch Quelle 3 nichts ab (kein
`NEXTCLOUD_URL`, http auf Nicht-Loopback, Garbage), bleibt `ENV_PUBLIC_URL` leer, die
bestehende Fehlerzeile in `main` feuert (Text um die dritte Quelle ergaenzt: "und aus
NEXTCLOUD_URL liess sich keine brauchbare Adresse ableiten"), der Setup-State auf der
Connections-Seite bleibt, der Prozess dient weiter. Die bestehenden Tests dieses Zweigs
(`test_an_installation_without_any_public_address_serves_and_says_where_to_set_it` u.a.)
nutzen `NEXTCLOUD_URL=http://nc.test`, also einen nicht ableitbaren Wert: sie belegen
den Fail-closed-Weg weiter und brauchen hoechstens Assertion-Anpassungen an den
erweiterten Wortlaut.

## Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `src/mcp_connector/exapp/config_values.py` | Validierungskern aus `_public_url` extrahieren (eine Regel, zwei Log-Texte); neue Funktion `derived_public_url(env)` |
| `src/mcp_connector/entry_exapp.py` | Kettenglied 3 in `_resolved_env` und im Rescue; A2-Kommentar ersetzen; Fehlerzeile und Rescue-Text auf drei Quellen; INFO-Zeile, welche Quelle gewonnen hat |
| `src/mcp_connector/exapp/ui/strings.py` | `ADMIN_FIELD_PUBLIC_URL_DESCRIPTION`: Pflicht-Formulierung zu "leer = abgeleitet aus der Nextcloud-Adresse, setzen zum Ueberschreiben" |
| `tests/unit/test_exapp_config_values.py` | Ableitungstests (Task 1) |
| `tests/unit/test_exapp_entry.py` | Praezedenz-/Rescue-/Fail-closed-Tests (Task 2), Wortlaut-Assertions des IN-02-Tests |
| `appinfo/info.xml:489` | Variable-Description: "Required for OAuth" ersetzen durch Optional-mit-Ableitungs-Default-Satz |
| `docs/exapp-install.md` (Z. 37, 639), `docs/oauth-setup.md` (Z. 56-75, 115), `docs/faq.md` (Z. 85-90) | Kette dokumentieren, Pflicht-Option zur Override-Option |
| `CHANGELOG.md` | Eintrag unter Unreleased |

README/README.de/README.fr: Grep nach `NC_MCP_PUBLIC_URL` traf dort nichts; bei der
Ausfuehrung einmal gegenpruefen, sonst nichts zu tun. `docs/client-setup.md:174` nennt
beide Variablen fuer die Allowed Hosts: lesen, nur anfassen, wenn der Satz durch die
neue Kette falsch wuerde (vermutlich nicht, er beschreibt den Host-Fix).

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: derived_public_url in config_values, test-first</name>
  <files>src/mcp_connector/exapp/config_values.py, tests/unit/test_exapp_config_values.py</files>
  <behavior>
    Neue Tests (RED zuerst, Namen im Hausstil):
    - test_the_public_address_is_derived_from_nextcloud_url_and_the_app_id:
      NEXTCLOUD_URL=https://cloud.example.com, APP_ID=mcp_connector ->
      "https://cloud.example.com/exapps/mcp_connector" (Trailing Slash am Input egal).
    - test_the_derived_address_leaves_in_one_spelling:
      NEXTCLOUD_URL="HTTPS://Cloud.Example.COM/" -> Schema und Host lowercased
      (IN-03-Familie, Normalisierung greift auch auf abgeleitete Werte).
    - test_a_non_loopback_http_nextcloud_url_derives_nothing:
      "http://nextcloud-aio-apache" -> None (A2-Fall: AppAPI-Downgrade/interner Name,
      fail-closed; genau die RFC-8414-Regel von CR-01).
    - test_a_loopback_nextcloud_url_still_derives:
      "http://127.0.0.1:8081" -> "http://127.0.0.1:8081/exapps/mcp_connector"
      (Dev-/Staging-Fall, deckt die gemessenen oauth-setup-Laeufe).
    - test_garbage_nextcloud_url_values_derive_nothing (parametrisiert):
      leer, nur Whitespace, "not a url", "ftp://x", Credentials in der URL,
      Port ausserhalb 1-65535, unlesbare IPv6-Klammer -> jeweils None, keine Exception.
    - test_a_missing_app_id_derives_nothing: NEXTCLOUD_URL ok, APP_ID leer -> None.
    - test_the_derivation_refusal_names_the_variable_and_never_the_value:
      caplog traegt "NEXTCLOUD_URL", nie den Wert (Hausregel T-05-03 sinngemaess;
      der Wert stammt zwar aus der Deploy-Env, aber eine Regel ohne Ausnahme bleibt
      eine Regel).
  </behavior>
  <action>
    In config_values.py den Validierungskern von _public_url extrahieren: eine private
    Funktion (z.B. _validated_address(raw) -> str | None plus Rueckgabe/Reason fuer den
    Ablehnungsgrund), die Strip/rstrip("/"), config.normalize_base_url, Fragment-,
    Credential-, Host-, Port- und https-oder-LOOPBACK_HOSTS-Regel sowie _one_spelling
    buendelt. _public_url ruft den Kern und behaelt Wort fuer Wort seine
    _rejected-Warnung ("Correct it in the Nextcloud administration settings ..."),
    damit die bestehenden Log-Tests unveraendert gruen bleiben.

    Neue oeffentliche Funktion derived_public_url(env: Mapping[str, str] | None = None)
    -> str | None: liest config.ENV_NEXTCLOUD_URL und config.ENV_APP_ID direkt und
    fail-soft (kein exapp_settings, das wirft); bei fehlendem Wert None ohne Log
    (nichts zu melden). Kandidat = f"{base}/exapps/{app_id}" mit base =
    NEXTCLOUD_URL.strip().rstrip("/"). Kandidat durch den Kern; bei Ablehnung genau
    eine INFO/WARNING-Zeile, die NEXTCLOUD_URL und den Grund nennt, nie den Wert, und
    sagt, dass der bestehende Weg (Formfeld oder NC_MCP_PUBLIC_URL) offen bleibt.
    Docstring: Ableitungsform mit den Belegen (bootstrap_exapp.sh:196,
    docs/exapp-install.md, AIO nextcloud_url) und der A2-Antwort (Validierung statt
    Vertrauen). derived_public_url in __all__ aufnehmen. Keine Netzwerk-Calls: der
    bestehende Test test_only_one_place_in_this_module_reaches_the_network muss
    unveraendert gruen bleiben.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_exapp_config_values.py -x -q</automated>
  </verify>
  <done>Alle neuen Tests gruen, alle bestehenden config_values-Tests unveraendert gruen; RED-Commit vor GREEN-Commit in der Historie.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Kettenglied 3 in entry_exapp verdrahten (Ableitung, Rescue, Texte), test-first</name>
  <files>src/mcp_connector/entry_exapp.py, tests/unit/test_exapp_entry.py</files>
  <behavior>
    Neue Tests ueber den bestehenden Start-Harness des Praezedenzblocks
    (test_exapp_entry.py ab ~1098, Muster von
    test_an_admin_value_is_the_address_the_started_app_calls_itself):
    - test_the_derived_address_is_the_one_the_started_app_calls_itself:
      kein Admin-Wert, kein NC_MCP_PUBLIC_URL, NEXTCLOUD_URL=https://cloud.example.com
      -> issuer/resource der gestarteten App ist
      https://cloud.example.com/exapps/<APP_ID>; keine Setup-State-Fehlerzeile im Log.
    - test_the_deploy_variable_wins_over_the_derivation: beide gesetzt -> die Variable.
    - test_the_admin_value_wins_over_the_derivation: Formwert gesetzt -> der Formwert.
    - test_a_refused_admin_value_falls_back_to_the_derivation: gespeicherter
      Garbage-Formwert + ableitbarer NEXTCLOUD_URL -> abgeleitete Adresse in Kraft,
      die _rejected-Warnung zum Formwert steht trotzdem im Log (Kettenregel: ein
      abgelehnter Wert ist kein Wert in Kraft).
    - test_an_underivable_nextcloud_url_keeps_the_setup_state:
      NEXTCLOUD_URL=http://nc.test, sonst nichts -> Loopback-Default, Fehlerzeile
      feuert und nennt jetzt auch die dritte Quelle (Ableitung versucht und
      verworfen bzw. nicht ableitbar).
    - test_the_rescue_after_a_refused_deploy_variable_serves_the_derived_address:
      NC_MCP_PUBLIC_URL=Garbage (IssuerRefused-ausloesend) + NEXTCLOUD_URL ableitbar
      -> App dient mit der abgeleiteten Adresse, Rescue-Zeile im Log.
    - test_the_rescue_without_a_derivable_address_serves_the_documented_default:
      NC_MCP_PUBLIC_URL=Garbage + NEXTCLOUD_URL=http://nc.test -> Loopback-Default,
      wie heute.
    - test_the_rescue_line_names_all_three_sources_and_never_a_value:
      Rescue-Text nennt Formfeld, NC_MCP_PUBLIC_URL und die Ableitung aus
      NEXTCLOUD_URL mit der Praezedenzregel, nie einen Wert.
    - test_the_start_names_the_derivation_as_the_source_that_won: INFO-Zeile analog
      zur Overlay-Zeile ("these values come from ..."), Variablenname statt Wert.
  </behavior>
  <action>
    In _resolved_env nach dem Overlay-Merge, nur im ExApp-Zweig: wenn
    (resolved.get(config.ENV_PUBLIC_URL) or "").strip() leer ist, derived =
    config_values.derived_public_url(resolved); bei Treffer
    resolved[config.ENV_PUBLIC_URL] = derived plus eine INFO-Zeile, die die Quelle
    benennt (Variablennamen, nie Werte, gleiche Sprache wie die Overlay-Zeile).
    Empfehlung: kleines Helper (z.B. _fill_public_url_from_derivation(resolved) ->
    bool), damit der Rescue dieselbe Zeile Code nutzt statt einer Kopie.

    In main:
    (1) Den A2-Kommentar (Zeilen ~559-562) ersetzen: A2 benennen, die Antwort benennen
    (Ableitung existiert jetzt, aber nur durch den Validierungskern von
    config_values; ein http-Downgrade oder ein interner Name leitet nichts ab, also
    bleibt "kein stiller kaputter Default" wahr).
    (2) Setup-State-Fehlerzeile (Zeilen ~563-594): dritter Zustandssatz. Die state-
    Variable unterscheidet weiterhin "refused" vs. "nichts gespeichert"; ergaenzt wird,
    dass auch aus NEXTCLOUD_URL keine brauchbare Adresse ableitbar war (die Zeile wird
    nur noch erreicht, wenn das so ist). Wortlaut knapp halten, kein Wert im Log.
    (3) Rescue-Zweig (IssuerRefused, nicht-Exchange): nach resolved.pop(ENV_PUBLIC_URL)
    das Helper aus (1) aufrufen; der Log-Text (IN-02-Nachfolger) nennt drei Quellen und
    die Regel ("a stored value wins over the variable, the variable wins over the
    derived address") und sagt, ob dieser Start mit der abgeleiteten Adresse oder dem
    dokumentierten Default weiterdient. Der Exchange-Zweig (SystemExit) bleibt
    unveraendert. Bestehende IN-02-Assertions in test_exapp_entry.py auf den neuen
    Wortlaut heben.

    Erwartete Nebenwirkungen pruefen, nicht raten: voller Unit-Lauf; Kandidaten fuer
    Anpassung sind ausschliesslich Wortlaut-Assertions (Setup-State, Rescue). Der
    421-Test test_the_aio_custom_domain_is_served_instead_of_answering_421 ruft
    build_exapp_app direkt und ist von _resolved_env unberuehrt.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_exapp_entry.py tests/unit/test_exapp_config_values.py -x -q</automated>
  </verify>
  <done>Praezedenzkette 1>2>3>4 durch Tests belegt, Rescue faellt auf die Ableitung, Fail-closed-Zweig unveraendert erreichbar und getestet, kein Test des Repos rot.</done>
</task>

<task type="auto">
  <name>Task 3: Doku, Formfeld-Text, info.xml, CHANGELOG</name>
  <files>docs/exapp-install.md, docs/oauth-setup.md, docs/faq.md, appinfo/info.xml, src/mcp_connector/exapp/ui/strings.py, CHANGELOG.md</files>
  <action>
    Ueberall dieselbe Kette in einem Satzmuster erzaehlen (Formwert > Deploy-Variable >
    abgeleitet aus NEXTCLOUD_URL als <nextcloud-url>/exapps/mcp_connector, sofern https
    oder Loopback > dokumentierter Default). Englische Doku-Sprache, keine Backticks-
    Regelverstoesse, keine Em-Dashes:
    - docs/oauth-setup.md (Z. 56-75): NC_MCP_PUBLIC_URL von "the one value to set" zu
      "override; derived from NEXTCLOUD_URL on AIO-style deployments"; die Tabelle
      Z. 115 um die Ableitungszeile ergaenzen; benennen, wann man weiterhin setzen MUSS
      (NEXTCLOUD_URL intern/http, Split-Domain, eigener Praefix).
    - docs/exapp-install.md (Z. 37 --env-Beispiel, Z. 639): --env als Override
      kennzeichnen; der Satz zu Z. 639 ("nothing sets NC_MCP_PUBLIC_URL on that path")
      pruefen und an die Ableitung anpassen.
    - docs/faq.md (Z. 85-90): Antwort auf "Does the app need any configuration" wird
      "usually no": abgeleitet, wann ja (die drei Muss-Faelle), Verweis oauth-setup.md.
    - appinfo/info.xml:489: Description der Variable: "Required for OAuth" ersetzen
      durch Optional-Satz mit Ableitungs-Default und Override-Semantik.
    - strings.ADMIN_FIELD_PUBLIC_URL_DESCRIPTION (exapp/ui/strings.py): leeres Feld =
      abgeleiteter Default; setzen heisst ueberschreiben; der bekannte Preis
      (disable/enable) bleibt genannt. Falls ein Test den Wortlaut pinnt, mitziehen.
    - CHANGELOG.md: Unreleased-Eintrag im Stil des 421-Eintrags (Z. ~161), mit
      Verweis auf Issue #4 / jekkels Kommentar und der Fail-closed-Regel.
    - Gegenprobe mit unabhaengigem Muster: grep -rn "NC_MCP_PUBLIC_URL" ueber README*,
      docs/, appinfo/ und src/ und jede Fundstelle einmal lesen, ob sie die Option noch
      als Pflicht behauptet (docs/client-setup.md:174, docs/staging-setup.md,
      docs/conference-demo.md, docs/n8n-setup.md nur anfassen, wenn faktisch falsch).
  </action>
  <verify>
    <automated>uv run pytest tests/unit -q && grep -n "Required for OAuth" appinfo/info.xml | wc -l</automated>
  </verify>
  <done>Keine Doku-Stelle behauptet mehr eine Pflicht ohne Ableitungs-Hinweis; info.xml-Description aktualisiert; CHANGELOG-Eintrag vorhanden; Wortlaut-Tests gruen.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Beschreibung |
|----------|--------------|
| Deploy-Env -> issuer/audience | NEXTCLOUD_URL wird erstmals Quelle der OAuth-Selbstadresse |
| Admin-Form (HTTP) -> Prozess | unveraendert, bestehende T-05-03/T-05-21-Regeln |

## STRIDE-Register

| Threat ID | Kategorie | Komponente | Disposition | Mitigation |
|-----------|-----------|------------|-------------|------------|
| T-BL17-01 | Spoofing (falscher issuer) | derived_public_url | mitigate | abgeleiteter Kandidat laeuft durch denselben Validierungskern wie der Admin-Wert (https oder Loopback per RFC 8414, CR-01); NEXTCLOUD_URL stammt aus der Deploy-Env, ist nicht request-settable (dieselbe Vertrauensbasis wie deployment_hosts seit Issue #4) |
| T-BL17-02 | Tampering (stiller kaputter Default, A2) | _resolved_env | mitigate | fail-closed: unbrauchbarer Kandidat leitet nichts ab, bestehende Fehlerzeile und Setup-State bleiben; Ableitung wird im Log als Quelle benannt, nie stumm |
| T-BL17-03 | Information Disclosure (Wert im Log) | Log-Zeilen | mitigate | Variablennamen statt Werte, wie _rejected (T-05-03) |
| T-BL17-04 | Elevation (Exchange-Audience als Placeholder) | main, Exchange-Zweig | accept/unveraendert | SystemExit-Zweig von 22-REVIEW CR-01 bleibt; Ableitung verbessert dort nur den No-Config-Fall (eindeutige Audience) |

Keine neuen Pakete, kein Package-Legitimacy-Gate noetig.
</threat_model>

## Commit-Aufteilung (atomar, conventional, keine Claude-Trailer, Autor street1983nk)

1. `test(exapp): failing tests for deriving the public URL from NEXTCLOUD_URL` (Task 1 RED)
2. `feat(exapp): derive the public URL from NEXTCLOUD_URL and the app id` (Task 1 GREEN, Kern-Refactor + derived_public_url)
3. `test(exapp): pin the precedence chain and the rescue around the derived address` (Task 2 RED)
4. `feat(exapp): fill the public URL from the derivation before the documented default` (Task 2 GREEN, _resolved_env + Rescue + Texte + A2-Kommentar)
5. `docs(exapp): the public URL is derived; the explicit option is the override` (Task 3, inkl. info.xml, strings, CHANGELOG)

## Abschlussverifikation

Hausgates, alle vor dem letzten Commit lokal gruen (uv-Toolchain):

```
uv run ruff check .
uv run ruff format --check .
PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright
uv run vulture
uv run pytest tests/unit tests/contract -q
```

Dazu die Gegenprobe mit unabhaengigem Muster (nicht das Muster der Umsetzung): einmal
`grep -rn "exapps/" src/ | grep -v test` und pruefen, dass der Suffix `/exapps/<APP_ID>`
nur an der einen neuen Stelle gebaut wird (keine zweite Rechtschreibung derselben
Ableitung), sowie `grep -rn "derived" src/mcp_connector` gegen vergessene Halbverdrahtung.

## Erfolgskriterien

1. No-Config-AIO-Fall: nur NEXTCLOUD_URL=https://<domain> gesetzt -> Discovery-Dokumente,
   issuer, resource und Consent-Redirect nennen https://<domain>/exapps/<APP_ID>.
2. Override-Praezedenz durch Tests gepinnt: Formwert > Variable > Ableitung > Default.
3. Fail-closed byte-genau erhalten, Fehlertexte nennen drei Quellen (IN-02-Nachfolger).
4. Alle Hausgates gruen, Doku und info.xml widersprechen dem Code nicht mehr.

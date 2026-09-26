<!--
SPDX-FileCopyrightText: 2026 Khaled Cherif
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 20-jwks-schicht-und-pyjwt-stand
reviewed: 2026-09-19T00:00:00Z
depth: deep
diff_range: fd7199f..5ea9151
files_reviewed: 3
files_reviewed_list:
  - src/mcp_connector/oauth/jwks.py
  - src/mcp_connector/oauth/oidc.py
  - tests/unit/test_oauth_jwks.py
findings:
  critical: 2
  warning: 6
  info: 6
  total: 14
status: issues_found
fixed_at: 2026-09-19
fix_status: 11 von 14 behoben, IN-04 Kommentar korrigiert, 3 bewusst offen (IN-01, IN-04 Verhalten, IN-05, alle Phase 22)
---

# Phase 20: Code-Review-Bericht

**Geprueft:** 2026-09-19
**Tiefe:** deep (Aufrufketten ueber Modulgrenzen, plus ausgefuehrte Gegenproben)
**Dateien:** 3 Quelldateien des Bereichs fd7199f..5ea9151
**Status:** issues_found

## Zusammenfassung

Die Heraustrennung der Schluesselsatz-Schicht ist handwerklich sauber: der schnelle Pfad
ist beweisbar sperrfrei, es gibt genau ein Schloss je `KeySet` und damit je Issuer, es gibt
keinen prozessweiten Schluesselcache, in dem sich `kid`-Werte zweier Issuer treffen
koennten, das Groessenlimit greift vor `json.loads`, Weiterleitungen und `jku`/`x5u` werden
nie verfolgt, und in keiner Logzeile steht Token- oder Schluesselmaterial. Die Tests in
`tests/unit/test_oauth_jwks.py` pruefen echte Eigenschaften und laufen gruen, ruff und
pyright sind sauber.

Darunter liegen aber zwei Befunde, die die Schicht genau dort treffen, wo Phase 21/22 sie
hinstellen will. Erstens laeuft die gesamte Ablauf- und Karenzlogik in der einzigen
produktiven Instanz nicht an `time.monotonic`, sondern an `time.time`: ein Ruecksprung der
Wanduhr friert Cache-Ablauf und Karenz gleichzeitig ein. Zweitens bremst die Karenz nur den
Zweig "Cache frisch, `kid` unbekannt". Der Zweig "Cache abgelaufen oder nie gefuellt" hat
gar keine Bremse, also wird bei einem ausgefallenen Provider jede eingehende Anfrage eins
zu eins in eine ausgehende Abholung uebersetzt. Beides ist unten mit ausgefuehrten
Gegenproben belegt, nicht abgeleitet.

Dazu kommt ein inhaltlicher Widerspruch zum Nachtrag aus 20-01: dort steht, die Anhebung
auf PyJWT 2.14 raeume `GHSA-w6j9-cwv2-h6wq` (entkommende `TypeError`/`AttributeError` aus
kaputten JWK-Eintraegen) fuer diesen Code ab. Sie tut es nicht, siehe WR-01.

## Kritische Befunde

### CR-01: Die einzige produktive Instanz betreibt die Schicht an der Wanduhr

**Status 2026-09-19:** behoben in `953969b`. `OidcClient` setzt `time.monotonic` als Standarduhr und reicht sie an `KeySet` durch. Gegenprobe: `test_the_key_cache_does_not_run_on_the_wall_clock` (vorher `assert 2 == 1`).

**Datei:** `src/mcp_connector/oauth/oidc.py:163`, `src/mcp_connector/oauth/oidc.py:170`,
gegen `src/mcp_connector/oauth/jwks.py:113`

**Befund:** `KeySet` ist ausdruecklich fuer eine monotone Uhr entworfen. Die Signatur setzt
`clock: Callable[[], float] = time.monotonic` (jwks.py:113), der Kommentar bei jwks.py:124
begruendet den Startwert minus unendlich mit "unter jeder Uhr, auch einer monotonen nahe
null", und die Zusammenfassung 20-02 fuehrt den monotonen Standardwert als Entwurfsentscheid
auf. `OidcClient` setzt aber `self._clock = clock or time.time` (oidc.py:163) und reicht
genau diese Uhr an `KeySet` durch (oidc.py:170). `self._clock` wird in `oidc.py` sonst
nirgends benutzt, das Feld existiert praktisch nur, um die Schicht zu versorgen.

**Szenario (ausgefuehrt, nicht behauptet):** Cache um `t=10000` gefuellt, dann springt die
Wanduhr um 1800 Sekunden zurueck (NTP-Korrektur nach Containerstart, Wiederaufnahme aus
Suspend, Rueckspielen eines VM-Schnappschusses).

- `_stale` rechnet `now - fetched_at`, also minus 1800. Ueber 1801 Sekunden echter Zeit
  fanden null Aktualisierungen statt, wo ohne den Sprung sechs faellig gewesen waeren.
- Derselbe Sprung auf `_miss_refresh_at` (jwks.py:154): ueber 600 Sekunden echter Zeit gab
  es null Nachladungen fuer einen unbekannten `kid`, wo eine je 60 Sekunden faellig waere.

Die Wirkung ist die gefaehrliche Richtung: ein vom Provider zurueckgezogener oder
kompromittierter Schluessel bleibt ueber die Dauer des Ruecksprungs plus die Cachefrist
gueltig, und eine Rotation wird in genau demselben Fenster nicht bemerkt, weil auch die
Karenz nicht mehr ablaeuft. Ein Vorwaertssprung ist nur unschoen, ein Ruecksprung ist ein
stilles Aushebeln beider Frischekontrollen zugleich.

**Fix:** Die Uhr der Schicht von der Uhr der Tokenpruefung trennen. `OidcClient` braucht
fuer die Schluesselschicht keine einstellbare Wanduhr:

```python
def __init__(self, settings, *, clock=None, key_clock=None):
    self._clock = clock or time.time
    self._keys = KeySet(..., clock=key_clock or time.monotonic)
```

Die Tests, die heute `clock` fuer den Cache-Ablauf drehen (`tests/unit/test_oauth_oidc.py:485`),
drehen dann `key_clock`. Alternativ den Parameter in `OidcClient` ganz fallen lassen und
`KeySet` seinen eigenen Standard behalten lassen.

### CR-02: Der Fehlerpfad hat keine Bremse, jede Anfrage wird eins zu eins nach aussen gereicht

**Status 2026-09-19:** behoben in `a839300`. Ein fehlgeschlagener Versuch wird in `_attempt` gestempelt, der Ablaufzweig weist danach `JWKS_FAILURE_RETRY_SECONDS` (10) lang ohne Abruf ab. Fail-closed unverändert: die Bremse verbilligt nur Abweisungen. Gegenprobe: `test_a_failing_cold_fetch_is_not_repeated_for_every_caller` (vorher `assert 25 == 1`).

**Datei:** `src/mcp_connector/oauth/jwks.py:145-152`

**Befund:** Die Karenz (`_miss_refresh_at`) wird ausschliesslich im `elif`-Zweig
"Cache frisch, `kid` unbekannt" gesetzt und geprueft (jwks.py:153-160). Der Zweig
"Cache abgelaufen oder nie gefuellt" ruft `_attempt` ohne jede Bremse auf. Der Vergleich
`self._fetches != fetches_seen` (jwks.py:146) teilt nur das Ergebnis eines *bereits
laufenden* Fluges; wer danach ankommt, startet einen neuen. Es gibt kein negatives Caching:
ein Fehlschlag laesst `fetched_at` unberuehrt (jwks.py:206-208), der Cache bleibt also
abgelaufen, und damit faellt jede weitere Anfrage wieder in denselben Zweig.

**Szenario (ausgefuehrt):** kalter Cache, Provider antwortet 500. 25 eingehende Anfragen
erzeugten 25 ausgehende Abholungen. Jede davon baut ausserdem einen frischen
`httpx.AsyncClient` mit vollem TLS-Handschlag auf (jwks.py:223) und kann bis zu zweimal
`_TIMEOUT` dauern, weil `_jwks_uri()` intern noch die Discovery nachzieht (oidc.py:293).

Wirkung: genau dann, wenn der Identitaetsanbieter ohnehin schwaechelt, wird die Last
verstaerkt statt gedrosselt, inklusive der Aussicht, von dessen Ratelimit oder Sperrliste
erfasst zu werden und damit die Anmeldung vollstaendig zu verlieren. Heute ist der Pfad
noch dadurch eingehegt, dass `oidc_routes.py` vor `exchange()` eine einloesbare
State-Transaktion verlangt, ein Fremder kann also nicht beliebig oft ausloesen. Genau diese
Einhegung faellt weg, sobald die Schicht laut Modulkopf (jwks.py:4-6) und laut Auftrag in
Phase 21/22 im vor-authentischen Pfad steht. Der Modulkopf bewirbt die Karenz ausdruecklich
als Schutz "for a pre-authentication reachable path" (jwks.py:73-76); diesen Schutz gibt es
fuer den Fall, den ein Angreifer am leichtesten herstellt, nicht.

**Fix:** Denselben Stempel auch auf den Ablaufzweig legen, aber nur nach einem
*fehlgeschlagenen* Versuch, damit der Erfolgsfall unveraendert bleibt:

```python
if self._stale(now):
    if self._fetches != fetches_seen:
        raise self._refuse("the key set could not be refreshed")
    if now - self._failed_refresh_at < self._retry_seconds:
        raise self._refuse("the key set could not be refreshed")
    try:
        await self._attempt(now)
    except Exception:
        self._failed_refresh_at = now
        raise
```

Ein eigener, kurzer `retry_seconds`-Wert ist sinnvoll (etwa 5 bis 10 Sekunden), damit ein
kurzer Aussetzer des Providers nicht zur vollen Karenz von 60 Sekunden fuehrt.

## Warnungen

### WR-01: `_usable_key` faengt nur `jwt.PyJWTError`, PyJWT 2.14 wirft hier weiter `TypeError`

**Status 2026-09-19:** behoben in `25d6c9e`. `_usable_key` fängt zusätzlich `TypeError`, `ValueError` und `AttributeError`; der Nachtrag in `docs/dependency-audit.md` ist richtiggestellt (2.14 härtet `PyJWKClient`, nicht `PyJWK`). Gegenprobe: drei neue Fälle in `test_an_entry_that_may_not_verify_never_enters_the_cache` (vorher roher `TypeError`).

**Datei:** `src/mcp_connector/oauth/jwks.py:276-279`

**Befund:** Der Nachtrag `docs/dependency-audit.md` sagt zu `GHSA-w6j9-cwv2-h6wq`, auf 2.13
habe ein kaputter JWKS-Eintrag "eine unbehandelte Ausnahme an der Transportgrenze" erzeugt,
und fuehrt die Anhebung auf 2.14 als Abhilfe. Gegen die installierte 2.14.0 geprueft:
`jwt.PyJWK({"kty": "RSA", "n": None, "e": "AQAB", "kid": "x"})` wirft
`TypeError: Expected a string value`, ebenso bei `n` als Zahl oder Liste und bei `x` als
Zahl fuer `OKP`. `TypeError` ist kein `jwt.PyJWTError`, der `except`-Zweig bei jwks.py:278
greift also nicht. Gegenprobe ausgefuehrt: die Ausnahme verlaesst `KeySet.key()` roh statt
als die vom Aufrufer gereichte Ablehnung.

Damit ist der im Modulkopf zugesagte Vertrag gebrochen ("The layer defines no exception of
its own: every caller brings the refusal it already answers with", jwks.py:24-27). Heute
faengt `oidc_routes.py:267` noch pauschal `except Exception`, der Schaden bleibt also eine
falsche Logzeile. Der naechste Aufrufer aus Phase 21 muss dieselbe Pauschale mitbringen,
sonst wird aus einer Ablehnung eine 500 mit Traceback.

**Fix:**

```python
    try:
        key = jwt.PyJWK(entry).key
    except (jwt.PyJWTError, TypeError, ValueError, AttributeError):
        return None
```

Dazu ein Test mit `{"kty": "RSA", "n": None, "e": "AQAB", "kid": KID}` in der bestehenden
Parametrisierung bei `tests/unit/test_oauth_jwks.py:235`, und die Behauptung im Nachtrag
richtigstellen: die 2.14 haerten `PyJWKClient`, nicht `PyJWK` gegen jede Eingabeform.

### WR-02: Eine 200-Antwort mit leerem Schluesselsatz loescht einen funktionierenden Cache

**Status 2026-09-19:** behoben in `23a69b8`. Ein Satz ohne brauchbaren Schluessel wird vor der Zuweisung abgewiesen, der alte Cache bleibt stehen. Gegenprobe: `test_a_200_without_a_usable_key_leaves_the_cache_standing` (vorher wurde der vorher funktionierende `kid` abgelehnt).

**Datei:** `src/mcp_connector/oauth/jwks.py:196-208`

**Befund:** `not isinstance(entries, list) or len(entries) > MAX_KEYS` laesst `[]` durch,
und auch eine Liste, aus der `_usable_key` jeden Eintrag verwirft, endet bei `keys = {}`.
Zeile 208 ersetzt den Cache dann bedingungslos und setzt `fetched_at = now`. Gegenprobe
ausgefuehrt: erster Abruf liefert einen brauchbaren Schluessel, das Nachladen wegen eines
unbekannten `kid` faengt `{"keys": []}` ein, danach wird der vorher funktionierende `kid`
abgelehnt.

Das widerspricht genau der Eigenschaft, die
`test_a_failed_reload_leaves_the_cache_standing` (Zeile 213) beweist: eine 500 laesst den
Cache stehen, eine 200 mit leerem Satz raeumt ihn ab. Ein Provider, der waehrend eines
rollenden Neustarts kurz eine leere JWKS ausliefert, legt damit alle Anmeldungen lahm, und
wegen der Karenz heilt das in Schritten von 60 Sekunden statt sofort. Nebenwirkung:
`_stale` ist fuer den leeren Cache `False`, also verlaesst danach jede Anfrage den schnellen
Pfad und nimmt das Schloss.

**Fix:** Einen Satz ohne brauchbaren Schluessel wie einen fehlgeschlagenen Abruf behandeln,
also vor Zeile 208:

```python
        if not keys:
            raise self._refuse("the JWKS carries no usable key")
```

Damit bleibt der alte Cache stehen, weil der Fehler vor der Zuweisung greift.

### WR-03: `_fetches` wird je Versuch zweimal erhoeht, gegen die eigene Zusage

**Status 2026-09-19:** behoben in `ffc28dc`. Die Erhoehung in `_refresh` ist gestrichen, `_attempt` zaehlt als einzige Stelle; `test_twenty_concurrent_calls_cost_one_fetch_and_share_the_key` nagelt den Wert fest. Gegenprobe: `assert keys._fetches == 1` scheiterte vorher mit `assert 2 == 1`.

**Datei:** `src/mcp_connector/oauth/jwks.py:192` gegen `src/mcp_connector/oauth/jwks.py:166-178`

**Befund:** `_attempt` erhoeht den Zaehler auf beiden Auswegen (Zeilen 176 und 178) und
begruendet das ausdruecklich damit, der Zaehler duerfe sich erst bewegen, wenn ein Versuch
*abgeschlossen* ist. `_refresh` erhoeht ihn aber schon als allererste Anweisung
(Zeile 192). Gegenprobe ausgefuehrt: nach genau einem erfolgreichen Abruf steht
`_fetches` auf 2, die Route wurde einmal aufgerufen.

Verhalten bricht das heute nicht, weil beide Pfade gleich viel zaehlen und ein Wartender
den Wert ohnehin nur auf Ungleichheit prueft. Es ist aber genau der Zaehler, auf dem die
Entscheidung "teile die Ablehnung, starte keinen zweiten Flug" ruht (Zeile 146), die
Zeile 192 macht die dokumentierte Invariante falsch, und kein Test haelt den Wert fest.
Wer spaeter eine der beiden Stellen aufraeumt, verschiebt die Semantik lautlos.

**Fix:** Zeile 192 streichen, `_attempt` bleibt die einzige Stelle, die zaehlt. Dazu eine
Zusicherung im Test, die den Zaehler festnagelt, etwa nach
`test_twenty_concurrent_calls_cost_one_fetch_and_share_the_key`:
`assert keys._fetches == 1`.

### WR-04: `hmac.compare_digest` auf `str` wirft bei nicht-ASCII einen `TypeError`

**Status 2026-09-19:** behoben in `5237180`. Beide Seiten werden vor `hmac.compare_digest` nach UTF-8 kodiert. Gegenprobe: neuer Fall "non-ascii nonce" in `test_a_token_that_breaks_a_rule_is_refused` (vorher roher `TypeError`).

**Datei:** `src/mcp_connector/oauth/oidc.py:274`

**Befund:** `hmac.compare_digest(token_nonce, nonce)` bekommt zwei `str`. Fuer `str`
unterstuetzt die Funktion nur ASCII und wirft sonst
`TypeError: comparing strings with non-ASCII characters is not supported` (gegengeprueft).
`token_nonce` stammt aus den Claims eines fremden Tokens. Signaturgeprueft ist es zwar,
aber ein Angreifer, der beim Provider selbst eine Autorisierung mit eigenem `nonce` startet
und den Code an unseren Callback reicht, bestimmt dessen Inhalt. Ergebnis: eine rohe
Ausnahme statt `OidcRefused`, heute nur durch das pauschale `except Exception` in
`oidc_routes.py:267` aufgefangen.

Die Zeile ist aelter als diese Phase, steht aber in einer geaenderten Datei und im gleichen
heissen Pfad, den Phase 21 erweitert.

**Fix:** Vor dem Vergleich in Bytes wandeln, dann gilt die Konstantzeit ohne Sonderfall:

```python
    if not isinstance(token_nonce, str) or not hmac.compare_digest(
        token_nonce.encode("utf-8"), nonce.encode("utf-8")
    ):
        raise _refused("the ID token carries another nonce")
```

### WR-05: Die Karenz wird erst hinter dem Schloss geprueft, nicht davor

**Status 2026-09-19:** behoben in `f134d9a`. Karenz und Fehlschlagpause werden vor dem Schloss geprüft und hinter dem Schloss unverändert erneut; der sperrfrei gemessene Erfolgspfad ist unangetastet. Gegenprobe: `test_an_unknown_kid_inside_the_cooldown_does_not_queue_behind_a_fetch` (vorher hängt der zweite Aufruf bis `wait_for` ihn nach einer Sekunde abbricht).

**Datei:** `src/mcp_connector/oauth/jwks.py:140-156`

**Befund:** Der schnelle Pfad (Zeile 136) greift nur fuer einen *bekannten* `kid`. Jede
Anfrage mit unbekanntem `kid` nimmt das Schloss, auch wenn schon feststeht, dass sie in der
Karenz nur abgelehnt wird (Zeile 154). Damit serialisiert eine Flut erfundener `kid`-Werte
vollstaendig auf einem `asyncio.Lock`, dessen Warteschlange unbegrenzt waechst, und zwar
genau in dem Moment, in dem ein laufender Flug das Schloss haelt. Ein Flug kann lange
dauern: `_refresh` zieht ueber `_jwks_uri()` erst die Discovery nach (oidc.py:293) und holt
dann die JWKS, also bis zu zweimal `_TIMEOUT`, in Summe rund 30 Sekunden, waehrend derer
jede weitere Anfrage mit unbekanntem oder abgelaufenem Schluessel haengt.

**Fix:** Den billigen Teil der Entscheidung vor das Schloss ziehen, das Ergebnis hinter dem
Schloss unveraendert erneut pruefen (die Doppelpruefung ist ohnehin schon da):

```python
        if not self._stale(now) and now - self._miss_refresh_at < self._cooldown_seconds:
            raise self._refuse("the token names an unknown or unusable key")
```

### WR-06: `metadata()` hat weder Single-Flight noch negatives Caching

**Status 2026-09-19:** behoben in `8cfec98`. `metadata()` hat jetzt sperrfreien Schnellpfad, eigenes `asyncio.Lock` mit Doppelprüfung und dieselbe Fehlschlagpause wie die Schicht darunter; die Prüfung ist nach `_discover` gewandert. Gegenprobe: `test_concurrent_callers_cost_one_discovery_and_share_it` und `test_a_failed_discovery_is_not_repeated_for_every_caller` (beide vorher `assert 10 == 1`).

**Datei:** `src/mcp_connector/oauth/oidc.py:177-205`

**Befund:** `metadata()` prueft `self._metadata is not None` und holt sonst. Es gibt kein
Schloss, also holen gleichzeitige Aufrufer je einzeln, und es gibt keinen Merker fuer einen
Fehlschlag, also holt nach jedem Fehler jeder neue Aufrufer erneut. Das ist dieselbe Klasse
wie CR-02, nur eine Ebene hoeher, und es untergraebt das Single-Flight der Schicht
teilweise: `exchange()` ruft `metadata()` ausserhalb jedes Schlosses (oidc.py:229, 239),
`KeySet` ruft es ueber `_jwks_uri()` innerhalb seines Schlosses. Der Hinweis
"validated once and then reused for the life of the process" im Docstring gilt nur fuer den
Erfolgsfall.

**Fix:** Ein eigenes `asyncio.Lock` in `OidcClient`, im Schloss erneut auf
`self._metadata is not None` pruefen, und einen kurzen Sperrzeitraum nach einem Fehlschlag
fuehren, analog zum Vorschlag in CR-02.

## Info

### IN-01: `same_origin` normalisiert den Standardport nicht

**Status 2026-09-19:** bewusst offen, Zuordnung Phase 22. Portnormalisierung und Hostnamen mit abschließendem Punkt sind eine Änderung am Vergleichsverhalten der Origin-Prüfung; der heutige Stand ist fail-closed, also keine Lücke. Owner-Entscheid dieses Laufs: Architektur- und Betriebsverhalten nicht im Audit-Fix anfassen.

**Datei:** `src/mcp_connector/oauth/jwks.py:283-285`

`_origin` vergleicht `parts.netloc.lower()` roh. Gegengeprueft:
`same_origin("https://auth.example.com:443/keys", "https://auth.example.com")` ist `False`.
Ein Discovery-Dokument, das den Standardport ausschreibt (bei einigen Providern mit
Reverse-Proxy durchaus ueblich), wird also abgelehnt. Das ist fail-closed und damit keine
Luecke, aber eine Betriebsfalle, deren Ursache aus der Logzeile
"a discovery endpoint leaves the issuer origin" nicht hervorgeht. Auch der abschliessende
Punkt im Hostnamen (`auth.example.com.`) faellt darunter. Empfehlung: Port 443 fuer `https`
vor dem Vergleich streichen, oder die Strenge im Docstring benennen.

### IN-02: Die Begruendung fuer `aclosing` stimmt nicht

**Status 2026-09-19:** behoben in `f1bba5e`. Die Gegenüberstellung zu `try/finally` ist gestrichen, der Verweis auf GHSA-fhv5-28vv-h8m8 bleibt. Reine Kommentarkorrektur, daher ohne Test.

**Datei:** `src/mcp_connector/oauth/jwks.py:235-239`

Der Kommentar sagt, hier stehe `aclosing` "instead of try/finally", weil in diesem Modul
nichts laufen duerfe, was "on the way out, whatever happened" ausgefuehrt wird. `aclosing`
ist selbst nichts anderes als ein `try/finally` um `aclose()`. Der ersetzte Code
(`finally: await response.aclose()`) verhielt sich identisch. Die Begruendung ist damit
irrefuehrend an einer Stelle, an der spaetere Leser eine Sicherheitsaussage vermuten.
Empfehlung: den Verweis auf GHSA-fhv5-28vv-h8m8 behalten, die Gegenueberstellung streichen.

### IN-03: Der Standardwert von `_KeyCache.fetched_at` widerspricht der Absicht

**Status 2026-09-19:** behoben in `f1bba5e`. `_KeyCache.fetched_at` steht auf `float("-inf")`. Kein Verhaltenswechsel (niemand baut ein argumentloses `_KeyCache`), daher ohne neuen Test.

**Datei:** `src/mcp_connector/oauth/jwks.py:94`

`fetched_at: float = 0.0`, waehrend `KeySet.__init__` (Zeile 126) eigens minus unendlich
setzt und das ausfuehrlich begruendet. Ein `_KeyCache()` ohne Argumente gilt unter einer
monotonen Uhr in den ersten 300 Sekunden Prozesslaufzeit als frisch und leer. Heute baut
niemand so eines, aber der Standardwert ist eine Falle direkt neben ihrer eigenen
Gegenmassnahme. Empfehlung: `fetched_at: float = float("-inf")`.

### IN-04: Abgelaufener Cache plus unbekannter `kid` kostet zwei Abholungen, nicht eine

**Status 2026-09-19:** teilweise behoben in `995105a` (die falsche Zusage im Kommentar ist korrigiert: die Obergrenze sind zwei Abholungen, nicht eine). Das Verhalten selbst bleibt bewusst offen: der Miss-Zweig zusätzlich auf ein gerade gesetztes `fetched_at` pruefen zu lassen, verkürzt das Fenster, in dem ein wirklich neuer Schluessel bemerkt wird. Diese Abwägung gehört in die Rotationsarbeit von Phase 22, nicht in einen Audit-Fix.

**Datei:** `src/mcp_connector/oauth/jwks.py:69`, `src/mcp_connector/oauth/jwks.py:145-160`

Der Kommentar bei Zeile 69 sagt "An unknown `kid` triggers at most one refetch". Gemessen:
bei abgelaufenem Cache holt der erste Aufrufer wegen des Ablaufs, der zweite holt direkt
danach noch einmal, weil der Ablaufzweig `_miss_refresh_at` bewusst nicht stempelt und die
Karenz daher noch auf minus unendlich steht. Zwei Abholungen, dann bremst die Karenz. Das
ist begrenzt und nicht gefaehrlich, aber es ist eine mehr als zugesagt. Wenn CR-02
umgesetzt wird, laesst sich das gleich mit erledigen, indem der Miss-Zweig zusaetzlich
prueft, ob `fetched_at` gerade erst gesetzt wurde.

### IN-05: Je Abruf ein neuer `httpx.AsyncClient`

**Status 2026-09-19:** bewusst offen, Zuordnung Phase 22. Ein `httpx.AsyncClient` je `KeySet` beziehungsweise je `OidcClient` braucht eine Lebenszeit und ein Schließen am Anwendungsrand, also eine Architekturänderung. Owner-Entscheid dieses Laufs: nicht im Audit-Fix. Der Kostenfaktor ist durch CR-02 außerdem deutlich kleiner geworden, weil ein ausgefallener Provider nicht mehr je Anfrage einen TLS-Handschlag kostet.

**Datei:** `src/mcp_connector/oauth/jwks.py:223-228`

Die Trennung der Verbindungspools vom Nextcloud-Pfad (T-06-14) ist richtig und im Modulkopf
gut begruendet, sie verlangt aber nur einen *eigenen* Client, nicht einen *neuen je
Anfrage*. Im Normalbetrieb faellt das nicht auf (ein Abruf je 300 Sekunden), im Zusammenspiel
mit CR-02 bezahlt jeder Wiederholungsversuch einen vollen TLS-Handschlag. Empfehlung: einen
Client je `KeySet` beziehungsweise je `OidcClient` anlegen und mit dessen Lebenszeit
schliessen.

### IN-06: `JWKS_CACHE_SECONDS` und `MAX_RESPONSE_BYTES` werden nur fuer die Tests weiterexportiert

**Status 2026-09-19:** behoben in `f1bba5e`. Die Weiterexporte in `oauth/oidc.py` sind gestrichen, die Tests nennen `jwks.JWKS_CACHE_SECONDS` und `jwks.MAX_RESPONSE_BYTES`.

**Datei:** `src/mcp_connector/oauth/oidc.py:41-42`, `src/mcp_connector/oauth/oidc.py:50-51`

Beide Namen werden in `oidc.py` nirgends benutzt, sondern nur importiert und in `__all__`
weitergereicht. Die einzigen Verwender sind `tests/unit/test_oauth_oidc.py:252` und
`:485`. Damit hat jede Konstante zwei Adressen, was genau die Doppelung ist, gegen die die
Herausloesung angetreten ist. Empfehlung: die Tests auf `jwks.JWKS_CACHE_SECONDS` und
`jwks.MAX_RESPONSE_BYTES` umstellen und die Weiterexporte streichen.

## Was ausdruecklich in Ordnung ist

Gegengeprueft und bestaetigt, damit die Punkte nicht erneut geprueft werden muessen:

- **Der schnelle Pfad ist sperrfrei.** Waehrend ein Nachladen fuer einen unbekannten `kid`
  laeuft und das Schloss haelt, wird eine gleichzeitige Anfrage mit bekanntem `kid` aus dem
  frischen Cache sofort beantwortet (ausgefuehrt: die Anfrage mit Treffer schliesst vor der
  mit Fehlschlag ab). Zwischen jwks.py:136 und 138 liegt kein `await`, der Cache kann also
  nicht unter der Pruefung ausgetauscht werden.
- **Ein Schloss je `KeySet`, also je Issuer** (jwks.py:131), angelegt im Konstruktor und
  nicht bei erster Benutzung. Kein prozessweiter Cache, also auch keine `kid`-Kollision
  zwischen zwei Issuern bei mehrfacher Instanziierung.
- **Der Lock wird auf keinem Ausnahmepfad gehalten**, weil `async with` ihn loest und
  `_attempt` die Ausnahme durchreicht, statt sie zu schlucken.
- **Das Groessenlimit greift vor dem Parsen**: `stream=True`, Statuspruefung, dann
  `bounded_response` mit Abbruch innerhalb der Chunk-Schleife, erst danach `json.loads`
  (jwks.py:239-249).
- **Fail-closed bei Ablauf**: ein abgelaufener Cache wird nie ersatzweise ausgeliefert, auch
  wenn der `kid` darin stand (durch `test_an_expired_cache_never_serves_a_kid_when_the_reload_fails`
  festgehalten).
- **Keine Log-Leaks**: `_refused` loggt nur feste Phrasen, der einzige eingesetzte Fremdwert
  ist ein HTTP-Statuscode (jwks.py:242). Weder Token, noch `kid`, noch Schluesselmaterial,
  noch die URL erreichen das Log. `OidcSettings.__repr__` maskiert das Client-Secret.
- **Gegen `kid`-Kollision und gegen symmetrische Schluessel** ist die Schicht dicht, und die
  Ablehnung ist fuer "unbekannt" und "kollidiert" wortgleich, also ohne Orakel.
- **PyJWT-Stand**: `pyjwt[crypto]>=2.14,<3` in `pyproject.toml`, `uv.lock` auf 2.14.0. Die
  Anhebung selbst liegt in fd7199f, also unmittelbar vor dem geprueften Bereich.
  `jwt.get_unverified_header` ist auf 2.14 gegen leere, nicht-objektartige, tief
  verschachtelte und base64-kaputte Token gepruefte `PyJWTError`-Quelle, dort entkommt
  nichts.
- **Werkzeuge**: ruff sauber, pyright null Befunde, `tests/unit/test_oauth_jwks.py` und
  `tests/unit/test_oauth_oidc.py` vollstaendig gruen (100 Tests).

## Nachtrag 2026-09-19: Audit-Fixes

Alle Befunde sind einzeln abgearbeitet, jeder Fix in einem eigenen Commit mit
Regressionstest. Die Gegenprobe (Test vor dem Fix rot) steht bei jedem Befund oben und in
der Commit-Nachricht. Gates je Commit grün: `ruff check`, `ruff format --check`,
`pyright` (0 Fehler), `vulture`, volle `pytest`-Suite.

| Befund | Status | Commit |
|--------|--------|--------|
| CR-01 | behoben | `953969b` |
| CR-02 | behoben | `a839300` |
| WR-01 | behoben | `25d6c9e` |
| WR-02 | behoben | `23a69b8` |
| WR-03 | behoben | `ffc28dc` |
| WR-04 | behoben | `5237180` |
| WR-05 | behoben | `f134d9a` |
| WR-06 | behoben | `8cfec98` |
| IN-01 | bewusst offen (Phase 22) | entfaellt |
| IN-02 | behoben | `f1bba5e` |
| IN-03 | behoben | `f1bba5e` |
| IN-04 | Kommentar behoben, Verhalten bewusst offen (Phase 22) | `995105a` |
| IN-05 | bewusst offen (Phase 22) | entfaellt |
| IN-06 | behoben | `f1bba5e` |

Zwei bestehende Tests wurden angepasst, beide ohne Verlust der Eigenschaft, die sie
halten: `test_an_expired_cache_never_serves_a_kid_when_the_reload_fails` dreht die Uhr
jetzt über die neue Fehlschlagpause, und `tests/unit/test_oauth_oidc.py` nennt die
Konstanten der Schicht statt der Weiterexporte (IN-06). Der sha256-Anker auf
`tests/unit/test_oauth_oidc.py` aus dem Phase-20-Umzugsbeweis ist damit eingelöst und
abgelöst.

Kein Vorgriff auf Phase 21/22: kein `ExchangeVerifier`, keine Throttle-Änderung, keine
neue Konfigurationsfläche, kein neues Fremdpaket. `JWKS_FAILURE_RETRY_SECONDS` ist eine
Modulkonstante mit Konstruktorhaken, genau wie `cooldown_seconds` es schon war.

---

_Geprüft: 2026-09-19_
_Pruefer: Claude (gsd-code-reviewer)_
_Tiefe: deep_

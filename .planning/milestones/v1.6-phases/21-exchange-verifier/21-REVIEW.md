---
phase: 21-exchange-verifier
reviewed: 2026-09-19T00:00:00Z
depth: deep
files_reviewed: 2
files_reviewed_list:
  - src/mcp_connector/oauth/exchange.py
  - tests/unit/test_oauth_exchange.py
findings:
  critical: 2
  warning: 11
  info: 5
  total: 18
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-09-19
**Depth:** deep (Quergriff auf `oauth/jwks.py`, `oauth/oidc.py`, `oauth/principal.py` und den installierten PyJWT 2.14.0)
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Der Prüfkern ist in den klassischen JWS-Fallen sauber: `alg` wird vor jeder anderen Arbeit gegen die konfigurierte Liste entschieden, die Liste selbst ist per `ALLOWED_ALGORITHMS` auf asymmetrische Verfahren eingeschränkt, `none` und `HS256` fallen messbar vor jedem Schlüsselzugriff, der Issuer-Vorfilter läuft auf dem ungeprüften Payload und kann tatsächlich nur ablehnen (der Decoder prüft `iss` danach signaturgedeckt ein zweites Mal), der Audience-Vergleich ist exakt statt präfixbasiert, und ein Dutzend absichtlich kaputter Tokenformen (zwei Segmente, JWE-Form, kaputtes Base64, Nicht-UTF-8-Payload, `b64: false`, 100 kB `kid`, Payload als Array) endet ausnahmslos in `ExchangeRefused`.

Der Kern der Befunde liegt woanders: die zentrale Zusage des Moduls, dass **jede** Eingabe in genau einer detailfreien Ausnahme endet, hält nicht. Drei Ausnahmeklassen entkommen `claims_of`, eine davon vollständig vor jeder Authentisierung und mit einem rund 8 kB grossen, ungezeichneten Token. Dazu kommt ein Validierer in `ExchangeSettings`, der `nan` und `inf` durchlässt und damit sämtliche Zeitgrenzen lautlos ausschaltet: ein seit 27 Stunden abgelaufenes Token wird damit angenommen, gemessen und nicht vermutet.

Alle Behauptungen unten sind am installierten PyJWT-Quelltext gelesen oder per ausgeführter Gegenprobe gegen das echte Modul belegt. Die 85 Tests der Phase laufen grün; keiner der gefundenen Fälle steht im Negativkorpus.

## Status der Behebung (2026-09-19)

Alle achtzehn Befunde sind abgearbeitet: fünfzehn behoben, drei mit Begründung eingeordnet.
Jeder Fix hat einen Regressionstest, der vor dem Fix rot war; die Gegenprobe steht je Befund
unten am Eintrag. Die Phasengrenze hielt dabei: `git diff --name-only edb0f0e..HEAD` nennt
`src/mcp_connector/oauth/exchange.py`, `tests/unit/test_oauth_exchange.py` und
`vulture_whitelist.py`, unter `src/` genau eine Datei. `verifier.py`, `oidc.py`, `jwks.py` und
`throttle.py` sind unberührt, und es ist keine Konfigurationsfläche und kein Env-Zugriff
hinzugekommen: die neue Grenze ist ein Konstruktorparameter mit Default, nach dem Muster von
`jwks.py`.

| Befund | Status | Commit |
|--------|--------|--------|
| CR-01 | behoben | `bfa777a` |
| CR-02 | behoben | `ca02bf9` |
| WR-01 | behoben | `b0e6ead` |
| WR-02 | behoben | `bfa777a` |
| WR-03 | behoben | `e17810e` |
| WR-04 | behoben | `bc7e9b5` |
| WR-05 | behoben | `4531200` |
| WR-06 | behoben | `12e0389` |
| WR-07 | behoben | `ca02bf9` |
| WR-08 | behoben | `2dfca3d` |
| WR-09 | eingeordnet (kein Fix) | `291793b` |
| WR-10 | eingeordnet (keine Beschneidung) | `291793b` |
| WR-11 | eingeordnet (bekannte Grenze) | `291793b` |
| IN-01 | behoben | `3faa18e` |
| IN-02 | behoben | `4531200` |
| IN-03 | eingeordnet | `291793b` |
| IN-04 | mittelbar behoben | `bfa777a` |
| IN-05 | behoben | `be459fa` |

**Offen fuer spätere Phasen, aus diesen Befunden:**

- Phase 22: die Drossel deckelt die Abtastrate der Laufzeitklassen aus WR-09; `MAX_TOKEN_BYTES`
  steht als Konstruktorparameter bereit und braucht dort keine zweite Erfindung.
- Phase 23: die `sub`-Abbildung entscheidet WR-11 (ein gewöhnliches client_credentials-Token
  derselben erlaubten Partei ist hier nicht unterscheidbar) und IN-03 (Unicode-Normalform von
  `sub`). WR-10 liefert dazu die ehrliche Schnittstellenzusage: geprüft sind genau sieben
  Claims, der Rest ist Transport.
- Phase 24: AUDIT-07 bringt die Betreiber-Sichtbarkeit abgewiesener Versuche, die WR-08 aus dem
  Log genommen hat.

Gates nach dem letzten Commit: `ruff check`, `ruff format --check`, `pyright` (0 errors,
0 warnings), `vulture` und die volle Suite (3747 Tests, davon 133 in
`tests/unit/test_oauth_exchange.py`, vorher 85) sind grün, in zufälliger und in fester
Reihenfolge.

## Critical Issues

### CR-01: Ein ungezeichnetes Token von rund 8 kB verlässt `claims_of` als `RecursionError`, vor jeder Authentisierung

**Status (2026-09-19):** **behoben** in `bfa777a` - Bytes-Obergrenze `MAX_TOKEN_BYTES` (8192, Konstruktorparameter mit Default, keine Env-Konfiguration) vor dem ersten Base64-Schritt, dazu beide ungeprüften Parse-Schritte fail-closed nach Klasse statt nach Fehlerliste. Gegenprobe vor dem Fix: `test_a_deeply_nested_payload_is_a_refusal_never_a_recursion_error` endete mit `RecursionError: maximum recursion depth exceeded while decoding a JSON array`.

**File:** `src/mcp_connector/oauth/exchange.py:275-278` (mittelbar auch `283-297`)

**Issue:** Der Vorfilter dekodiert den kompletten Payload ungeprüft: `jwt.decode(token, options={"verify_signature": False})`. PyJWT fängt an dieser Stelle nur `ValueError` ab. Gemessen an `.venv/Lib/site-packages/jwt/api_jwt.py:297-300`:

```python
try:
    payload: dict[str, Any] = json.loads(decoded["payload"])
except ValueError as e:
    raise DecodeError(f"Invalid payload string: {e}") from e
```

Bezeichnenderweise fängt dieselbe Bibliothek beim **Header** zusätzlich `RecursionError` ab (`api_jws.py:358-361`), beim Payload nicht. `json.loads` wirft bei tief verschachteltem JSON `RecursionError`, und das ist weder `ValueError` noch `PyJWTError`, also greift `except jwt.PyJWTError` in Zeile 277 nicht.

Gegenprobe gegen das echte Modul (Fake-KeySet, damit kein Netz nötig ist; erreicht wird die Stelle ohnehin vor jedem Schlüsselzugriff):

```
deep(2998) token bytes: 8070 -> *** ESCAPED RecursionError
```

Der Angreifer braucht dafür keinen Schlüssel, keine Signatur und keine Kenntnis des Audience-Werts: Header `{"alg":"RS256","kid":"k1","typ":"JWT"}`, Payload `{"iss":` + 2998 mal `[` + 2998 mal `]` + `}`, Signatursegment `AAAA`. Die minimale Verschachtelungstiefe ist mit 2998 gemessen und hängt nicht von der bereits belegten Python-Stapeltiefe ab (geprüft mit 0, 100, 300 und 600 zusätzlichen Rahmen: immer 2998), das Token bleibt also verlässlich bei rund 8,1 kB und passt damit unter die Vorgabe von h11/uvicorn für einen Header-Block.

Konsequenzen in dem Pfad, in den Phase 22 das einbaut: erstens ist es genau das Orakel, das der Moduldocstring ausschliessen will, denn ein Aufrufer, der `ExchangeRefused` in 401 übersetzt und alles andere durchfallen lässt, antwortet hier mit 500. Zweitens ist es eine billige Vorauthentisierungs-Last (eine HTTP-Anfrage je Stapelerschöpfung). Drittens bricht es die im Docstring von `jwks.py` gezogene Linie, dass fremde Eingaben nur begrenzt gelesen werden.

Beachtenswert: der OIDC-Pfad (`oauth/oidc.py:277-297`) hat diese Lücke **nicht**, weil er den Payload nicht ungeprüft vordekodiert. Die Lücke ist mit dem Kostenfilter dieser Phase neu entstanden.

**Fix:** Ein Längenwächter allein genügt nicht sauber (8070 Byte liegen unter einer 8-kB-Grenze); nötig ist beides, eine harte Grenze **und** das Fangen der Nicht-PyJWT-Ausnahmen:

```python
#: Ein Keycloak-Access-Token liegt bei ein bis drei Kilobyte. Alles darüber ist
#: kein Token dieses Pfades, und die Grenze steht vor dem ersten Base64-Schritt.
MAX_TOKEN_BYTES = 4096

...
        if not token:
            raise _refused("the token is empty")
        if len(token) > MAX_TOKEN_BYTES:
            raise _refused("the token is longer than allowed")
        ...
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except (jwt.PyJWTError, RecursionError):
            raise _refused("the token payload is unreadable") from None
```

Dazu ein Korpusfall mit genau diesem Token, damit das Orakel-Gate die Klasse künftig abdeckt.

### CR-02: `leeway_seconds` und `max_lifetime_seconds` nehmen `nan` und `inf` an und schalten damit jede Zeitgrenze ab

**Status (2026-09-19):** **behoben** in `ca02bf9` - `_require_positive_seconds` prüft `math.isfinite` und Vorzeichen fuer `leeway_seconds` und `max_lifetime_seconds`. Gegenprobe vor dem Fix: vier Parametrisierungen (`nan`/`inf` je Feld) und `test_a_time_that_is_not_a_finite_number_never_reaches_the_hot_path` waren rot, `nan` kam durch die Konstruktion.

**File:** `src/mcp_connector/oauth/exchange.py:158-161`

**Issue:** Die Prüfung lautet `if self.leeway_seconds <= 0: raise ValueError(...)` beziehungsweise dasselbe für `max_lifetime_seconds`. Für `float("nan")` ist jeder Vergleich falsch, also fällt der Wert durch die Prüfung hindurch. Danach ist er wirkungslos im Sinne von "prüft nichts mehr": PyJWT rechnet `exp <= (now - leeway)`, und mit `leeway = nan` ist das immer falsch; dasselbe gilt für `nbf` und `iat`. Die beiden eigenen Regeln in Zeile 328 und 330 vergleichen gegen `nan` und sind damit ebenfalls immer falsch.

Gegenprobe:

```
2) leeway nan                     -> ACCEPTED nan
2) leeway inf                     -> ACCEPTED inf
2) max_lifetime nan               -> ACCEPTED nan
2) max_lifetime inf               -> ACCEPTED inf
4) token expired 27 hours ago with nan leeway -> ACCEPTED s1
```

Das ist kein theoretischer Wert: Phase 22 liest diese Felder aus Konfiguration, und `float("nan")` wie `float("inf")` entstehen aus den Zeichenketten `"nan"`, `"NaN"`, `"inf"`, `"Infinity"` ohne jede Fehlermeldung. Der Klassendocstring verspricht genau das Gegenteil ("jede Verletzung ist ein `ValueError` beim Bauen, nie ein stilles Vorgabeverhalten"). Ein `inf` in der Lebensdauer ist als Absicht noch lesbar, ein `nan` in der Karenz schaltet die Ablaufprüfung komplett ab, ohne dass irgendwo etwas auffällt.

**Fix:** Endlichkeit mitprüfen, in einer Hilfsfunktion, damit es nicht an zwei Stellen auseinanderläuft:

```python
import math

def _positive_seconds(value: float, name: str) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number of seconds")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number of seconds")
```

und im `__post_init__` beide Felder darüber führen. Dazu je ein Settings-Test mit `nan` und `inf` in der bestehenden Parametrisierung ab Zeile 124 der Testdatei.

## Warnings

### WR-01: `iat`, `nbf` oder `exp` als Objekt, Liste oder `Infinity` verlassen `claims_of` als `TypeError` beziehungsweise `OverflowError`

**Status (2026-09-19):** **behoben** in `b0e6ead` - der signaturprüfende Decode fängt zusaetzlich `TypeError` und `OverflowError`; der falsche Kommentar nennt jetzt, was den eigenen `_number`-Wächter wirklich erreicht (numerische Zeichenkette und `bool`). Gegenprobe vor dem Fix: acht von neun Parametrisierungen rot (`dict`, `list`, `Infinity` je Zeitclaim), nur `NaN` war schon gedeckt.

**File:** `src/mcp_connector/oauth/exchange.py:283-297` und `320-324`

**Issue:** PyJWT rechnet in `_validate_iat`, `_validate_nbf` und `_validate_exp` jeweils `int(payload[...])` und fängt dabei ausschliesslich `ValueError` (gemessen an `api_jwt.py:469-512`). Für einen `dict`- oder `list`-Wert wirft `int()` einen `TypeError`, für `Infinity` einen `OverflowError`; beides ist kein `PyJWTError`, also greift Zeile 296 nicht. Dass Python `json.loads` das Nicht-Standard-Literal `Infinity` überhaupt annimmt, ist mitgemessen (`json.loads('{"exp": Infinity}') -> {'exp': inf}`).

Gegenprobe mit gültig signierten Tokens:

```
iat as dict: *** ESCAPED TypeError: int() argument must be a string, a bytes-like object or a real number, not 'dict'
iat as list: *** ESCAPED TypeError
nbf as dict: *** ESCAPED TypeError
exp as dict: *** ESCAPED TypeError
exp = Infinity: *** ESCAPED OverflowError: cannot convert float infinity to integer
iat = Infinity: *** ESCAPED OverflowError
nbf = Infinity: *** ESCAPED OverflowError
```

Damit ist der Kommentar in Zeile 323 sachlich falsch: "Eine nicht-numerische Zeit ist eine Ablehnung, nie ein `TypeError` aus der Arithmetik". Der Wächter `_number` in Zeile 320 bis 324 wird für genau die Formen, gegen die er geschrieben ist (`dict`, `list`, `inf`), nie erreicht, weil PyJWT vorher abstürzt. Erreichbar bleibt er nur für Zeichenketten und `bool`, und dafür gibt es den Test in Zeile 470 der Testdatei. Die Auslösung setzt eine gültige Signatur des konfigurierten Issuers voraus, deshalb Warning und nicht Critical; die Wirkung ist dieselbe 500-gegen-401-Unterscheidung wie in CR-01.

**Fix:** Die eigene Typprüfung vor den Decoder ziehen (sie hat dort ohnehin ihren Platz, siehe WR-03) oder die Klammer erweitern:

```python
        except (jwt.PyJWTError, TypeError, OverflowError):
            raise _refused("the token did not meet the standard claims") from None
```

Sauberer ist die erste Variante: `iat`, `exp` und `nbf` aus dem bereits vorliegenden `unverified` über `_number` prüfen, bevor `jwt.decode` sie zu sehen bekommt, und den Kommentar in Zeile 323 an die Wirklichkeit anpassen.

### WR-02: Keine Längengrenze, bevor das Token zweimal vollständig dekodiert wird

**Status (2026-09-19):** **behoben** in `bfa777a`, zusammen mit CR-01 - `MAX_TOKEN_BYTES` steht in `__all__`, damit Phase 22 die Grenze nicht ein zweites Mal erfindet. Gegenprobe vor dem Fix: `test_an_oversized_token_is_refused_although_every_claim_would_hold` und `test_a_token_beyond_the_byte_limit_falls_before_the_first_decoding` waren rot.

**File:** `src/mcp_connector/oauth/exchange.py:247-297`

**Issue:** `claims_of` prüft nur `if not token`. Danach laufen Base64-Dekodierung und JSON-Parsen über beliebig grosse, angreiferbestimmte Eingaben, und für ein Token mit passendem `iss` gleich zweimal. Gemessen:

```
1 MB payload, matching iss: refused  (175.4 ms)
8 MB payload, matching iss: refused  (1542.0 ms)
8 MB payload, foreign iss:  refused  (1202.4 ms)
```

Anderthalb Sekunden CPU je Anfrage in einem Single-Process-Async-Server, ohne Authentisierung, sind ein Lastverstärker. Der Moduldocstring von `jwks.py` zieht für jede fremde Antwort ausdrücklich eine Grenze (`MAX_RESPONSE_BYTES`); für die fremde Eingabe, die pro Anfrage ankommt, gibt es keine. Dass ein Transport davor vielleicht eine Header-Grenze setzt, zählt hier nicht: das Modul beschreibt sich selbst als freistehend und liest nichts aus der Umgebung, also darf es sich auf keine ungenannte Grenze eines noch nicht existierenden Aufrufers stützen.

**Fix:** `MAX_TOKEN_BYTES` wie unter CR-01, als erste Anweisung nach der Leerprüfung, und als Konstante in `__all__`, damit Phase 22 sie nicht ein zweites Mal erfindet.

### WR-03: Der Payload wird zweimal dekodiert und zweimal geparst

**Status (2026-09-19):** **behoben** in `e17810e` - `_PreparsedJWT` überschreibt `_decode_payload`, den von PyJWT dokumentierten Hook, und reicht das Ergebnis des Vorfilters weiter. Die Reihenfolge bleibt unangetastet: `decode` prüft die Signatur, bevor es den Payload anfordert. Gegenprobe vor dem Fix: der Parse-Zähler des neuen Tests stand auf `[1, 1]` statt `[1]`.

**File:** `src/mcp_connector/oauth/exchange.py:276` und `283`

**Issue:** Zeile 276 dekodiert Base64 und parst JSON des gesamten Payloads, Zeile 283 tut für dasselbe Segment beides erneut. Für den Normalfall, also ein gültiges Token, ist das dauerhaft doppelte Arbeit in dem Pfad, der jede Anfrage trägt, und für den Angriffsfall verdoppelt es die Kosten aus WR-02 (gemessen 175 ms gegen 125 ms bei 1 MB, 1542 ms gegen 1202 ms bei 8 MB; die Differenz ist genau der zweite Durchlauf). Es ist zugleich die zweite Angriffsfläche derselben Art, siehe CR-01.

**Fix:** Mit einer Längengrenze ist der Schaden begrenzt und die Doppelung vertretbar. Wer sie ganz loswerden will, liest den Issuer aus dem einen bereits geparsten `unverified` und lässt danach `jwt.decode` laufen, was unvermeidbar ein zweites Mal parst; alternativ das Vorfilter-Parsen auf das Nötige beschränken und in einem Kommentar festhalten, dass die Doppelung der Preis des Kostenfilters ist. Wichtig ist, dass die Entscheidung im Code steht statt unbemerkt zu passieren.

### WR-04: `REQUIRED_CLAIMS` ist eine veränderliche, exportierte Liste und zugleich die Regel, die PyJWT ausführt

**Status (2026-09-19):** **behoben** in `bc7e9b5` - `REQUIRED_CLAIMS` ist ein `Final[tuple[str, ...]]`, der Export bleibt, der Decoder bekommt eine eigene Kopie. Gegenprobe vor dem Fix: beide Tests rot (Inhaltsvergleich gegen das Tupel und `isinstance(..., tuple)`).

**File:** `src/mcp_connector/oauth/exchange.py:97`, benutzt in `294`

**Issue:** `REQUIRED_CLAIMS = ["iss", "sub", "aud", "exp", "iat", "typ", "azp"]` steht in `__all__` und wird als `options={"require": REQUIRED_CLAIMS}` direkt in den Decoder gereicht. Jede Stelle im Prozess, die `exchange.REQUIRED_CLAIMS.remove("azp")` ausführt, schwächt ab diesem Moment jeden vorhandenen und jeden künftigen Checker, ohne dass eine Konstruktion oder eine Konfiguration berührt würde. Alle anderen Regelkonstanten des Moduls sind unveränderlich (`frozenset`, `tuple`), diese eine nicht. Der Test in Zeile 501 der Testdatei prüft nur den Inhalt, nicht die Unveränderlichkeit.

**Fix:**

```python
REQUIRED_CLAIMS: Final[tuple[str, ...]] = ("iss", "sub", "aud", "exp", "iat", "typ", "azp")
...
                options={"require": list(REQUIRED_CLAIMS), "verify_aud": False},
```

Der Test in Zeile 501 vergleicht dann gegen das Tupel.

### WR-05: `audience_holds` hält bei leerer Erwartung, entgegen der Regel, die sein eigener Docstring zitiert

**Status (2026-09-19):** **behoben** in `4531200` - leere Erwartung und leerer Claim halten nie mehr. Gegenprobe vor dem Fix: `audience_holds` mit zwei leeren Zeichenketten lieferte `True`.

**File:** `src/mcp_connector/oauth/exchange.py:164-203`, konkret `190-191`

**Issue:** Gegenprobe:

```
audience_holds('', '')   -> True
audience_holds([''], '') -> True
```

Der Docstring in Zeile 170 beruft sich ausdrücklich auf `principal.same_principal` als Form des Vergleichs. Genau diese Funktion lehnt den leeren Wert **vor** dem Vergleich ab (`principal.py:96-98`: "Ein leerer Wert scheitert vor dem Vergleich, damit eine Anfrage ohne Identität nie als Eigentümerin einer Zeile durchgeht, die auch keine hat, fail closed, D-37"). `audience_holds` übernimmt die Form, aber nicht die Regel. Heute rettet der Wächter in Zeile 148, dass `settings.audience` nie leer ist; die Funktion steht aber in `__all__`, liegt vierzig Zeilen vom Wächter entfernt und ist damit die Art Lücke, die ein späterer Aufrufer aufreisst.

**Fix:**

```python
    if not expected:
        return False
    if isinstance(claim, str):
        return hmac.compare_digest(...)
```

plus zwei Fälle in der Parametrisierung ab Zeile 522 der Testdatei.

### WR-06: `azp_allowed` als blosse Zeichenkette wird als Allowlist einzelner Zeichen angenommen

**Status (2026-09-19):** **behoben** in `12e0389` - `_require_string_sequence` verlangt eine Sequenz nicht-leerer Strings und lehnt eine blanke Zeichenkette bei der Konstruktion ab, fuer `azp_allowed` und `algorithms`. Gegenprobe vor dem Fix: eine blanke Zeichenkette als Allowlist warf gar nichts.

**File:** `src/mcp_connector/oauth/exchange.py:150-153`

**Issue:** Die Prüfung iteriert über `self.azp_allowed`. Eine Zeichenkette ist iterierbar, jedes Zeichen ist ein nicht-leerer `str`, also hält die Prüfung. Gegenprobe:

```
2) azp_allowed as a bare string   -> ACCEPTED 'f13-orchestrator'
```

Die Folge ist eine Allowlist aus den Einzelzeichen `f`, `1`, `3`, `-`, `o` und so weiter. Praktisch lehnt das jedes echte Token ab, ist also nicht fail-open, aber es ist ein lautloser Konfigurationsfehler, der erst in Phase 22 als "nichts geht mehr" auffällt; und eine Keycloak-Client-Id aus einem einzigen Zeichen würde tatsächlich passen. Dieselbe Lücke gibt es beim `audience`-Feld nicht, dort steht ein ausdrückliches `isinstance(self.audience, str)`.

**Fix:**

```python
        if isinstance(self.azp_allowed, str) or not isinstance(self.azp_allowed, tuple):
            raise ValueError("azp_allowed is a tuple of client ids, not a single string")
```

vor die bestehende Inhaltsprüfung, plus einen Fall in der Settings-Parametrisierung.

### WR-07: Nicht-String-Konfiguration endet als `AttributeError` oder `TypeError`, nicht als `ValueError`

**Status (2026-09-19):** **behoben** in `ca02bf9`, zusammen mit CR-02 - `_require_text` fuer `issuer`, `jwks_uri`, `jwks_origin`, `audience` und `typ_expected`, jedes Feld wird getypt bevor es gelesen wird. Gegenprobe vor dem Fix: `typ_expected` als Zahl (`AttributeError`) und `jwks_uri = None` (`TypeError`) waren rot.

**File:** `src/mcp_connector/oauth/exchange.py:144` und `156-157`

**Issue:** Der Klassendocstring (Zeile 119 bis 122) verspricht, dass jede Verletzung beim Bauen ein `ValueError` ist. Gegenprobe:

```
2) typ_expected as int -> *** AttributeError: 'int' object has no attribute 'strip'
2) jwks_uri None       -> *** TypeError: argument of type 'NoneType' is not iterable
2) issuer None         -> ValueError (issuer must be an https URL)
```

`issuer` ist abgedeckt, weil `urlsplit` intern greift; `jwks_uri` fällt über das `"#" in url` in `same_origin` und `typ_expected` über `.strip()`. Für Phase 22, die diese Felder aus Konfiguration füllt, heisst das: ein Konfigurationsfehler kommt je nach Feld als sprechender `ValueError` oder als roher `AttributeError` an.

**Fix:** `isinstance(..., str)` für `jwks_uri` und `typ_expected` analog zur `audience`-Prüfung in Zeile 148, oder eine gemeinsame kleine Hilfsfunktion `_require_text(value, name)` für alle vier Zeichenkettenfelder.

### WR-08: Jede abgelehnte Anfrage schreibt eine WARNING-Zeile, vor der Authentisierung und im Takt des Angreifers

**Status (2026-09-19):** **behoben** in `2dfca3d` - Routineablehnungen gehen auf DEBUG; der Docstring der Ablehnungsfabrik hält fest, dass die Betreiber-Sichtbarkeit abgewiesener Versuche mit AUDIT-07 in Phase 24 kommt und ein Loglevel kein Ersatz dafuer ist. Nebenbefund beim Fix: das Leak-Gate sammelte über `caplog`, während `nextcloud.http.configure_logging` `propagate = False` auf den Paket-Logger setzt; das Gate sammelt jetzt am Logger selbst und hängt nicht mehr an der Reihenfolge der Suite.

**File:** `src/mcp_connector/oauth/exchange.py:110-112`

**Issue:** `_refused` loggt bedingungslos auf WARNING, und `claims_of` ruft es auf jedem Ablehnungspfad auf. In dem Pfad, den Phase 22 baut, bestimmt ein Fremder damit direkt die Anzahl der WARNING-Zeilen: eine HTTP-Anfrage, eine Zeile. Das Logging ist synchron, also kostet es Ereignisschleifenzeit, und der Plattenverbrauch ist unbegrenzt. Die Inhalte sind sauber (das caplog-Gate in Zeile 795 der Testdatei belegt, dass weder Token noch Claim-Werte auftauchen), das Problem ist allein die Menge.

**Fix:** Vor Phase 22 entscheiden und im Docstring festhalten: entweder die Routineablehnungen auf DEBUG und nur die Schlüsselsatz-Probleme auf WARNING, oder eine Zählerstruktur mit periodischer Zusammenfassung. Die Testzeile 802 ("mindestens eine Warnung je Fall") muss dann mitgezogen werden.

### WR-09: Die Ablehnung ist als Objekt ununterscheidbar, über die Laufzeit aber nicht

**Status (2026-09-19):** **eingeordnet, kein Fix in dieser Phase** (`291793b`) - grobe Kostenklassen sind einem gestaffelten Prüfer inhärent, und die Staffelung ist der Grund, warum die billigen Klassen der Normalfall sind. Der Moduldocstring grenzt die Zusage jetzt auf das Ausnahmeobjekt ein (Typ, Text, Argumente) und benennt den Laufzeitunterschied samt Vorfilter als bewusst hingenommen; was er verrät (unser Issuer, ein oeffentlicher `kid`) ist nicht geheim, und die Abtastrate deckelt die Drossel aus Phase 22.

**File:** `src/mcp_connector/oauth/exchange.py:239-335`, Test `tests/unit/test_oauth_exchange.py:765-788`

**Issue:** Der Orakel-Test prüft `type(exc)`, `str(exc)` und `exc.args` und ist damit ein Beweis über das Ausnahmeobjekt, nicht über das beobachtbare Verhalten. Gemessene Mediane über 40 Läufe, Schlüssel aus einem Fake-KeySet, also ohne Netzanteil:

```
alg not configured   0.037 ms
foreign issuer       0.103 ms
wrong signature      0.194 ms
wrong azp            0.252 ms
id token typ         0.257 ms
wrong audience       0.290 ms
accepted             0.208 ms
```

Drei grobe Klassen sind klar getrennt: vor dem Payload-Parsen, vor der Signaturprüfung und nach ihr. Der Vorfilter in Zeile 279 ist dabei der deutlichste Marker, er trennt "unser Issuer" von "fremder Issuer" um den Faktor zwei bis drei. Mit einem echten `KeySet` kommt ein vierter Fall dazu, der sich um Grössenordnungen unterscheidet: ein unbekannter `kid` bei kaltem Zwischenspeicher zieht eine ausgehende Abfrage nach sich, ein bekannter nicht. Der Moduldocstring formuliert die Zusage absolut ("Ein Aufrufer, der eine falsche Signatur von einer falschen Audience unterscheiden kann, hat ein Orakel in die Hand bekommen"), und genau diese beiden Fälle liegen hier rund 100 Mikrosekunden auseinander.

Sicherheitlich ist das begrenzt: der Issuer ist keine geheime Information und der `kid` steht öffentlich im JWKS. Der Befund ist trotzdem einzutragen, weil die Zusage im Docstring weiter reicht als der Beweis im Test.

**Fix:** Kein Umbau des Prüfkerns; die Reihenfolge ist aus Kostengründen richtig so. Zu tun ist eine ehrliche Formulierung: den Absatz ab Zeile 21 auf "ununterscheidbar in Typ, Text und Argumenten" eingrenzen und den Laufzeitunterschied als bewusst in Kauf genommen benennen, mit dem Vorfilter als namentlich genanntem Grund.

### WR-10: `claims_of` gibt den vollständigen Claim-Satz zurück, obwohl nur sieben Claims geprüft sind

**Status (2026-09-19):** **eingeordnet, keine Beschneidung** (`291793b`) - Phase 23 braucht den Claim, den sie auf ein Konto abbildet, und der muss nicht unter den sieben geprüften stehen. Der Docstring von `claims_of` nennt jetzt genau die geprüften Claims und sagt vom Rest, dass er Transport ist; dieser Satz gehoert in die Anforderung von Phase 23.

**File:** `src/mcp_connector/oauth/exchange.py:335`, Docstring `240`

**Issue:** Der Rückgabewert ist das rohe `claims`-Dictionary des Decoders. Geprüft sind `iss`, `aud`, `azp`, `typ`, `iat`, `exp`, `sub` und, falls vorhanden, `nbf`. Alles andere, etwa `email`, `preferred_username`, `groups`, `realm_access`, geht ungeprüft durch, und der Docstring nennt das Ergebnis "der geprüfte Claim-Satz von `token`". Phase 23 macht daraus ein Nextcloud-Konto; die Testdatei baut mit `CANARY_EMAIL` und `CANARY_USERNAME` bereits genau die Claims, die dort verlockend sind.

**Fix:** Entweder den Rückgabewert auf die geprüften Claims eingrenzen (eine kleine `frozen dataclass` mit `sub`, `azp`, `aud`, `iat`, `exp` wäre die ehrlichste Schnittstelle für Phase 23), oder den Docstring auf "der Claim-Satz eines Tokens, dessen Signatur und Pflichtclaims geprüft sind; jeder weitere Claim ist ungeprüft" ändern und den Satz in die Anforderung von Phase 23 übernehmen.

### WR-11: Nichts unterscheidet ein getauschtes Token von einem gewöhnlichen client_credentials-Token derselben erlaubten Partei

**Status (2026-09-19):** **eingeordnet, bekannte Grenze** (`291793b`) - Keycloak V2 schreibt kein `act`, also ist ein gewöhnliches client_credentials-Token derselben erlaubten Partei mit den Regeln dieses Moduls nicht vom Tauschergebnis zu trennen. Die Annahme steht als eigener Absatz im Moduldocstring; die Entscheidung (eigene Regel, Scope oder niedergeschriebene Annahme) ist ein Punkt fuer die Planung von Phase 23, zusammen mit der `sub`-Abbildung.

**File:** `src/mcp_connector/oauth/exchange.py:300-314`

**Issue:** Der Kommentar hält richtig fest, dass Keycloak Standard Token Exchange V2 kein `act` schreibt und `azp` deshalb die einzige Spur der handelnden Partei ist. Die Folge steht nicht da: ein Token, das derselbe erlaubte Client über den gewöhnlichen client_credentials-Grant holt, trägt dieselben `iss`, `azp` und, bei passendem Mapping, dieselbe `aud` sowie `typ: Bearer`. Es ist mit den Regeln dieses Moduls nicht vom Tauschergebnis zu trennen. Sein `sub` ist die Service-Account-Id des Clients, also ein Wert, den der Client selbst bestimmt; Phase 23 bildet `sub` auf ein Konto ab. Wer den Client besitzt, kann damit eine Identität behaupten, ohne je getauscht zu haben.

**Fix:** Vor Phase 23 entscheiden und dokumentieren. Mindestens: die Annahme als Absatz in den Moduldocstring ("wer die Zugangsdaten einer erlaubten Partei besitzt, kann jedes `sub` ihres Realms behaupten, das die Kontoabbildung akzeptiert"). Besser: eine Regel ergänzen, die nur der Tauschpfad erfüllt, etwa das Ablehnen von Tokens, deren `sub` mit `service-account-` beginnt, sobald der F13-Wortlaut das bestätigt, oder ein vereinbarter Scope. Die Entscheidung gehört in Phase 22 oder 23, der Befund gehört jetzt notiert.

## Info

### IN-01: `hmac.compare_digest` hier, `secrets.compare_digest` im restlichen Repository

**Status (2026-09-19):** **behoben** in `3faa18e` - `secrets.compare_digest` wie im übrigen Repository, das Import-Gate des Moduls prüft es mit.

**File:** `src/mcp_connector/oauth/exchange.py:32`, `191`, `201`, `311`

Beide Namen zeigen auf dieselbe Funktion, aber `oauth/principal.py:98` und die übrigen Vergleichsstellen benutzen `secrets`. Ein einheitlicher Import macht das repoweite Suchen nach Vergleichsstellen zuverlässig.

### IN-02: Zwei Behauptungen im Docstring von `audience_holds` sind ungenauer als der Code

**Status (2026-09-19):** **behoben** in `4531200`, zusammen mit WR-05 - `same_principal` wird als Regel benannt statt als Implementierung, und die Konstantzeit-Aussage gilt ausdrücklich innerhalb einer Liste von Strings.

**File:** `src/mcp_connector/oauth/exchange.py:170-171` und `196-203`

Erstens wird `principal.same_principal` als Form des Vergleichs genannt, ohne benutzt zu werden und ohne die Leerregel zu übernehmen (siehe WR-05). Zweitens ist "weder ein Treffer noch ein vergifteter Eintrag ändert, wie lange der Gang dauert" nur innerhalb einer festen Listenform wahr: für Nicht-String-Einträge entfällt der `compare_digest`-Aufruf, die Dauer hängt also von der Zusammensetzung ab. Beides ist sicherheitlich folgenlos, weil die Liste erst nach der Signaturprüfung gelesen wird; die Sätze sollten trotzdem stimmen.

### IN-03: `sub` wird ohne Unicode-Normalisierung und ohne Längengrenze weitergereicht

**Status (2026-09-19):** **eingeordnet** (`291793b`) - die Normalform von `sub` ist eine Entscheidung der Kontoabbildung in Phase 23; der Kommentar an der Stelle sagt das und nennt `MAX_TOKEN_BYTES` als die Längengrenze, unter der `sub` seit CR-01 mittelbar steht.

**File:** `src/mcp_connector/oauth/exchange.py:332-334`

Geprüft werden `str`, nicht leer und kein Rand-Weissraum. Gegenprobe: `sub = "aléx"` (NFD) wird angenommen und unverändert zurückgegeben; `"alex"` in NFC wäre ein anderer Wert mit derselben Darstellung. Für Phase 23, die daraus ein Konto macht, ist die Normalform eine Entscheidung, die dort getroffen werden muss. Gleiches gilt für die Länge: ein `sub` von 100 kB ist durch nichts in diesem Modul ausgeschlossen, sobald CR-01 eine Tokengrenze setzt allerdings mittelbar schon.

### IN-04: Keine Grenze für die Länge der `aud`-Liste oder die Anzahl der Claims

**Status (2026-09-19):** **mittelbar behoben** durch `MAX_TOKEN_BYTES` in `bfa777a` - die `aud`-Liste und die Anzahl der Claims stehen unter derselben Grenze wie das Token; im Kommentar an der `sub`-Prüfung festgehalten.

**File:** `src/mcp_connector/oauth/exchange.py:192-203`

`audience_holds` läuft ohne frühen Abbruch über jeden Eintrag. Die Listenlänge bestimmt der Aussteller, also greift die Regel erst nach der Signaturprüfung; mit einer Tokengrenze aus CR-01 ist sie mittelbar begrenzt. Ohne diese Grenze ist sie es nicht.

### IN-05: Der Negativkorpus enthält keinen Fall, der eine Ausnahme ausserhalb von `ExchangeRefused` provozieren soll

**Status (2026-09-19):** **behoben** in `be459fa` - der Negativkorpus hat vier strukturell kaputte Fälle bekommen (tiefe Verschachtelung, Übergröße, `iat` als Objekt, `exp: Infinity`); Orakel-Beweis und Leak-Gate laufen über dieselbe Liste und decken sie mit ab.

**File:** `tests/unit/test_oauth_exchange.py:702-745`

Alle zwölf Fälle sind wohlgeformte Tokens mit einer falschen Regel. Keiner ist strukturell kaputt, überdimensioniert oder tief verschachtelt, und keiner setzt einen Zeit-Claim auf eine nicht-numerische Form ausser der bereits abgedeckten Zeichenkette. Genau deshalb laufen alle 85 Tests grün, während CR-01 und WR-01 offen stehen. Beim Beheben gehören mindestens vier Fälle dazu: tiefe Verschachtelung, Übergrösse, `iat` als Objekt und `exp: Infinity`; der Orakel-Test in Zeile 765 fängt sie dann automatisch mit ab, weil er über denselben Korpus läuft.

---

_Reviewed: 2026-09-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

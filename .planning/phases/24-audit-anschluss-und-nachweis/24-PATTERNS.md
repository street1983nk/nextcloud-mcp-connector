# Phase 24: Audit-Anschluss und Nachweis - Pattern Map

**Mapped:** 2026-09-23
**Files analyzed:** 22 (5 neu in `src/`, 9 geändert in `src/`, 6 Tests, 2 Doku)
**Analogs found:** 21 / 22

Quelle der Dateiliste: `24-RESEARCH.md` (Entscheidungen D1 bis D4, Pitfalls 1 bis 10, BL-21/IN-04, BL-21/IN-05, Doku-Bausteine EXCH-08). Es gibt keine CONTEXT.md für diese Phase.

Jeder Auszug unten ist aus der genannten Datei gelesen worden, nicht aus einem Suchtreffer geraten. Zeilennummern stehen zum Stand 2026-09-23.

---

## File Classification

| Neue/geaenderte Datei | Rolle | Datenfluss | Nächster Analog | Match |
|-----------------------|-------|------------|------------------|-------|
| `src/mcp_connector/oauth/exchange_dryrun.py` (neu) | service, reine Funktionen | transform (Eingabe -> Schrittliste) | `src/mcp_connector/oauth/exchange.py` (`ExchangeTokenChecker.claims_of`, 337-480) | exact |
| `src/mcp_connector/exapp/exchange_check.py` (neu) | controller (occ-Route) | request-response | `src/mcp_connector/exapp/audit_verify.py` (ganze Datei) | exact |
| `src/mcp_connector/audit/refusals.py` (neu, optional) | service (Schreibweg) | event-driven, gebremst | `src/mcp_connector/audit/record.py` (`note_switch`, 272-293) | role-match |
| `src/mcp_connector/audit/store.py` (geändert) | model / Schema | CRUD (append-only) | sich selbst: `CHAIN_INSTANCE`/`USER_CHAIN_PREFIX` 171-199, `KIND_*` 202-212, `_SILENT_CHAINS` 397-399 | exact (Selbstanalog) |
| `src/mcp_connector/audit/record.py` (geändert) | service | event-driven | `note` 208-269 (dieselbe Funktion, ein Feld mehr) | exact |
| `src/mcp_connector/deps.py` (geändert) | model (`Caller`) | transform | `Caller` 121-146 + `resolve_caller` 148-191 | exact |
| `src/mcp_connector/exapp/audit_read.py` (geändert) | controller (Ausgabe) | request-response | `_line` 273-295 und `_document` 358-390 derselben Datei | exact |
| `src/mcp_connector/exapp/occ.py` (geändert) | config (Registrierung) | request-response | dritter Scheme-Eintrag 236-280 | exact |
| `src/mcp_connector/oauth/chain.py` (geändert) | middleware (Verifier-Kette) | request-response | `build_chain` 601-636 (Parameter `accounts` als Vorbild) | exact |
| `src/mcp_connector/oauth/exchange.py` (geändert) | service (Prüfer) | transform | `ExchangeRefused` 139-144 + `_refused` 147-162 | exact |
| `src/mcp_connector/oauth/exchange_accounts.py` (geändert) | Doku/Docstring | - | `EXCHANGE_CLIENT_ID` 27-34 | exact |
| `src/mcp_connector/errors.py` (geändert) | config (Konstanten) | - | `REASONS` 14-34 | exact |
| `src/mcp_connector/oauth/jwks.py` (geändert) | Doku/Docstring | - | `forget` 196-211 | exact |
| `src/mcp_connector/entry_exapp.py` (geändert) | config (Verdrahtung) | - | 130-183 (accounts + recorder), 319-321 (Routenliste) | exact |
| `src/mcp_connector/entry_oauth.py` (geändert) | config (Verdrahtung) | - | Zeile 276 (`build_chain`) | exact |
| `tests/contract/test_no_claim_leak.py` (neu) | test (Quelltext-Gate) | batch | `tests/contract/test_no_destructive_calls.py` (1-20, 295-349) | exact |
| `tests/unit/test_oauth_exchange_dryrun.py` (neu) | test | transform | `tests/unit/test_oauth_exchange.py` | role-match |
| `tests/unit/test_exapp_exchange_check.py` (neu) | test | request-response | `tests/unit/test_exapp_audit_verify.py` | exact |
| `tests/unit/test_exapp_entry.py` (geändert, IN-04) | test | request-response | `tests/unit/test_oauth_exchange_chain.py:1171-1202` | exact |
| `tests/unit/test_oauth_jwks.py` (geändert, IN-05) | test (Messung) | batch | `respx`-Muster mit `keys.call_count`, siehe `test_oauth_exchange_chain.py:1183,1198` | role-match |
| `docs/token-exchange.md` (neu) | doc | - | `docs/standalone-oauth.md` | role-match |
| `docs/exchange-evidence.md` (neu) | doc (Messnachweis) | - | `docs/spike-dav.md` (1-10, 91-139) | exact |

**Ohne Analog:** 1 Datei, siehe Abschnitt "No Analog Found".

---

## Pattern Assignments

### `src/mcp_connector/audit/store.py` (model, CRUD) - D1 und D2

**Analog:** sich selbst. Diese Datei besitzt das Schema; jede Änderung kopiert das Muster, das sie für Kettenarten und Zeilenarten schon trägt.

**Muster für eine neue Kettenart** (Zeilen 171-199, die zwei bestehenden Arten):

```python
#: The chain of instance events: the switch of D-15, and the markers for user chains that
#: are gone (a marker for a removed chain has nobody left to attach to in that chain).
CHAIN_INSTANCE = "i:instance"

#: The prefix of a user chain, named because two functions below have to agree on it: one
#: builds an identifier out of an account and the other reads the account back out of it.
USER_CHAIN_PREFIX = "u:"


def user_chain(nc_user: str) -> str:
    """The chain identifier of one account. Prefixed, so it can never collide with
    :data:`CHAIN_INSTANCE` however an account is named."""
    return f"{USER_CHAIN_PREFIX}{nc_user}"
```

Die neue `x:`-Kette wird exakt so eingeführt: eine Konstante mit `#:`-Kommentar, der sagt **warum** sie nicht `i:instance` ist (sie muss gefegt werden, sonst Pitfall 2).

**Muster für einen neuen `kind`** (Zeilen 202-212) - eine Konstante plus ein Satz, keine Migration:

```python
# --- kinds of a row ----------------------------------------------------------------------

#: One tool call, the ordinary row (D-05: one row after the call, not a pair around it).
KIND_CALL = "call"

#: A row that explains a gap: rows that gave way to the upper bound, or a whole chain that
#: went with its account (D-10, D-12). It carries the count and the end of what it replaces.
KIND_TOMBSTONE = "tombstone"

#: The log being switched on or off, which is itself logged (D-15).
KIND_SWITCH = "switch"
```

**Die Grenze, die nicht verschoben wird** (Zeilen 282-303). Der Plan darf diesen Block nicht anfassen:

```python
#: The field order of the canonical form, decided once and unchangeable afterwards: every
#: column except the two hashes, ``seq`` first.
CANONICAL_FIELDS: tuple[str, ...] = (
    "seq", "chain", "kind", "at", "actor", "nc_user", "tool", "client_id",
    "auth_id", "client_name", "outcome", "reason", "duration_ms", "params",
    "removed", "gap_chain", "gap_hash",
)
```

`actor` steht an Position 5 und ist bei jeder `call`-Zeile heute `None`. Das ist D1 Option A.

**Reinigungsmuster, das auf `actor` auszuweiten ist** (Zeilen 532-576). Heute läuft nur `client_name` durch `_clean_client_name`:

```python
def _clean_client_name(value: str | None) -> str | None:
    """The registered name of a client, made safe to print and bounded in length.
    ...
    """
    if value is None:
        return None
    return printable(value, limit=CLIENT_NAME_LIMIT) or None


def _row_values(seq: int, entry: Entry) -> tuple[Any, ...]:
    return (
        seq, entry.chain, entry.kind, entry.at,
        entry.actor,                              # <- ungereinigt, D1 Feinheit 2
        entry.nc_user, entry.tool, entry.client_id, entry.auth_id,
        _clean_client_name(entry.client_name),    # <- die Regel, die auf actor gehoert
        entry.outcome, entry.reason, entry.duration_ms,
        json.dumps(sorted(entry.params), separators=(",", ":"), ensure_ascii=False),
        entry.removed, entry.gap_chain, entry.gap_hash,
    )
```

**Sweep-Muster, das die neue Kette automatisch erfasst** (Zeilen 340, 365-375). `chain <> ?` mit `CHAIN_INSTANCE` in allen fünf Anweisungen: eine `x:`-Kette fällt dadurch ohne jede Änderung unter Verfall und Größengrenze.

```python
_SWEEPABLE_TOTAL = "SELECT COUNT(*) FROM entries WHERE chain <> ?"
_OLDEST_ROWS = "SELECT seq, chain, hash FROM entries WHERE chain <> ? ORDER BY seq LIMIT ?"
_DROP_OLDEST = "DELETE FROM entries WHERE chain <> ? AND seq <= ?"
```

**Die eine Stelle, die dabei bricht** (Zeilen 390-399, Pitfall 5). `_SILENT_CHAINS` liefert jede Kette außer der Instanz-Kette, `_account_of` schneidet nur `u:` ab:

```python
_SILENT_CHAINS = (
    "SELECT chain FROM entries WHERE chain <> ? GROUP BY chain HAVING MAX(at) <= ? ORDER BY chain"
)
```

Der Fix ist ein Präfixfilter (`AND chain LIKE 'u:%'`), und der Kommentarblock darüber erklärt bereits, warum nach `chain` und nicht nach `nc_user` gruppiert wird - dieser Satz bleibt stehen und bekommt einen zweiten daneben.

---

### `src/mcp_connector/audit/record.py` (service, event-driven) - D1 und D2

**Analog:** dieselbe Datei, zwei Funktionen.

**Wo die handelnde Partei hinkommt** (Zeilen 236-253):

```python
audit_store = await recorder.store_provider()
seq = await audit_store.append(
    Entry(
        chain=user_chain(caller.nc_user),
        kind=KIND_CALL,
        at=int(time.time()),
        actor=None,                                             # <- D1: hier der azp
        nc_user=caller.nc_user,
        tool=tool,
        client_id=caller.client_id,
        auth_id=caller.auth_id,
        client_name=_clamped_client_name(caller.client_name),
        outcome=outcome,
        reason=_known_reason(reason),
        duration_ms=round(duration_s * _MILLISECONDS),
        params=set_parameter_names(ctx, tool),
    )
)
```

**Das Muster für eine Zeile außerhalb des Tool-Pfads** (Zeilen 272-293). Der Ablehnungsschreiber kopiert genau diese Form: kein `ctx`, ein expliziter `moment`, eine `Entry` mit den Feldern, die diese Zeilenart hat, und ein Docstring, der die Wahl von `actor` begründet.

```python
async def note_switch(audit_store: AuditStore, *, enabled: bool, moment: int) -> None:
    """Write the switching of the log itself into the chain of instance events (D-15).

    ``actor`` is :data:`~mcp_connector.audit.store.ACTOR_UNKNOWN`, and that is a measured fact
    rather than a shortcut (D-16): ...
    """
    await audit_store.append(
        Entry(
            chain=CHAIN_INSTANCE,
            kind=KIND_SWITCH,
            at=moment,
            actor=ACTOR_UNKNOWN,
            outcome=SWITCH_ON if enabled else SWITCH_OFF,
        )
    )
```

**Unterschied, der in den Plan gehört:** `note_switch` lässt einen Fehler durch, `note` nicht. Der Ablehnungsschreiber folgt `note`: der Docstring dort sagt "Never raises, never writes a value", und der Grund (Zeilen 267-269) gilt für den vor-authentischen Pfad stärker:

```python
except Exception as exc:
    # The type only, never the message: a store error can carry a path (D-13).
    logger.error("the audit log did not record a call: %s", type(exc).__name__)
```

**Feste Bezeichner statt Freitext** (Zeilen 167-176) - genau der Weg, auf dem der Ablehnungsgrund in die Zeile kommt:

```python
def _known_reason(reason: str | None) -> str | None:
    """A rejection identifier out of the frozen set of D-07, or the honest "not determined".
    """
    if reason is None:
        return None
    return reason if reason in REASONS else REASON_UNSPECIFIED
```

---

### `src/mcp_connector/errors.py` (config) - der neue Ablehnungsbezeichner

**Analog:** derselbe Block, Zeilen 14-34.

```python
# The six rejection reasons. Each line says which case sets it.
REASON_UNSPECIFIED = "unspecified"  # not determined; honest instead of guessed
REASON_PERMISSION_DENIED = "permission_denied"  # Nextcloud answered 403
...
# Frozen on purpose: a seventh reason is a decision and belongs into a review, not into a
# diff. ``tests/unit/test_errors_reason.py`` walks src/ and fails on any ``reason=`` that is
# not one of these names.
REASONS: frozenset[str] = frozenset({...})
```

Zwei Konsequenzen für den Plan: (1) die Zahl "six" im Kommentar wird mitgezogen, (2) `tests/unit/test_errors_reason.py` läuft über `src/` und fällt auf jedes `reason=`, das nicht in dieser Liste steht - der Ablehnungsschreiber muss also bereits benannte Werte verwenden.

---

### `src/mcp_connector/oauth/exchange.py` (service, transform) - der Bezeichner an der Ausnahme

**Analog:** Zeilen 139-162, die Stelle selbst.

```python
class ExchangeRefused(Exception):
    """The token, a claim or the key set did not meet the rules. Carries no detail.

    Callers answer every refusal the same way (oracle-free); the reason goes to the log
    as a fixed phrase, never with a value from the token.
    """


def _refused(reason: str) -> ExchangeRefused:
    """One line per refusal, on DEBUG, with a fixed phrase and never a value.

    DEBUG and not WARNING, because in the path phase 22 builds this runs before any
    authentication: a stranger would otherwise decide how many WARNING lines are written
    and how much disk they cost, one HTTP request at a time, and the logging is
    synchronous. ...

    That is a deliberate trade and not the end of the story: what an operator needs to
    see about rejected exchange attempts (today they would stand in no line at all) is
    AUDIT-07 in phase 24, in the hash-chained audit trail and under its content bans. A
    log level is no substitute for it.
    """
    logger.debug("exchange refused: %s", reason)
    return ExchangeRefused()
```

**Zwei Docstrings, die in derselben Änderung mitgezogen werden müssen:** der von `ExchangeRefused` ("Carries no detail" wird unwahr) und der letzte Absatz von `_refused` (Phase 24 ist jetzt hier).

**Die Schrittfolge, die der Trockenlauf spiegeln muss** (`claims_of`, Zeilen 337-480). Die festen Phrasen liegen fertig vor und sind die Liste der Prüfschritte:

```python
if not token:                                   raise _refused("the token is empty")
if len(token) > self._max_token_bytes:          raise _refused("the token is longer than allowed")
# ... encode -> "the token is not text"
header = jwt.get_unverified_header(token)    -> "the token header is unreadable"
header["alg"] not in settings.algorithms     -> "the token uses an algorithm that is not configured"
kid fehlt                                    -> "the token names no key"
header typ fremd                             -> "the token header names another type"
jwt.decode(verify_signature=False)           -> "the token payload is unreadable"
unverified["iss"] != settings.issuer         -> "the token comes from another issuer"
key = await self._keys.key(kid, algorithm)   -> (Schluesselsatz-Abruf)
_PreparsedJWT(...).decode(...)               -> "the token did not meet the standard claims"
audience_holds(...)                          -> "the token is meant for another audience"
azp kein str                                 -> "the token names no acting party"
azp nicht in allowlist                       -> "the token was obtained by an unlisted acting party"
claims["typ"] != typ_expected                -> "the token is not an access token"
iat/exp nicht numerisch                      -> "the token carries no numeric times"
exp - iat > max_lifetime                     -> "the token lives longer than allowed"
now - iat > max_lifetime                     -> "the token is older than allowed"
sub unbrauchbar                              -> "the token names no usable subject"
```

Der Ordnungskommentar dieser Methode ist die Regel, die der Trockenlauf übernimmt (Zeilen 349-352):

```
The order is deliberate: the cheap, local rules fall first, the outgoing key
fetch happens only for a token that already looks like one of our issuer, and
the signature-covered checks are the last word on everything the earlier steps
read unverified.
```

---

### `src/mcp_connector/oauth/exchange_dryrun.py` (neu; service, transform) - EXCH-06, Regelhälfte

**Analog:** `src/mcp_connector/oauth/exchange_accounts.py` für die Modulform, `src/mcp_connector/oauth/exchange.py` für den Inhalt.

**Modulform: nichts liest die Umgebung, nichts spricht mit irgendwem** (`exchange_accounts.py:1-18`):

```python
"""The seam between a mapped principal and the identity it may act under (MAP-01, MAP-02).
...
Nothing here talks to anything. The module holds a protocol, a reserved identifier and one
pure function; the implementations of the protocol arrive with plans 23-03 and 23-04, and
they are the ones that may open a store or ask Nextcloud.
"""

from collections.abc import Mapping
from typing import Any, Final, Protocol, runtime_checkable

from .verifier import OAuthIdentity

__all__ = ["EXCHANGE_CLIENT_ID", "MAX_ACTING_PARTY_LENGTH", "ExchangeAccounts", "acting_party"]
```

**Datenform für ein Ergebnis, das kein fertiger Satz ist** (`audit/store.py:436-456`, `ChainFinding`). Das ist das Vorbild für "ein Prüfschritt mit seinem Ergebnis": die Regel antwortet in Daten, die Shell macht daraus Text und JSON.

```python
@dataclass(frozen=True, slots=True)
class ChainFinding:
    """One broken place in one chain, as data and never as a finished sentence.

    The wording an administrator reads is built by the check command (plan 18-08), so the
    same finding can also be handed out machine readable. What stands here is only what was
    measured: ...
    """

    chain: str
    kind: str
    seq: int
    next_seq: int | None = None
```

**Eigener Schlüsselsatz** (Pitfall 7). Das Konstruktionsmuster steht in `exchange.py:325-335`; der Trockenlauf baut seine eigene Instanz statt die des laufenden Prüfers zu nehmen:

```python
        # (ExchangeTokenChecker.__init__)
        origin=settings.jwks_origin or settings.issuer,
        jwks_uri=jwks_uri,
        algorithms=settings.algorithms,
        refuse=_refused,
        clock=self._clock,
```

---

### `src/mcp_connector/exapp/exchange_check.py` (neu; controller, request-response) - EXCH-06, Konsolenhälfte

**Analog:** `src/mcp_connector/exapp/audit_verify.py`, Datei für Datei übernehmbar.

**Pfadkonstante und Optionsname** (Zeilen 66-77) - die Konstante, aus der `occ.py` den Handlernamen ableitet:

```python
__all__ = ["AUDIT_VERIFY_PATH", "JSON_OPTION", "audit_verify_routes"]

#: The path of the one route of this module, and the name the occ command registration
#: hands to AppAPI as its ``execute_handler`` (``exapp/occ.py`` derives that from this
#: constant, so the two cannot drift apart). It appears in no ``<url>`` of the manifest,
#: on purpose; see the module docstring.
AUDIT_VERIFY_PATH = "/audit-verify"

JSON_OPTION = "json"
```

**Routenfabrik statt Registrierung auf dem Serverobjekt** (Zeilen 147-186):

```python
def audit_verify_routes(
    env: Mapping[str, str] | None = None, *, store_provider: StoreProvider
) -> list[Route]:
    """The one route of the check, handed out rather than registered on the server object.
    ...
    """

    async def audit_verify(request: Request) -> Response:
        guarded = _guard(request, env)
        if isinstance(guarded, Response):
            return guarded

        as_json = await _wants_json(request)
        try:
            ...
        except Exception as exc:
            # The type only, never the message: a store error can carry a path.
            logger.error("the audit log could not be checked: %s", type(exc).__name__)
            if as_json:
                return json_response({"checked": False, "error": type(exc).__name__})
            return _text(f"the audit log could not be checked: {type(exc).__name__}")

        return json_response(_machine_readable(...)) if as_json else _text(_report(...))

    return [Route(AUDIT_VERIFY_PATH, audit_verify, methods=["POST"])]
```

**Guard, wörtlich übernehmen** (Zeilen 309-322):

```python
def _guard(request: Request, env: Mapping[str, str] | None) -> str | Response:
    """Return the Nextcloud user id of this request, or the response that ends it.

    Verbatim the guard of ``exapp/purge.py`` and ``exapp/lifecycle.py`` ... a response
    instead of an exception so no rejection escapes as a 500, and no detail in the
    rejection so nothing tells a caller which of the checks refused it (T-02-03, T-18-07).
    """
    if HEADER_ORIGIN_IP in request.headers:
        return _text("Not Found", status_code=404)
    try:
        return require_appapi(request, env=env)
    except (AppApiRejected, ToolError):
        return json_response({}, status_code=401)
```

**Antwort immer 200** (Zeilen 430-436):

```python
def _text(body: str, status_code: int = 200) -> Response:
    """Every answer of this module that is not JSON, and 200 unless a guard says otherwise.

    The default is the measurement of the module docstring rather than a habit: a status
    other than 200 makes AppAPI drop this body, and the body is the whole answer.
    """
    return Response(body, status_code=status_code, media_type="text/plain", headers=NO_STORE)
```

**Der Schlüssel, den ein Skript beobachtet** (Zeilen 253-282). Für den Trockenlauf heißt er nicht `broken`, sondern `passed`, aus demselben Grund:

```python
def _machine_readable(overview: StoreOverview, findings: list[ChainFinding]) -> dict[str, Any]:
    """The same answer for a monitoring script, with the same 200 under it.

    ``broken`` exists because the exit code cannot carry it: the command answers 0 whatever
    it found, ... so this key is what a script watches instead.
    """
    return {
        "checked": True,
        ...
        "broken": bool(findings),
        "findings": [...],
        "limit": LIMIT_SENTENCE,
    }
```

**Der Ehrlichkeitssatz am Ende jeder Antwort** (Zeilen 124-129) - das Vorbild für Pitfall 8 ("was ein grüner Lauf nicht bedeutet"):

```python
#: The last line of every answer, in both shapes. It belongs in the answer and not only in
#: this docstring, because a green result is judged by whoever reads the console.
LIMIT_SENTENCE = (
    "This check finds an entry that was changed or removed unnoticed. It does not find "
    "somebody who can write this file, because whoever can write it can recompute the "
    "chain behind the change."
)
```

**Body lesen: nicht selbst bauen** (Zeilen 97-110, 325-427). `MAX_BODY_BYTES = 4096`, `MAX_ANNOUNCED_DIGITS = 10`, `TRUE_WORDS`, `_wants_json`/`_set_in`/`_is_set`/`_payload`/`_above_the_body_bound` sind vollständig übernehmbar. Für den Tokenwert kommt ein `_value(...)`-Leser dazu; dafür ist `exapp/audit_read.py:463-499` (`_value`, `_given`) der Analog, weil dort zum ersten Mal Optionen mit **Werten** gelesen werden.

**Achtung, Größengrenze:** `MAX_BODY_BYTES = 4096` ist kleiner als `MAX_TOKEN_BYTES = 8192`. Ein Token von 4 bis 8 KB käme durch die Bodygrenze dieses Musters nicht durch. Das ist ein Entscheidungspunkt für den Plan (Annahme A5 der Recherche) und gehört als erste Messung des Trockenlauf-Tasks angesetzt.

---

### `src/mcp_connector/exapp/occ.py` (config) - das vierte Kommando

**Analog:** derselbe Datei-Block, Zeilen 109-122 (Namen) und 203-217 (einfachster Scheme-Eintrag).

```python
#: What an administrator types for the check of AUDIT-02. The namespace has two levels on
#: purpose: ...
OCC_AUDIT_COMMAND_NAME = "mcp_connector:audit:verify"

#: The route on us AppAPI calls when the check runs, derived exactly like :data:`OCC_HANDLER`.
OCC_AUDIT_HANDLER = AUDIT_VERIFY_PATH.removeprefix("/")
```

```python
        {
            "name": OCC_AUDIT_COMMAND_NAME,
            "description": OCC_AUDIT_DESCRIPTION,
            "hidden": 0,
            "arguments": [],
            "options": [
                {"name": JSON_OPTION, "mode": "none", "description": OCC_AUDIT_JSON_DESCRIPTION}
            ],
            "usages": [OCC_AUDIT_COMMAND_NAME, f"{OCC_AUDIT_COMMAND_NAME} --{JSON_OPTION}"],
            "execute_handler": OCC_AUDIT_HANDLER,
        },
```

**Das Kommando mit Wert-Optionen** (Zeilen 236-259) ist die Form, die der Trockenlauf braucht (`--token=...`): `mode: "optional"` plus `"default": None`. Der Kommentarblock 218-235 darüber ist die Begründung und darf nicht dupliziert, sondern muss referenziert werden.

**Die drei nicht verhandelbaren Regeln**, aus dem Moduldocstring (Zeilen 12-18):

```
a ``mode`` Symfony rejects does not break the command that carries it, it breaks the occ
command line of the whole instance ... So the modes come from the positive list
``required``, ``optional``, ``none``, no command registers an argument, and a test in
``tests/unit/test_exapp_lifecycle.py`` holds every scheme against that list.
```

**Optionsbeschreibung mit benannter Folge** (Pitfall 6). Das Vorbild für eine Beschreibung, die eine Konsequenz ausspricht statt sie zu verschweigen, ist `OCC_FORCE_DESCRIPTION` (Zeilen 101-103):

```python
OCC_FORCE_DESCRIPTION = (
    "Required. This cannot be undone: every connected assistant has to be authorized again."
)
```

---

### `src/mcp_connector/oauth/chain.py` (middleware, request-response) - der Ablehnungsschreiber wird hereingereicht

**Analog:** `build_chain`, Zeilen 601-636, und der Parameter `accounts` aus Phase 23.

```python
def build_chain(
    store_verifier: StoreBranch,
    *,
    env: Mapping[str, str] | None = None,
    config: ExchangeConfig | None = None,
    accounts: ExchangeAccounts | None = None,
) -> StoreBranch:
    """The one place a deployment hangs the chain in, and the one place it does not.

    Without a configured exchange path this returns ``store_verifier`` **itself**, not a
    wrapper that behaves like it today. ... a test can say ``is`` about it instead of
    comparing behaviour and hoping the comparison was complete.
    ...
    ``accounts`` is the account source ... ``None`` keeps the state after phase 22: the
    chain hangs, and every exchange token is refused at the identity step.
    """
    loaded = config if config is not None else load_exchange_config(env)
    if loaded is None:
        return store_verifier
    return ChainedVerifier(
        store=store_verifier,
        checker=ExchangeTokenChecker(loaded.settings),
        config=loaded,
        accounts=accounts,
    )
```

Der Ablehnungsschreiber ist der nächste Parameter derselben Art: `refusals: RefusalWriter | None = None`, `None` heißt "Audit-Log aus" (D-14) und hängt nichts.

**Wo die Abweisung abgefangen wird und damit den Schreiber aufrufen muss** (Zeilen 524-536):

```python
        except ExchangeRefused:
            # The same promise read the other way round: a checked refusal ends here and is
            # never offered to the store branch afterwards.
            return None
        except Exception as exc:
            # Fail closed means this one branch and no other. ... The line names
            # the type of the failure and nothing else: no token, no claim, no principal.
            logger.error("an exchanged token could not be checked: %s", type(exc).__name__)
            return None
```

Zweite Stelle, die eine Zeile verdient (`resolve_identity`, Zeilen 552-576): kein Mapping-Ergebnis, keine Kontoquelle, Ausnahme der Quelle. Hier ist das Claim-Set **geprüft**, also darf nach Pitfall 4 hier (und nur hier) ein `azp` in die Zeile.

---

### `src/mcp_connector/entry_exapp.py` und `entry_oauth.py` (config) - Verdrahtung

**Analog:** `entry_exapp.py:130-183` und `:319-321`.

```python
    accounts = exchange_appapi.AppApiAccounts(env=env) if exchange_config is not None else None
    boundary = chain.build_chain(verifier, env=env, config=exchange_config, accounts=accounts)
    ...
    audit_store = audit_opener(env)
    recorder = (
        audit_record.Recorder(
            audit_store,
            env=env,
            retention_days=config.audit_retention_days(env),
            size_limit=config.audit_size_limit(env),
        )
        if config.audit_log_enabled(env)
        else None
    )
```

Das ist genau die Form für den Ablehnungsschreiber: gebaut, wenn `config.audit_log_enabled(env)` **und** `exchange_config is not None`, sonst `None`. Er bekommt `audit_store` (denselben Opener), nicht eine zweite Datei.

**Routenliste** (Zeilen 319-321) - eine Zeile mehr, in derselben Form:

```python
        *purge_routes(env, nextcloud=nextcloud, store_provider=store),
        *audit_verify_routes(env, store_provider=audit_store),
        *audit_read_routes(env, store_provider=audit_store),
```

**Achtung:** `entry_oauth.py:276` ruft `build_chain` ebenfalls auf. Wenn `build_chain` einen Parameter bekommt, müssen beide Einstiegspunkte entschieden werden - und der Standalone-Betrieb hat kein occ (Open Question 2 der Recherche).

---

### `src/mcp_connector/deps.py` (model) - das fünfte Feld von `Caller`

**Analog:** Zeilen 121-146 und 148-191.

```python
@dataclass(frozen=True, slots=True)
class Caller:
    """Who made one tool call, in the four values a record of it may name (D-08).

    Four fields and no fifth. There is no Nextcloud password here, and that absence is the
    point: ...
    """

    nc_user: str
    client_id: str | None
    auth_id: str | None
    client_name: str | None
```

```python
    identity = _oauth_identity(ctx)
    if identity is not None:
        return Caller(
            # The principal and not the login name: the audit chain of an account is keyed by
            # the value AppAPI callers use as well (oauth/principal.py).
            nc_user=identity.principal,
            client_id=identity.client_id,
            auth_id=identity.auth_id,
            client_name=identity.client_name,
        )
    ...
    return Caller(nc_user=user, client_id=None, auth_id=None, client_name=None)
```

**Der Docstring sagt wörtlich "Four fields and no fifth".** Er wird in derselben Änderung mitgezogen, und der neue Satz muss die Begründung tragen (Delegation belegen), sonst liest die nächste Person den Satz als verletzt. Der AppAPI-Zweig setzt das neue Feld auf `None`, wie er es mit den drei Clientwerten schon tut (Zeilen 136-139).

---

### `src/mcp_connector/exapp/audit_read.py` (controller) - die handelnde Partei in der Ausgabe

**Analog:** `_line` (273-295) und `_document` (358-390) derselben Datei.

```python
def _line(row: tuple[Any, ...]) -> str:
    """One entry on one line, in the order the plan of 19-06 fixed.

    Three of these columns are written by somebody who is not this app: ... Both go
    through :func:`mcp_connector.audit.text.printable`, the one rule of this application
    for such a value.
    """
    entry = _entry_of_row(row)
    return FIELD_SEPARATOR.join(
        (
            _field(row[0]),
            _moment(entry.at),
            printable(entry.chain, limit=CHAIN_LIMIT),
            _field(entry.tool),
            _cleaned(entry.client_name, CLIENT_NAME_LIMIT),   # <- daneben gehoert actor
            _field(entry.outcome),
            _field(entry.reason),
            _field(entry.duration_ms),
            _names(entry.params),
        )
    )
```

```python
def _cleaned(value: str | None, limit: int) -> str:
    """A value from a stranger, made safe to print, and :data:`NULL_FIELD` when there is none."""
    if value is None:
        return NULL_FIELD
    return printable(value, limit=limit) or NULL_FIELD
```

`actor` gehört durch `_cleaned` und nicht durch `_field`: der Wert kommt aus einer fremden Realm. Im JSON-Dokument (Zeilen 370-389) fehlt `actor` heute vollständig; es kommt in derselben Form dazu wie `client_name`:

```python
        "client_name": (
            None
            if entry.client_name is None
            else printable(entry.client_name, limit=CLIENT_NAME_LIMIT)
        ),
```

**Nebenwirkung, die im Plan stehen muss:** `_line` fügt eine Spalte hinzu. `tests/unit/test_exapp_audit_read.py` prüft die Spaltenzahl, und `docs/`-Beispiele der Ausgabe ziehen mit.

---

### `tests/contract/test_no_claim_leak.py` (neu; test, batch) - Kriterium 2

**Analog:** `tests/contract/test_no_destructive_calls.py`.

**Warum dieses Muster und kein grep** (Zeilen 1-20):

```python
"""The security promise of the README, enforced by a gate instead of by discipline.
...
Two things make this test trustworthy rather than decorative:

*   **Comments and docstrings are removed before counting.** ... A naive grep would fail on
    that sentence, and the usual repair is to delete the sentence, which trades
    documentation for a green check. String literals stay in scope on purpose:
    ``method="DELETE"`` is the real thing this gate is looking for.
*   **Every finding names file and line**, so a violation is a one line fix and never a
    hunt through the tree.
"""
```

**Die Maschinerie, wörtlich übernehmbar** (Zeilen 295-328):

```python
def _source_files() -> list[Path]:
    files = sorted(SRC.rglob("*.py"))
    assert files, f"no production sources found under {SRC}"
    return files


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Return the source lines with comments and docstrings blanked out."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    blanked = list(lines)

    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if ast.get_docstring(node, clean=False) is None:
            continue
        first = node.body[0]
        end = first.end_lineno or first.lineno
        for lineno in range(first.lineno, end + 1):
            blanked[lineno - 1] = ""

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        lineno, col = token.start
        blanked[lineno - 1] = blanked[lineno - 1][:col]

    return [(number, text) for number, text in enumerate(blanked, start=1) if text.strip()]
```

**Gegenprobe-Muster** (Zeilen 331-336) - der Grund, warum Gate und Gegenprobe dieselbe Funktion benutzen:

```python
def _violations(relative: str, lines: Iterable[tuple[int, str]]) -> list[str]:
    """Every finding in already filtered lines, in the form the failure message prints.

    Shared by the gate and by its counter proofs on purpose: a counter proof that
    reimplements the check proves something about the counter proof.
    """
```

**Das inhaltliche Gegenstück** für "die Liste darf keine Dekoration sein" steht in `tests/contract/test_audit_surface.py:101-115`:

```python
    assert matched != [], (
        "no name of FORBIDDEN_PARAMS occurs in the measured tool surface: the list would be "
        "decoration, and the case above would pass for the wrong reason"
    )
```

**Was das Gate von Phase 24 sucht** (aus D2 und Pitfall 4): ein Aufruf von `acting_party` außerhalb von `resolve_identity` bzw. der Kontoquelle, und jedes `Entry(...)` im Ablehnungsweg, das ein Feld aus einem ungeprüften Claim-Set trägt.

---

### `tests/unit/test_exapp_entry.py` (geändert) - BL-21 / IN-04

**Analog:** `tests/unit/test_oauth_exchange_chain.py:1171-1202`, der OAuth-Zwilling.

```python
@respx.mock
def test_repeated_exchange_refusals_end_in_429_while_the_existing_path_is_untouched(
    tmp_path: Path,
) -> None:
    """The bound of EXCH-05, and the promise around it, in one measurement.

    ``Bearer a.b.c`` has the shape of the exchange path and fails at its unreadable header,
    so the counting is provable without a single outgoing fetch: the key set route is
    registered and stays at zero calls. ...
    """
    keys = serve()
    app = entry_oauth.build_oauth_app(standalone_env(tmp_path))

    with TestClient(app, base_url=PUBLIC_URL) as client:
        refused = [
            mcp_call(client, "Bearer a.b.c").status_code
            for _attempt in range(throttle.EXCHANGE_LIMIT)
        ]
        throttled = mcp_call(client, "Bearer a.b.c")
        dotless = mcp_call(client, "Bearer a-token-this-server-issued-itself")

    assert refused == [401] * throttle.EXCHANGE_LIMIT
    assert throttled.status_code == 429
    assert int(throttled.headers["Retry-After"]) > 0
    assert keys.call_count == 0, "an unreadable header never costs an outgoing fetch"
    assert dotless.status_code == 401, "the exception of the MCP route holds for our own tokens"
```

**Die Helfer im ExApp-Aufbau stehen bereit.** `bearer_call` (`tests/unit/test_exapp_entry.py:2117-2123`):

```python
def bearer_call(client: TestClient, token: str) -> Any:
    """One MCP request of a connected client: the OAuth branch of the boundary."""
    return client.post(
        "/mcp",
        json=INITIALIZE,
        headers={**MCP_HEADERS, **appapi_headers(user=""), "Authorization": f"Bearer {token}"},
    )
```

`appapi_headers(user="")` ist der Unterschied zum OAuth-Zwilling und der Grund, warum der Test ohne diesen Header grün wäre, ohne den Drosselpfad je zu erreichen (`require_appapi` läuft davor).

`EXCHANGE_ENV` (`tests/unit/test_exapp_entry.py:2442-2447`):

```python
EXCHANGE_ENV = {
    "NC_MCP_EXCHANGE_ENABLED": "1",
    "NC_MCP_EXCHANGE_ISSUER": EXCHANGE_ISSUER,
    "NC_MCP_EXCHANGE_AZP": EXCHANGE_AZP,
    "NC_MCP_EXCHANGE_ACCOUNT_CLAIM": EXCHANGE_CLAIM,
}
```

**Oracle-Gate daneben** (`test_oauth_exchange_chain.py:1204-1219`) - die Form, die Pitfall 3 hält:

```python
    assert throttled.json()["error"] == "temporarily_unavailable"
    spoken = throttled.text.lower()
    for word in ("exchange", "signature", "issuer", "audience", "claim", "key"):
        assert word not in spoken
```

---

### `src/mcp_connector/oauth/jwks.py` (Docstring) - BL-21 / IN-05

**Analog:** die Methode selbst, Zeilen 196-211.

```python
    def forget(self) -> None:
        """Drop the cached key set; the two pre-authentication brakes stay standing.

        Why the method exists: a revocation inside this process has to reach the whole
        chain. A key set that keeps a rotated key ready for five more minutes is the second
        half of the very five second window ``StoreTokenVerifier.invalidate`` closes, and
        closing one half alone is a promise that does not hold.

        Why the two timestamps of this layer survive it: they are the brake this layer puts
        in front of the authentication, and a revocation that took them along would be a
        way to reset the cooldown from the outside, which is precisely the amplifier they
        were written against. ...
        """
        self._keys.keys.clear()
        self._keys.fetched_at = float("-inf")
```

Der neue Absatz trägt eine **gemessene** Zahl mit Datum. Das Muster für eine gemessene Zahl in einem Docstring steht in `audit/store.py:601-610`:

```python
def used_bytes(conn: sqlite3.Connection) -> int:
    """How many bytes this store really occupies.

    Not the file size and not ``page_count * page_size``: neither of them falls after rows
    are dropped, because the pages move to the free list (measured 2026-08-29: 20.000 rows,
    half of them dropped, file unchanged at 4.579.328 byte, 532 free pages). ...
    """
```

Zähler der Messung: `keys.call_count` aus dem `respx`-Muster oben.

---

### `docs/exchange-evidence.md` (neu; doc) - EXCH-07

**Analog:** `docs/spike-dav.md`.

**Kopf** (Zeilen 1-16):

```markdown
# DAV Impersonation Spike (D-30, AUTH-05)

**Status:** done, decision case A (every family runs under impersonation)
**Decision date:** 2026-08-15
**Nextcloud version:** 34.0.2 (build 34.0.2.1)
**AppAPI version:** 34.0.0
**Deploy daemon:** HaRP, over the `compose.exapp.yml` topology (Caddy on `127.0.0.1:8081`)
**Scope:** does the identity of the logged in user arrive in every Nextcloud API family when
the only credential in play is `APP_SECRET`, ...
```

**Der Negativfall, der die Datei trägt** (Zeilen 91-102) - genau die Struktur, die EXCH-07 braucht, mit Rohausgabe und dem Satz, warum `404` und nicht `200` die Aussage ist:

```markdown
### The negative case: bob cannot reach alice's file, even by the exact path

```
# PUT /remote.php/dav/files/alice/<marker>.md, impersonating alice
create as alice HTTP 201

# GET /remote.php/dav/files/alice/<marker>.md, impersonating bob
read alices path as bob HTTP 404
```

The path is already known, so nothing but Nextcloud's own permission check stands between
bob and the file. The answer is `404`, never `200`. This is the mitigation for T-02-50.
```

**Confused Deputy** (Zeilen 104-116) - für den Exchange-Pfad neu zu messen, weil dort zwei Bearer-Wege nebeneinander liegen.

**Serverseitiger Beweis** (Zeilen 118-131) - die eigentliche Evidenz ist das Impersonation-Log, nicht der Statuscode:

```markdown
### Server side impersonation log

Every request above appears in `data/exapp_impersonation.log`, one line per request with the
resolved user. ...

```
{"time":"2026-08-15T11:55:26+00:00","remoteAddr":"172.29.42.1","user":"alice","app":"mcp_connector","method":"PUT","url":"/remote.php/dav/files/alice/nurfueralice-evidence-3459.md","message":"impersonation request","version":"34.0.2.1"}
```
```

**Abschluss** (Zeilen 133-139): ein Abschnitt `## Consequence`, der sagt, welcher Fall eingetreten ist und was daraus folgt.

**Pitfall 9 als Pflichtteil:** in der Rohausgabe muss `NC_MCP_EXCHANGE_ISSUER` bzw. `client_id = urn:mcp-connector:token-exchange` auftauchen, sonst belegt die Datei nur das, was `spike-dav.md` seit 2026-08-15 belegt.

---

### `docs/token-exchange.md` (neu; doc) - EXCH-08

**Analog:** `docs/standalone-oauth.md` (Einrichtungsdoku, Englisch, mit einem Abschnitt über Grenzen). Der offene Anker steht dort in den Zeilen 62-66 und wird von dieser Datei eingelöst:

> "How the token exchange path is configured end to end, on this side and at the identity provider, gets its own setup document"

Zehn Bausteine aus `24-RESEARCH.md`, Abschnitt "Doku-Bausteine für EXCH-08". Die Quelle für die Variablenliste ist **ausschließlich** der Docstring von `oauth/chain.py:19-65`; eine zweite Fassung der Defaults in der Doku ist genau die Doppelpflege, die dieses Repo schon dreimal bestraft hat (R-18-06).

Doku-Wahrheitsgate beachten: `tests/unit/test_docs_audit_truth.py` existiert bereits und prüft Aussagen der Doku gegen den Code. Der Plan sollte prüfen, ob die neue Datei dort mitgeführt werden muss.

---

## Shared Patterns

### Fremder Text, der in eine Zeile oder auf eine Seite geht

**Quelle:** `src/mcp_connector/audit/text.py` (`printable`), angewandt in `audit/store.py:532-549`, `audit/record.py:108-126`, `exapp/audit_verify.py:285-306`, `exapp/audit_read.py:303-312`.
**Gilt für:** `actor` in `store._row_values`, `actor` in `audit_read._line` und `_document`, jeden Wert des Trockenlaufs, der in die Antwort geht.

```python
def _clamped_client_name(raw: str | None) -> str | None:
    """The registered name of a client, made safe to write down and bounded in length.

    The rule itself lives in :mod:`mcp_connector.audit.text` and lives there exactly once. It
    used to stand here in five lines of its own, in ``audit/store.py`` in five more and in
    ``exapp/audit_verify.py`` in five more, and two of those three replaced only the C0 range
    and DEL: three versions with two different sets of characters were R-18-06 of phase 18,
    and a name carrying a right-to-left override could turn the reading direction of an
    output line round.
    """
    if raw is None:
        return None
    return printable(raw, limit=store.CLIENT_NAME_LIMIT) or None
```

Wichtig für D1: `acting_party` (`oauth/exchange_accounts.py:84-88`) filtert mit `character.isprintable()` und ist **nicht** dieselbe Regel. Ein Test hält die beiden Wege gegeneinander.

### Fehlerbehandlung: der Typ, nie die Meldung

**Quelle:** `audit/record.py:267-269`, `exapp/audit_verify.py:169-174`, `oauth/chain.py:528-535, 571-576`.
**Gilt für:** jeden neuen `except`-Block dieser Phase.

```python
except Exception as exc:
    # The type only, never the message: a store error can carry a path.
    logger.error("the audit log could not be checked: %s", type(exc).__name__)
```

### Fähigkeit hereinreichen statt importieren

**Quelle:** `oauth/chain.py:601-636` (`accounts`), `exapp/audit_verify.py:147-156` (`store_provider`), `audit/record.py:53-56` (`StoreProvider`).
**Gilt für:** den Ablehnungsschreiber und den Trockenlauf-Store.

```python
#: How a caller hands in its own store, the shape ``exapp/purge.py`` uses for the OAuth one.
type StoreProvider = Callable[[], Awaitable[AuditStore]]
```

Aus-Zustand heißt: das Objekt selbst zurückgeben, nicht ein Wrapper mit gleichem Verhalten. Ein Test kann dann `is` sagen.

### Nichts geht durch `exapp/middleware.py`

**Quelle:** Phase 22 und 23 haben die Transportgrenze unangetastet gelassen; `exapp/middleware.py:144-147` (401) und `:157-175` (Recorder nur nach bestandener Prüfung).
**Gilt für:** alle Pläne dieser Phase. Der Ablehnungsschreiber hängt in `oauth/chain.py`, nicht an der Grenze.

### Kein Orakel in der HTTP-Antwort

**Quelle:** `tests/unit/test_oauth_exchange_chain.py:1204-1219`.
**Gilt für:** jeden Plan, der `ExchangeRefused` ein Feld gibt. Der Bezeichner verlässt den Prozess an genau einer Stelle: der Audit-Zeile.

### Jede occ-Antwort ist 200, jeder JSON-Schlüssel hat einen Beobachter

**Quelle:** `exapp/audit_verify.py:25-33` (Begründung), `:430-436` (`_text`), `:253-282` (`broken`), `exapp/audit_read.py:335-355` (`read`).
**Gilt für:** `exapp/exchange_check.py` (`passed`).

---

## No Analog Found

| Datei | Rolle | Datenfluss | Grund |
|-------|-------|------------|-------|
| Die Schreibbremse des Ablehnungsschreibers (Teil von `audit/refusals.py` bzw. `audit/record.py`) | service | rate-limited write | Es gibt in `src/` keine gebremste Schreibstelle. `oauth/throttle.py` bremst **Anfragen** gegen ein Zeitfenster und lebt im OAuth-Paket; `audit/` darf es nicht importieren (Schichtregel in `audit/record.py:21-25` und `tests/contract/test_module_boundaries.py`). Das nächste verwandte Muster ist die Intervall-Regel `should_sweep` / `should_check_accounts` (`audit/store.py:501-518`): eine reine Funktion auf der Sequenznummer, kein Zähler auf Modulebene (D-20). Der Planer sollte prüfen, ob die Bremse auf demselben Prinzip gebaut werden kann (Zustand aus der Kette lesen statt im Prozess halten), sonst gilt RESEARCH.md D2 / Pitfall 2 / Open Question 4 als Entwurfsfläche. |

---

## Decision Points für den Planer (aus dem Musterabgleich, nicht aus RESEARCH.md)

1. **Bodygrenze gegen Tokengröße.** `MAX_BODY_BYTES = 4096` (`audit_verify.py:97`) gegen `MAX_TOKEN_BYTES = 8192` (`exchange.py:104`). Das kopierte Muster ist zu eng für sein neues Datum. Erste Messung des Trockenlauf-Tasks (Annahme A5).
2. **`build_chain` hat zwei Aufrufer.** `entry_exapp.py:141` und `entry_oauth.py:276`. Ein neuer Parameter zwingt beide zu einer Entscheidung; im Standalone-Betrieb gibt es kein occ.
3. **Alle Leser der Spalte `chain`** (Annahme A4). Gefunden wurden: `_SILENT_CHAINS` (store.py:397), `_account_of` (store.py:191), `_SWEEPABLE_TOTAL` (340), die vier Sweep-Anweisungen (365-375), `_COUNT_OF_CHAIN`/`_DROP_CHAIN` (400-401), `audit_read._chain_of` (398) plus `INSTANCE_KEYWORD` (audit_read.py:155), `audit_verify._printable` (285). Jeder gehört im Plan einzeln geprüft.
4. **`_line` bekommt eine Spalte.** `tests/unit/test_exapp_audit_read.py` und jedes Ausgabebeispiel unter `docs/` ziehen mit.
5. **`tests/unit/test_errors_reason.py` läuft über `src/`** und fällt auf jedes `reason=`, das nicht in `REASONS` steht. Neue Bezeichner und ihre Verwendung gehören in denselben Commit.

---

## Metadata

**Analog search scope:** `src/mcp_connector/audit/`, `src/mcp_connector/oauth/`, `src/mcp_connector/exapp/`, `src/mcp_connector/` (Einstiegspunkte), `tests/contract/`, `tests/unit/`, `docs/`
**Dateien gelesen (ganz oder in gezielten Bereichen):** 14 Quelldateien, 4 Testdateien, 1 Doku-Datei
**Pattern extraction date:** 2026-09-23

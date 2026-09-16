"""The handler behind ``occ mcp_connector:purge``: end every connection of this instance.

Success criterion 2 of this phase says an uninstall removes all data, tokens included. The
measurement says the opposite happens on its own: the Remove button of Nextcloud 34 calls
``disableExApp()`` for an ExApp, so the container stops and nothing else does. The volume
with the encrypted app passwords stays, ``ExAppService::unregisterExApp()`` does not delete
the ExApp configuration this app keeps its data key in, and the Nextcloud app passwords in
``oc_authtoken`` are touched by no AppAPI path at all. Measured on this machine two days
after the last run: 85 clients, 84 authorizations, 83 refresh tokens, all still there, and
84 app passwords still valid. Without this module the criterion is not reachable.

Three decisions, each with its source, because each of them is one somebody will want to
undo.

**Why there is no route in the manifest.** The occ command reaches this handler over
AppAPI's ``PublicFunctions``, the same internal path ``/heartbeat``, ``/init`` and
``/enabled`` arrive on, so it needs no declaration to work. Declaring one would publish an
instance wide deletion to the internet, because the PHP proxy attaches valid AppAPI headers
itself and protects none of these paths (T-02-20, pitfall 13 of 05-RESEARCH.md). The big
comment in ``appinfo/info.xml`` names this path as the fourth deliberately absent one, and
:func:`purge_routes` therefore runs the same double check ``exapp/lifecycle.py`` runs:
``x-origin-ip`` means the PHP proxy and is answered with 404, then ``require_appapi``.

**Why the order is not negotiable.** The data key lives in Nextcloud's ExApp configuration,
the encrypted app passwords live in the volume, and one is useless without the other.
Revoking a Nextcloud app password means authenticating with that very password, so it has
to be decrypted first. Whoever deletes the key first, or empties the tables first, has
destroyed the only knowledge of which credential belongs to which connection, and every one
of them stays valid in Nextcloud with no record left that it exists (pattern 4 of
05-RESEARCH.md). Hand back, then empty, then delete the key.

**Why nothing is cleaned up on the ``enabled=0`` hook.** That hook looks like the natural
place, because the Remove button fires exactly it. It also fires on every update
(``lib/Command/ExApp/Update.php``) and on every ordinary disable, so cleaning up there
would delete every connection of every user whenever an administrator updates the app. The
disable branch of ``exapp/lifecycle.py`` stays empty, and a test in
``tests/unit/test_exapp_purge.py`` keeps it that way (T-05-28).
"""

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from ..errors import ToolError
from ..nextcloud.target import NextcloudTarget
from ..oauth import crypto, loginflow
from ..oauth.store import AuthorizationRow, OAuthStore
from .auth import AppApiRejected, require_appapi
from .responses import NO_STORE, BodyTooLarge, BodyUnreadable, bounded_body, json_response

__all__ = ["FORCE_OPTION", "PURGE_PATH", "purge_routes"]

#: The path of the one route of this module, and the name the occ command registration
#: hands to AppAPI as its ``execute_handler`` (``exapp/occ.py`` derives that from this
#: constant, so the two cannot drift apart). It appears in no ``<route>`` of the manifest,
#: on purpose; see the module docstring.
PURGE_PATH = "/purge"

#: The one option of the command. Declared on the AppAPI side in ``exapp/occ.py`` and
#: checked here as well, because what AppAPI hands over is input: an instance wide deletion
#: does not run because a declaration somewhere else says a flag is required.
FORCE_OPTION = "force"

#: The envelope AppAPI wraps an occ invocation in, and the answer to assumption A5, point 2.
#: Measured against a running AppAPI 34.0.0 on 2026-08-19 (plan 05-08): the command object
#: built by ``ExAppOccService::buildCommand`` calls ``PublicFunctions::exAppRequest`` with
#: ``params: ['occ' => ['arguments' => ..., 'options' => ...]]``, and
#: ``AppAPIService::prepareRequestToExApp`` turns ``params`` into the JSON body of a POST.
#: So the body of a real invocation is ``{"occ": {"arguments": null, "options": {"force":
#: true}}}`` and the flag is one level below the top. Without this key the live command
#: answered ``purged: false`` with ``--force`` on the command line.
OCC_ENVELOPE = "occ"

#: Set on the proxy path, never by HaRP and never on the internal AppAPI path. The same
#: header ``exapp/lifecycle.py`` refuses, spelled a second time rather than imported: that
#: module imports ``exapp/occ.py``, which imports this one, so an import back would close a
#: cycle. A test holds the two spellings equal.
HEADER_ORIGIN_IP = "x-origin-ip"

#: The largest body this handler reads before deciding it is not an occ invocation. The
#: real one is a handful of option names; anything above this is not AppAPI and is not
#: parsed (the rule of ``oauth/connections.py``, MAX_FORM_BYTES).
MAX_BODY_BYTES = 4096

#: The words that mean "no" when a flag arrives with a value. They are no longer the
#: decision (:data:`TRUE_WORDS` is), they are the difference between a decision and a typo:
#: a spelled out no needs no log line, an unknown word does.
FALSE_WORDS = frozenset({"0", "false", "no", "off", "none", "nein"})

#: The words that mean "yes" when the flag arrives with a value, and the whole list of them
#: (WR-02). The spellings are the ones ``oauth/registry.py`` and ``exapp/config_values.py``
#: already use, so a value that arms a switch of this app reads the same everywhere.
#:
#: What plan 05-08 measured against a running AppAPI 34.0.0 is not a word at all: the body
#: of a real invocation is ``{"occ": {"arguments": null, "options": {"force": true}}}``, so
#: the flag arrives as a JSON boolean and :func:`_is_set` answers it before this list is
#: consulted. The list is therefore the lower bound of what stays accepted around that
#: measurement, never a guess that replaces it.
TRUE_WORDS = frozenset({"1", "true", "yes", "on"})

FORCE_HINT = (
    "Nothing was changed. This command ends every MCP connection of this instance and "
    f"cannot be undone, so it only runs with --{FORCE_OPTION}."
)

STORE_HINT = (
    "Nothing was changed: the data of this app could not be opened, so no credential "
    "could be handed back to Nextcloud. Check that the app is enabled and that its volume "
    "is readable, then run the command again before removing the app."
)

#: Counts and the way out, never an account and never a connection (V7, T-05-60). The
#: number is already in the answer next to this text, so the sentence carries the meaning
#: instead of repeating it.
REVOKE_HINT = (
    "Nothing was deleted. Not one app password could be handed back to Nextcloud, which "
    "is a fault of the connection to Nextcloud rather than of a single connection of this "
    "app. The tables of this app are untouched, so fix the reachability and run the "
    "command again: that run is a complete one. If it keeps answering this, the manual "
    "clean up per user is in docs/uninstall.md."
)

logger = logging.getLogger("mcp_connector.exapp.purge")

#: How a caller hands in its own store, the same shape ``oauth/connections.py`` uses.
type StoreProvider = Callable[[], Awaitable[OAuthStore]]


def purge_routes(
    env: Mapping[str, str] | None = None,
    *,
    nextcloud: NextcloudTarget,
    store_provider: StoreProvider,
) -> list[Route]:
    """The one route of the purge, handed out rather than registered on the server object.

    A factory for the reason D-23 gives and ``exapp/lifecycle.py`` states: a registration on
    the shared MCP server object would make this path appear in the standalone HTTP mode of
    phase 1 as soon as anything imports this module, and that mode has no AppAPI identity to
    check it against.
    """

    async def purge(request: Request) -> Response:
        """Revoke, empty, delete the key. In that order, and only with ``force``."""
        guarded = _guard(request, env)
        if isinstance(guarded, Response):
            return guarded

        if not await _forced(request):
            logger.info("a purge without the force option changed nothing")
            return json_response({"purged": False, "hint": FORCE_HINT})

        try:
            store = await store_provider()
            rows = await store.all_authorizations()
        except Exception as exc:
            # The type only, never the message: a store error can carry a path.
            logger.error("the purge found no readable store: %s", type(exc).__name__)
            return json_response({"purged": False, "hint": STORE_HINT})

        revoked, failures = await _hand_back_every(store, rows, nextcloud)
        if rows and revoked == 0:
            # WR-01 of 05-REVIEW.md, and the line is drawn at zero on purpose. A run that
            # handed back nothing at all signals a fault of the connection to Nextcloud and
            # not a single broken row, and these tables are the only record of which app
            # password belongs to which connection. Emptying them in this moment destroys
            # that record while every one of those credentials stays valid in Nextcloud,
            # which leaves the manual clean up of docs/uninstall.md as the only rescue and
            # makes a second run of this command pointless. So: keep everything, say so,
            # stay repeatable.
            logger.error(
                "the purge changed nothing: none of the %s connections could hand its app "
                "password back to Nextcloud",
                len(rows),
            )
            return json_response(
                {
                    "purged": False,
                    "connections": len(rows),
                    "revoked": revoked,
                    "revoke_failures": failures,
                    "hint": REVOKE_HINT,
                }
            )

        cleared = await _empty(store)
        # Last, and only now. Every ciphertext this key opens is gone at this point, and
        # until this line every one of them still had to be decryptable.
        key_deleted = await crypto.delete_key(env)

        logger.info(
            "the purge ended %s connections, handed back %s app passwords, failed on %s, "
            "cleared the tables: %s, deleted the data key: %s",
            len(rows),
            revoked,
            failures,
            cleared,
            key_deleted,
        )
        return json_response(
            {
                "purged": True,
                "connections": len(rows),
                "revoked": revoked,
                "revoke_failures": failures,
                "tables_cleared": cleared,
                "key_deleted": key_deleted,
            }
        )

    return [Route(PURGE_PATH, purge, methods=["POST"])]


async def _hand_back_every(
    store: OAuthStore, rows: list[AuthorizationRow], nextcloud: NextcloudTarget
) -> tuple[int, int]:
    """Give every Nextcloud app password back, one attempt each. Returns (done, failed).

    Three properties of ``provider.sweep_abandoned``, which this loop is built after, hold
    here as well and all three are the difference between a purge and a hang: one attempt
    per credential with the five second timeout of ``loginflow.REVOKE_TIMEOUT`` and no
    retry, a failure that is counted instead of raised, and a loop that keeps going
    (T-05-31). Nothing of a row is logged: the count is the report, the account is not
    (security domain V7, T-05-29).
    """
    revoked = 0
    failures = 0
    for row in rows:
        try:
            password = await store.app_password(row.auth_id)
        except Exception:
            logger.error("the app password of a connection could not be read back")
            password = None

        if password and await loginflow.revoke_app_password(
            row.nc_user, password, target=nextcloud
        ):
            revoked += 1
        else:
            # loginflow already logged what happened, without a value of the exchange.
            failures += 1
            logger.warning("a connection was purged without handing its app password back")
    return revoked, failures


async def _empty(store: OAuthStore) -> bool:
    """Empty every table, or report that it did not happen. Never raises.

    A failure here does not invalidate the revocations above, and it must not hide them:
    the answer of the handler carries both facts as their own field.
    """
    try:
        await store.wipe_all()
    except Exception as exc:
        logger.error("the tables of this deployment were not emptied: %s", type(exc).__name__)
        return False
    return True


def _guard(request: Request, env: Mapping[str, str] | None) -> str | Response:
    """Return the Nextcloud user id of this request, or the response that ends it.

    Verbatim the guard of ``exapp/lifecycle.py``, including the reason for both halves: a
    response instead of an exception so no rejection escapes as a 500, and no detail in the
    rejection so nothing tells a caller which of the checks refused it (T-02-03).
    """
    if HEADER_ORIGIN_IP in request.headers:
        return _text("Not Found", status_code=404)
    try:
        return require_appapi(request, env=env)
    except (AppApiRejected, ToolError):
        return json_response({}, status_code=401)


async def _forced(request: Request) -> bool:
    """Whether this invocation carries the ``force`` flag, in any shape AppAPI may send it.

    The wire shape of an occ option was assumption A5 until plan 05-08 measured it against a
    running AppAPI 34.0.0: the body is the envelope named in :data:`OCC_ENVELOPE`, and the
    flag sits inside it. The measurement is the reason this function still accepts the other
    spellings rather than only that one. Both directions matter, and the first one is what
    the measurement found: without the envelope, ``occ mcp_connector:purge --force`` answered
    ``purged: false`` on a live instance, so an administrator would have removed the app
    believing the credentials were gone. A purge that runs without the flag is the other
    failure, an instance wide deletion nobody asked for.

    The query string is not read, and that is WR-02 of 05-REVIEW.md. The measured
    invocation carries the flag in the JSON body and nowhere else
    (``AppAPIService::prepareRequestToExApp`` puts the parameters of a POST into the body,
    and this is a POST only route), so a query parameter is a shape AppAPI never produces.
    Every additionally accepted shape is attack surface for the day one of the three
    barriers in front of this handler falls, and an empty ``?force=`` was a yes.
    """
    return _forced_in(await _payload(request))


def _forced_in(payload: Any, *, inside_envelope: bool = False) -> bool:
    """The flag in a JSON body: in the occ envelope, at the top level, or in a list.

    ``inside_envelope`` keeps the descent one level deep. The envelope AppAPI builds carries
    no second one, and a body that nests them is not an occ invocation.
    """
    if not isinstance(payload, dict):
        return False
    if FORCE_OPTION in payload and _is_set(payload[FORCE_OPTION]):
        return True

    options = payload.get("options")
    if isinstance(options, dict) and FORCE_OPTION in options and _is_set(options[FORCE_OPTION]):
        return True
    if isinstance(options, list | tuple) and any(
        isinstance(item, str) and item.strip().lstrip("-") == FORCE_OPTION for item in options
    ):
        return True

    if not inside_envelope:
        return _forced_in(payload.get(OCC_ENVELOPE), inside_envelope=True)
    return False


def _is_set(value: object) -> bool:
    """Whether this value means the flag is set. A positive list, and nothing beside it.

    Until WR-02 this read "only a spelled out no is a no", which made every unknown word a
    yes for the one action of this app that cannot be undone. That inverted the rule
    ``registry._switch`` and ``config_values._switch`` follow everywhere else: a value
    nobody understands is a typo, and a typo is not a security switch. So a yes is a JSON
    ``true``, the number one, a flag that arrived with no value at all (a Symfony option in
    mode ``none`` is presence and nothing more), or one of :data:`TRUE_WORDS`.

    The number side is WR-01 of the re-review: "a number other than zero" survived the
    WR-02 fix, so the string ``"2"`` was a no with a warning while the number ``2`` armed
    the purge. Numbers now follow the same positive list as words: one is the yes, zero is
    the spelled out no, and every other number is the typo an unknown word is.

    An unknown value leaves one line behind, a spelled out no does not: the second one is a
    decision, the first one is the typo somebody has to be able to find.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    if isinstance(value, int | float):
        if value == 1:
            return True
        if value != 0:
            _warn_unknown_value()
        return False
    if not isinstance(value, str):
        return False

    word = value.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word not in FALSE_WORDS:
        _warn_unknown_value()
    return False


def _warn_unknown_value() -> None:
    """The one line an unrecognized flag value leaves behind.

    The value itself stays out of the log, like every other value on this path (V7).
    """
    logger.warning(
        "the %s option of a purge carried a value that is neither on nor off, so "
        "nothing was changed. The values it understands are %s.",
        FORCE_OPTION,
        ", ".join(sorted(TRUE_WORDS)),
    )


async def _payload(request: Request) -> Any:
    """The JSON body, or ``None`` when there is none this handler is willing to read.

    Bounded and never logged. The body arrives on the internal AppAPI path, so it is not
    attacker input in the ordinary sense, and it is still the input of a destructive action:
    a body above :data:`MAX_BODY_BYTES` is not an occ invocation and is not parsed at all.

    IN-01 of the re-review is why the limit is not the announced length any more. The header
    is the sender's claim about the body, and a request with ``Transfer-Encoding: chunked``
    makes no claim at all: it carried no ``content-length``, the check therefore never fired,
    and ``request.body()`` read whatever arrived into memory, flag included. The announced
    length is still read first, because refusing before a single byte is on the wire is
    cheaper than counting; ``responses.bounded_body`` is what actually holds.

    That counting lives in ``exapp/responses.py`` and not here, because the connections form
    had the identical hole behind the identical header check, and one limit with two callers
    is one place to get it right.
    """
    announced = request.headers.get("content-length", "")
    if announced.isdigit() and int(announced) > MAX_BODY_BYTES:
        logger.warning("a purge call announced a body this handler does not read")
        return None
    try:
        raw = await bounded_body(request, MAX_BODY_BYTES)
    except BodyTooLarge:
        logger.warning("a purge call sent a body this handler does not read")
        return None
    except BodyUnreadable:
        logger.warning("the body of a purge call could not be read")
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("the body of a purge call is not JSON")
        return None


def _text(body: str, status_code: int) -> Response:
    return Response(body, status_code=status_code, media_type="text/plain", headers=NO_STORE)

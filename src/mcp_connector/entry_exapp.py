"""Console script ``nc-mcp-exapp``: the MCP server as a Nextcloud ExApp (EXAPP-01).

This is the fourth operating mode of the same code base (D-23). It serves the same MCP
endpoint as ``entry_http``, plus the three AppAPI lifecycle routes, and it takes its
identity exclusively from the deploy environment the AppAPI deploy daemon injects:

``APP_ID``, ``APP_SECRET``, ``APP_VERSION`` and ``NEXTCLOUD_URL`` are set when the
container starts, together with ``APP_HOST``/``APP_PORT`` for a plain deployment or
``HP_SHARED_KEY``/``HP_EXAPP_SOCK`` behind HaRP.

This process never needs a Nextcloud account of its own. It authenticates to Nextcloud
with ``APP_SECRET`` plus the user id AppAPI puts into the incoming header, so a second
credential channel in the environment is not a convenience but the silent fallback D-27
forbids: ``main`` refuses to start when one is configured.
"""

import asyncio
import logging
import os
import time
from collections.abc import Mapping

import httpx
import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Route

from . import config
from .audit import CHAIN_INSTANCE, KIND_SWITCH, AuditStore, audit_opener
from .audit import record as audit_record
from .audit.store import AUDIT_FILENAME
from .errors import IssuerRefused, ToolError
from .exapp import config_values
from .exapp.audit_read import audit_read_routes
from .exapp.audit_verify import audit_verify_routes
from .exapp.lifecycle import lifecycle_routes
from .exapp.middleware import RequireAppApi
from .exapp.purge import purge_routes
from .exapp.ui import strings
from .nextcloud.http import USER_AGENT, NoCookieJar, configure_logging
from .oauth import throttle
from .oauth.connect import connect_routes
from .oauth.connections import connections_routes
from .oauth.consent import consent_routes
from .oauth.metadata import metadata_routes
from .oauth.provider import NextcloudOAuthProvider, auth_routes
from .oauth.registry import client_policy
from .oauth.store import store_opener
from .oauth.verifier import StoreTokenVerifier
from .server import mcp

__all__ = ["build_exapp_app", "main"]

#: The one route of this application that carries the MCP transport.
MCP_PATH = "/mcp"

#: The socket path HaRP itself defaults to when it starts an ExApp with the FRP tunnel.
DEFAULT_EXAPP_SOCK = "/tmp/exapp.sock"  # noqa: S108 - HaRP dictates this path, not we

#: Both would authenticate a caller of this server on their own, which the ExApp mode must
#: never allow: the identity comes from AUTHORIZATION-APP-API and from nowhere else.
CONFLICTING_VARIABLES = (config.ENV_STATIC_BEARER, config.ENV_APP_PASSWORD)

logger = logging.getLogger("mcp_connector.entry_exapp")


def build_exapp_app(env: Mapping[str, str] | None = None) -> Starlette:
    """Build the MCP application of this deployment and attach the lifecycle routes.

    The MCP half is built exactly like ``entry_http.build_app``. Behind HaRP the ``Host``
    header is the one of the reverse proxy, so the entrypoint of the container sets
    ``NC_MCP_DISABLE_DNS_REBINDING_PROTECTION`` on that path alone. Everywhere else the
    check stays armed, and since issue #4 it is armed over an allowlist that carries the
    public address of this deployment (``config.deployment_hosts``) instead of localhost
    alone: the proxy of an AIO installation forwards the custom domain, and a one click
    installation has no deploy variable to add it with (the 421 of pitfall 6 in phase 1).

    The three lifecycle routes are appended here and nowhere else. Registering them on the
    shared server object would add them to the standalone HTTP mode as well, and D-23 says
    that mode stays as it was.

    The MCP route is wrapped in :class:`~mcp_connector.exapp.middleware.RequireAppApi`
    here and only here, for the same reason: the standalone HTTP mode of phase 1 has no
    AppAPI identity and must not grow an authentication it cannot satisfy (D-23). Inside
    this mode the wrapper is not optional, so a missing wrap is an error and not a
    warning: it would leave the whole JSON-RPC preamble unauthenticated (CR-01).
    """
    security = TransportSecuritySettings(
        allowed_hosts=config.allowed_hosts(env),
        enable_dns_rebinding_protection=config.dns_rebinding_protection(env),
    )
    app = mcp.streamable_http_app(transport_security=security)
    # One policy, one store and one provider for the whole application, built before the
    # transport boundary because the boundary needs the verifier that shares them: a
    # revocation has to be visible to the endpoint that issued the token and to the check
    # that lets it act, and two objects with two stores would be two answers to one
    # question.
    policy = client_policy(env)
    store = store_opener(env)
    provider = NextcloudOAuthProvider(env=env, policy=policy, store_provider=store)
    verifier = StoreTokenVerifier(store_provider=store, get_client=provider.get_client, env=env)
    # The last wire of the pair, and the one that makes "revoked" mean "now": the verifier
    # answers from a five second process cache, and a revocation, whether it comes from the
    # user through /revoke or from the reuse detection of the rotation, empties it in the
    # same process instead of waiting for the window to run out (SC 4, T-03-62).
    provider.on_revocation(verifier.invalidate)
    # One throttle for the whole application, so the five path classes are five counters
    # and not five objects with five ceilings (SC 5, D-37). It never reaches the MCP route:
    # a tool call arrives with a verified bearer and is answered from the process cache,
    # and rate limiting the actual work of this server would be our own denial of service.
    counters = throttle.Throttle()
    # One audit store per application, built exactly where the OAuth one is built and for
    # the same reason: the file cannot be opened while the routes are, because the path comes
    # from a volume that a deployment may not have mounted yet, so both sides get an opener
    # and the first row that needs the file pays for opening it. No module global either
    # (D-20), which is why this is a local of the function that builds one application.
    audit_store = audit_opener(env)
    # D-14 in one line: without the switch there is no recorder, without a recorder the
    # transport boundary deposits nothing, and without a deposit the recording path in
    # ``graceful`` returns before it has written anything. The known 401 of the first start
    # after an installation falls the same way and needs no branch of its own: AppAPI refuses
    # the admin value read while the app is not enabled yet, ``config_values`` answers with an
    # empty overlay, and an empty overlay leaves the default in code in force, which is off.
    #
    # ``env`` and never ``os.environ``: this is the same resolved mapping ``_resolved_env``
    # handed to every other factory above, and the account check of D-12 (plan 18-09) calls
    # Nextcloud with it. A second, unresolved mapping would have different values at exactly
    # the moment it matters, namely on an installation from the app store, which gets no
    # deploy variable at all.
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

    async def access_disabled(nc_user: str) -> bool:
        """Whether this Nextcloud account has paused its MCP access (EXAPP-02, D-47).

        The switch comes out of the same store as the tokens, through the same opener, so
        one deployment has one file and one answer to "may this account be served". A
        second store here would be a second truth, exactly as a second provider would be.
        The call is a local read per request and nothing caches it: that is what makes the
        flip take effect on the next request instead of within five seconds (D-48).
        """
        opened = await store()
        return await opened.access_disabled(nc_user)

    guarded = 0
    for route in app.router.routes:
        if isinstance(route, Route) and route.path == MCP_PATH:
            route.app = RequireAppApi(
                route.app,
                env,
                token_verifier=verifier,
                access_check=access_disabled,
                audit_recorder=recorder,
            )
            guarded += 1
    if guarded != 1:
        raise RuntimeError(
            f"the ExApp application has {guarded} guarded {MCP_PATH} routes instead of one; "
            "the MCP transport would be served without the AppAPI handshake"
        )
    # The lifecycle routes and the three discovery documents both come from a factory and
    # are attached here, never on the shared server object. A registration on the singleton
    # would make them appear in the standalone HTTP mode of phase 1 as well, and D-23 says
    # that mode stays as it was. The metadata routes replace the measurement probe of the
    # spike (D-29, AUTH-06) with the production path of AUTH-03; they live below
    # /.well-known/, they are public by contract, and they are what the 401 of the transport
    # boundary points a client at. The onboarding routes of AUTH-02 hang here for the same
    # reason twice over: they are the browser half of this deployment mode, and a page that
    # hands out a Nextcloud credential has no business appearing in the standalone HTTP
    # server of phase 1, which has no store, no data key and no AppAPI identity (D-23, D-36).
    # The connections page of EXAPP-02 joins them for the third reason of the same rule: it
    # ends connections and pauses accounts, and it does so through this deployment's own
    # provider, so it hangs where that provider is and nowhere else.
    #
    # The authorization server of plan 03-05 joins the same line: auth_routes builds the
    # endpoints of the SDK with create_auth_routes and our own provider, and consent_routes
    # adds the authorization endpoint in front of it plus the consent screen. The same rule
    # is why the provider is not passed to the MCPServer constructor as auth_server_provider:
    # that would attach these routes to the MCP application, where the standalone mode would
    # inherit them (03-RESEARCH.md, anti patterns).
    #
    # The purge of plan 05-06 hangs here for the same rule a fourth time, and for it the
    # rule is the security control itself: the route has no entry in appinfo/info.xml,
    # because a declared one would make an instance wide deletion callable through the PHP
    # proxy, which attaches valid AppAPI headers itself (T-02-20, T-05-26). It gets the one
    # store of this application, because it empties exactly that file.
    #
    # The check of plan 18-08 hangs here for the same rule a fifth time, and its reason is
    # the fourth one over again with a different loss: /audit-verify is the handler of the
    # occ command mcp_connector:audit:verify, and its answer names the chains of this
    # instance, which are named after the accounts that have them. A declared route would
    # hand that list to anyone who can reach the PHP proxy, because that proxy attaches valid
    # AppAPI headers itself (T-02-20, T-18-07). So the path is absent from appinfo/info.xml,
    # named there only in the comment, and the handler carries the same double check as the
    # four paths above it. It gets the audit store of this application and not the OAuth one,
    # because it checks exactly that file, and it gets it whether the switch of D-14 is on or
    # off: a log that was switched off is the one that most needs to stay checkable.
    #
    # The read of plan 19-07 hangs here for the same rule a sixth time, and it is the loss of
    # the fifth one with one option more: /audit-read is the handler of the occ command
    # mcp_connector:audit:read, and where the check names the chains, this answer names the
    # rows themselves, so a declared route would hand the list of everybody who used this app
    # to anyone who can reach the PHP proxy and, one option further, the tools each of them
    # called (T-02-20, T-19-20). So this path is absent from appinfo/info.xml as well, named
    # there only in the comment, and the handler carries the same double check. It gets the
    # audit store and not the OAuth one, because it reads exactly that file, and it is
    # appended whether the switch of D-14 is on or off: a log that was switched off has to
    # stay readable, because that is what makes it auditable at all, and what a period without
    # recording holds is exactly what somebody will have to be able to look up.
    #
    # The policy read above is what the two places that answer to it read as well: the
    # discovery document stops advertising a registration endpoint when the switch is off,
    # and the routes stop containing one (AUTH-07, D-35). One store opener serves the
    # browser onboarding, the authorization server and the token verifier, so a deployment
    # fetches its data key once and every half writes to one file.
    #
    # The second switch of the same policy travels the same one way (AUTH-08): the document
    # announces client id metadata documents exactly while this deployment resolves them, and
    # it is the same `policy` object `provider.get_client` asks. A second read of the
    # environment here would be a second answer to one question, and the one that a client
    # reads is the one that cannot refuse: a client that picks that way because this document
    # offered it has no fallback left when the resolution then says no.
    for route in (
        *lifecycle_routes(env),
        *metadata_routes(env, dcr_enabled=policy.dcr_enabled, cimd_enabled=policy.cimd_enabled),
        *connect_routes(env, store_provider=store, throttle=counters),
        *connections_routes(
            env,
            store_provider=store,
            end_connection=provider.end_connection,
            throttle=counters,
        ),
        *auth_routes(env, provider=provider, throttle=counters),
        *consent_routes(env, provider=provider, throttle=counters),
        *purge_routes(env, store_provider=store),
        *audit_verify_routes(env, store_provider=audit_store),
        *audit_read_routes(env, store_provider=audit_store),
    ):
        app.router.routes.append(route)
    return app


def _warn_when_the_host_check_is_a_trap(env: Mapping[str, str] | None = None) -> None:
    """Name the 421 trap of a docker-install daemon without HaRP at startup (IN-04).

    Without ``HP_SHARED_KEY`` the rebinding protection stays armed, and until issue #4 the
    allowlist behind it was localhost and nothing else: the ``Host`` header a proxy
    forwards is either the container name or, as measured in AIO, the public custom
    domain, and neither was in it. The lifecycle routes sit before the transport check, so
    the installation turns green and every ``/mcp`` request afterwards dies as a 421 that
    surfaces as one log line.

    Since :func:`~mcp_connector.config.deployment_hosts` the allowlist carries the public
    address of this deployment, so the trap is only still open when there is no such
    address to derive from. The warning is skipped whenever the question is already
    answered: a derived host, an allowlist of her own, the shared key that selects the
    HaRP path, or a disabled check.
    """
    source = os.environ if env is None else env
    if (source.get(config.ENV_HP_SHARED_KEY) or "").strip():
        return
    if (source.get(config.ENV_ALLOWED_HOSTS) or "").strip():
        return
    if config.deployment_hosts(source):
        return
    if not config.dns_rebinding_protection(env):
        return
    logger.warning(
        "%s is not set, %s is empty and no address of this deployment could be read from "
        "%s or %s. The Host check stays armed with the localhost default, so every /mcp "
        "request will answer 421. Set the public address of this app, which the allowlist "
        "is derived from, or set %s to the host name the proxy uses for this container "
        "(docs/exapp-install.md, pitfall 5).",
        config.ENV_HP_SHARED_KEY,
        config.ENV_ALLOWED_HOSTS,
        config.ENV_PUBLIC_URL,
        config.ENV_NEXTCLOUD_URL,
        config.ENV_ALLOWED_HOSTS,
    )


def _startup_client() -> httpx.AsyncClient:
    """A client for the one call this process makes before it serves anything.

    Deliberately not :func:`~mcp_connector.nextcloud.http.shared_client`: that one binds its
    connection pool to the event loop it is first used in, and the loop of the start time read
    is closed again as soon as :func:`asyncio.run` returns. A pool left behind in a dead loop
    is unusable in the loop uvicorn opens afterwards, and its sockets would never be closed
    either. The properties are the ones of the shared client, and a check in
    ``tests/unit/test_exapp_entry.py`` holds them equal so the two cannot drift apart: no
    redirects, the same timeouts, no cookie jar and our user agent.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0, read=30.0),
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
        cookies=NoCookieJar(),
    )


async def _admin_values(env: Mapping[str, str]) -> config_values.AdminValues:
    """The admin values of this installation, over a client that dies with this loop."""
    async with _startup_client() as client:
        return await config_values.admin_values(env=env, client=client)


async def _audit_startup(env: Mapping[str, str]) -> None:
    """Record the switching of the log, then give an idle store one chance to clean up.

    **Why the start is the moment.** D-15 asks that switching the log on or off leaves a
    trace of its own. An admin value only takes effect once this app has been disabled and
    enabled again, which stops and starts this container, so the start *is* the moment the
    change becomes real, and it is the one moment this app can observe. There is no callback:
    AppAPI's ``SetValueListener`` stores an admin value and tells nobody.

    **Why ``actor`` says unknown.** The same listener drops ``$event->getUser()`` for an admin
    form before anything of ours runs (app_api v34.0.3), so the administrator behind a switch
    cannot be named on this path. :func:`~mcp_connector.audit.record.note_switch` writes the
    fixed identifier for it, and its docstring carries the source (D-16).

    **Why a file that does not exist stays absent.** An installation that never switched the
    log on gets no ``audit.sqlite3``, not even an empty one with a schema in it: a file that
    exists says something happened, and nothing did.

    **Why the sweep runs here at all.** The expiry of D-11 rides on the write path, every nth
    row. A log that has been switched off has no write path any more, so without this one call
    its rows would sit out their retention window and stay forever. This is the only moment
    left that can take them, which is why it runs whenever the file was already there and not
    only while the log is on.
    """
    path = config.persistent_storage(env) / AUDIT_FILENAME
    existed = path.exists()
    enabled = config.audit_log_enabled(env)
    if not existed and not enabled:
        return

    store = AuditStore(path)
    last = await store.last_entry(CHAIN_INSTANCE, kind=KIND_SWITCH)
    # No switch row yet means the log has never been on: the shipped state is off (D-14), so
    # a start that finds nothing and is off has nothing to report, and one that finds nothing
    # and is on reports the change from that shipped state.
    known = last.outcome if last is not None else audit_record.SWITCH_OFF
    current = audit_record.SWITCH_ON if enabled else audit_record.SWITCH_OFF
    if known != current:
        await audit_record.note_switch(store, enabled=enabled, moment=int(time.time()))
    if existed:
        await store.sweep(
            moment=int(time.time()),
            retention_days=config.audit_retention_days(env),
            size_limit=config.audit_size_limit(env),
        )


def _record_the_switch(env: Mapping[str, str]) -> None:
    """Run :func:`_audit_startup` and let no failure of it cost this container its start.

    The same error model the recording path itself follows (D-13, fail open): a store that
    cannot be written must not stop this app from serving, because that would turn a full
    volume into an outage of every assistant. The line names the type of the failure and
    nothing else, since the message of a store error carries the path of the file (T-18-10).
    """
    try:
        asyncio.run(_audit_startup(env))
    except Exception as exc:
        logger.error(
            "the audit log did not record the state of its switch on this start: %s",
            type(exc).__name__,
        )


def _resolved_env() -> tuple[dict[str, str], frozenset[str]]:
    """The deploy environment with the values an administrator set in Nextcloud on top.

    Returned with the field ids that arrived and were refused, because the environment alone
    cannot tell "she set nothing" from "what she set is unusable": both are the same missing
    key. The one place that difference is worth a sentence is the setup state below (05-14,
    line B), and nothing else reads the second half.

    Resolved exactly once, here, and handed to every factory as a plain mapping. The
    alternative would be a read per request, and it is refused for three reasons.
    ``config.public_url`` is synchronous and pure, and every one of its callers
    (``metadata.py``, ``consent.py``, ``settings_form.py``, ``admin_settings.py`` and every
    form action of every page) would have to change signature to await something. A process
    wide cache with an expiry would be mutable module state, which D-20 forbids with exactly
    two named exceptions. And a read per request would be a second Nextcloud round trip on
    every request, which is the property SC 5 of phase 3 measured.

    The price is one step for the administrator: a changed value takes effect after the app is
    disabled and enabled again. That price is named in the description of the form field
    (plan 05-01), in the setup state of the connections page and in ``docs/oauth-setup.md``,
    and it is not hidden anywhere.

    Nothing is read outside the ExApp mode: without the AppAPI variables there is no channel
    to read over. A failure of the read is an empty overlay, so the deploy environment of an
    existing installation keeps working exactly as it did (T-05-20).

    One key of the result travels further than this mapping, and :func:`main` says why: the
    switch of TALK-04 is read by a tool, and a tool never sees this mapping.
    """
    env = dict(os.environ)
    if not config.exapp_configured(env):
        return env, frozenset()

    overlay, refused = asyncio.run(_admin_values(env))
    if overlay:
        # The names of the keys, never their values: they arrived over HTTP and one of them is
        # a list of client addresses (T-05-21). An administrator needs to see which source won.
        logger.info(
            "these values come from the administration settings of this app and win over the "
            "deploy environment: %s",
            ", ".join(sorted(overlay)),
        )
    return {**env, **overlay}, refused


def main() -> None:
    """Validate the deploy environment, then serve until the container stops."""
    configure_logging()

    for name in CONFLICTING_VARIABLES:
        if (os.environ.get(name) or "").strip():
            logger.error(
                "%s is set in an ExApp process. The ExApp mode takes its identity from "
                "AUTHORIZATION-APP-API only; a second credential channel would be a silent "
                "fallback (D-27). Remove the variable from the deploy environment.",
                name,
            )
            raise SystemExit(2)

    # Everything below reads this mapping and never os.environ again: the values an
    # administrator set in Nextcloud are part of the environment of this process from here on
    # (plan 05-04). The read happens after the refusal above, so a misconfigured process never
    # opens a socket, and before every check, so the checks judge the values that will be used.
    resolved, refused = _resolved_env()

    # The one exception to the sentence above, and it contradicts it on purpose, so it says
    # why (TALK-04, way A of 09-RESEARCH.md). A tool has no `resolved` mapping in its hand:
    # `ctx` carries headers and nothing else, a header is settable from outside, and a
    # security switch whose off state hangs on a header being scrubbed reliably is worse than
    # the activation cycle. So the resolved value of this one key goes back into the process
    # environment, where `config.talk_send_enabled` reads it per call, exactly as
    # `select_mode`, `static_bearer` and `exapp_configured` read the environment per call.
    # `os.environ` is not module state in the sense of D-20: it is the environment of this
    # process and not a dictionary of one of our modules, which is why
    # tests/contract/test_no_destructive_calls.py::ALLOWED_MODULE_STATE stays untouched at
    # its two entries. Exactly one key travels, never the whole overlay, so this exception
    # cannot grow by habit. The price is the known one: a changed value takes effect after
    # this app has been disabled and enabled once, the same price the five other values pay,
    # and it is named in the description of the form field, in docs/oauth-setup.md and in
    # the refusal sentence of the tool. The alternative, reading the value out of Nextcloud
    # per send, is refused: one more round trip per message, a second failure mode, and the
    # answer to a failed read would have to be fail closed, which contradicts "on by
    # default" on every network hiccup.
    if config.ENV_TALK_SEND in resolved:
        os.environ[config.ENV_TALK_SEND] = resolved[config.ENV_TALK_SEND]

    try:
        config.exapp_settings(resolved)
        # The place the OAuth store writes to, checked before the first request and not on
        # the first authorization: a missing or read only volume answers every question
        # correctly until the container restarts and then has lost every connection
        # (pitfall 12, T-03-15). The data key is not fetched here; that needs a running
        # event loop and a reachable Nextcloud, and the store asks for it when it opens.
        config.persistent_storage(resolved)
        # Directly behind the volume check, because it writes into that volume, and before
        # anything is built, because the state it records is the state the application below
        # is about to be built with (D-15, D-16). It never raises: see :func:`_record_the_switch`.
        _record_the_switch(resolved)
        # The one value an installation has to set (WR-09). It becomes the issuer, the audience
        # of every token, the resource_metadata pointer, the prefix of every form action and
        # the target of the consent redirect.
        #
        # Until plan 05-04 this was SystemExit(2), and that exit was the deadlock of a one
        # click installation: a store install in NC 34 sets no variable at all (05-RESEARCH,
        # pitfall 2), the process died on start, the app therefore never became `enabled`, the
        # enabled=1 hook never registered the admin form, and the administrator had no place to
        # enter the missing address. So the promise "no silent misconfiguration" is not kept by
        # refusing to run any more. It is kept by this error line and by the visible setup state
        # on the connections page, while the process stays alive long enough to be configured.
        #
        # No address is derived from NEXTCLOUD_URL here, deliberately (assumption A2): AppAPI
        # sets that variable with https replaced by http and it may be an internal address. A
        # derived value would be a silent default with broken discovery, which looks exactly
        # like a configured installation and is the failure this plan removes.
        if (
            config.exapp_configured(resolved)
            and not (resolved.get(config.ENV_PUBLIC_URL) or "").strip()
        ):
            app_id = (resolved.get(config.ENV_APP_ID) or "").strip()
            # Two states end here, and until plan 05-14 measured line B of its run they ended
            # in the same sentence: nothing was ever entered, or something was and
            # `config_values._public_url` refused it. The second one is the wrong thing to
            # tell an administrator who did fill the field in, because she then looks for an
            # empty field instead of at the value she typed. The warning of `_rejected` says
            # why the value was refused; this line says which of the two cases the setup
            # state is, and it names the value as little as that one does.
            state = (
                "the address stored in Nextcloud was refused, so none is in force (the "
                "warning above says why)"
                if config_values.PUBLIC_URL_KEY in refused
                else "no public address is stored in Nextcloud either"
            )
            logger.error(
                "%s is not set and %s. Until a usable one is set, every discovery document, "
                "the audience of every token and the consent redirect name %s, and no client "
                'can connect. Set it in "%s", then disable and enable this app again '
                "(occ app_api:app:disable %s, occ app_api:app:enable %s). This process keeps "
                "serving on purpose, so that form exists at all; the connections page says "
                "the same thing.",
                config.ENV_PUBLIC_URL,
                state,
                config.DEFAULT_PUBLIC_URL,
                strings.ADMIN_SETTINGS_PLACE,
                app_id,
                app_id,
            )
    except ToolError as exc:
        logger.error("%s %s", exc.message, exc.hint)
        raise SystemExit(2) from None

    # The public URL is what the authorization server calls itself, and the SDK refuses an
    # issuer that is not https unless it is loopback. That refusal is the one failure of this
    # function that is recoverable, so this build stands in a try of its own and catches the
    # type that means exactly it.
    #
    # It used to catch every ToolError of the build, which was true about today (the issuer
    # refusal in `provider.auth_routes` was the only one raised at build time) and an
    # assumption about tomorrow: a second source would have been logged as an address
    # problem, would have had a possibly good address dropped and would have ended in a
    # second build with a confusing double message. `IssuerRefused` is the marker instead of
    # that assumption (IN-06); everything else falls through to the SystemExit below.
    try:
        app = build_exapp_app(resolved)
    except IssuerRefused as exc:
        # CR-01 of 05-REVIEW.md, gap 1 of 05-VERIFICATION.md. An exit here is the same
        # deadlock plan 05-04 removed, only reachable through the form of plan 05-01: an app
        # that never becomes `enabled` again gets no admin form served by AppAPI, so the wrong
        # value is correctable by hand in oc_appconfig_ex and nowhere else, while the
        # container restarts forever. The promise "no silent misconfiguration" is kept here by
        # this error line plus the visible setup state of the connections page, not by dying.
        #
        # Nothing is deleted or written back to Nextcloud in this branch, on purpose (T-05-44):
        # a value the administrator typed stays where she typed it, so she finds it in the form
        # and corrects it instead of silently losing what she entered.
        #
        # Both places are named, and that is IN-02 of the re-review. The line used to say "the
        # stored value is kept ... correct it where it was entered" and point at the form
        # alone. Since the prevention half of CR-01 refuses an unusable form value in
        # `config_values._public_url`, the case that really reaches this branch is the other
        # one: a deploy variable, which nothing validates. An administrator sent to the form
        # then looks for a stored value that is not there. Naming both sources with the rule
        # between them is true whichever of the two it was, and the INFO line of
        # `_resolved_env` above says which one won on this start.
        #
        # The value itself is never named: it may have come out of the form and travelled over
        # HTTP (T-05-21), and this log is read by everyone who reads container logs.
        app_id = (resolved.get(config.ENV_APP_ID) or "").strip()
        resolved.pop(config.ENV_PUBLIC_URL, None)
        logger.error(
            "%s %s Nothing is deleted in Nextcloud, so every value stays where it was set. "
            'Correct the deploy variable %s, or enter a usable address in "%s" (a stored '
            "value wins over the variable), then disable and enable this app again "
            "(occ app_api:app:disable %s, occ app_api:app:enable %s). This process keeps "
            "serving with the documented default in the meantime; the connections page "
            "says the same thing.",
            exc.message,
            exc.hint,
            config.ENV_PUBLIC_URL,
            strings.ADMIN_SETTINGS_PLACE,
            app_id,
            app_id,
        )
        try:
            # Exactly one more attempt, and with the address gone: config.public_url answers
            # the loopback default now, which the SDK accepts. A build that fails again fails
            # for a different reason, and that is not something to retry.
            app = build_exapp_app(resolved)
        except ToolError as second:
            logger.error("%s %s", second.message, second.hint)
            raise SystemExit(2) from None
    except ToolError as other:
        # Any other build time failure: reported as itself and ended, exactly like the
        # checks above it. Dropping the public address would fix none of them and would
        # hide what really happened behind a second, wrong message (IN-06).
        logger.error("%s %s", other.message, other.hint)
        raise SystemExit(2) from None

    if (resolved.get(config.ENV_HP_SHARED_KEY) or "").strip():
        # HaRP with the FRP tunnel: the unix socket is the transport, frpc runs beside us.
        socket_path = resolved.get(config.ENV_HP_EXAPP_SOCK) or DEFAULT_EXAPP_SOCK
        logger.info("MCP Connector is serving as an ExApp on %s", socket_path)
        uvicorn.run(app, uds=socket_path)
        return

    _warn_when_the_host_check_is_a_trap(resolved)

    host = resolved.get(config.ENV_APP_HOST) or "127.0.0.1"
    try:
        port = int(resolved[config.ENV_APP_PORT])
    except (KeyError, ValueError):
        logger.error(
            "%s is not set to a port number. The AppAPI deploy daemon sets it when it "
            "starts the container; start the process with it or set %s for a HaRP daemon.",
            config.ENV_APP_PORT,
            config.ENV_HP_SHARED_KEY,
        )
        raise SystemExit(2) from None

    logger.info("MCP Connector is serving as an ExApp on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

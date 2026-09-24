"""Console script ``nc-mcp-oauth``: the MCP server with its own OAuth, without AppAPI.

The fifth operating mode of the same code base. It serves the same MCP endpoint as the
ExApp, the same authorization server and the same consent screen, for a Nextcloud that
this process reaches over HTTPS like any other client. What AppAPI provides in the ExApp
comes from explicit configuration here:

* the Nextcloud (``NC_MCP_URL``) and the public address of this app (``NC_MCP_PUBLIC_URL``,
  HTTPS, because the browser identity lives in ``__Host-`` cookies),
* the store directory and the data key file (``NC_MCP_OAUTH_STORAGE_DIR``,
  ``NC_MCP_OAUTH_DATA_KEY_FILE``), strict: no fallback, no generated key,
* the independent browser identity of the consent decision (CR-01): an OIDC single sign-on
  that the Nextcloud itself trusts through ``user_oidc`` (``NC_MCP_OIDC_*``).

``/mcp`` accepts nothing but a verified OAuth bearer (:class:`RequireOAuthBearer`). The
browser onboarding, the connections page, the purge and the audit routes of the ExApp are
not attached: each of them relies on AppAPI identity or occ.

``NC_MCP_AUTH_MODE=oauth`` selects this mode for the credential layer. ``main`` refuses a
start next to an ExApp environment, a static bearer or a configured app password, for the
reason ``entry_exapp`` gives: a second credential channel would be a silent fallback.
"""

import logging
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import __version__, config
from .errors import ToolError
from .exapp.middleware import RequireOAuthBearer
from .exapp.responses import NO_STORE
from .nextcloud.http import configure_logging
from .nextcloud.target import NextcloudTarget
from .oauth import chain, crypto, exchange_binding, exchange_enroll, oidc, throttle
from .oauth.consent import consent_routes
from .oauth.metadata import OPENID_CONFIGURATION_SUFFIX, metadata_routes
from .oauth.oidc_identity import OidcBrowserIdentitySource
from .oauth.oidc_routes import OIDC_CALLBACK_PATH, oidc_routes
from .oauth.provider import NextcloudOAuthProvider, auth_routes
from .oauth.registry import client_policy
from .oauth.store import explicit_store_opener
from .oauth.verifier import StoreTokenVerifier
from .server import mcp

__all__ = ["StandaloneSettings", "build_oauth_app", "load_settings", "main"]

MCP_PATH = "/mcp"

#: Every browser and OAuth route reads at most this much of a body. The MCP route keeps the
#: limits of the SDK; the routes attached here are forms and token requests.
MAX_BROWSER_BODY_BYTES = 64 * 1024

DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_BIND_PORT = 8765

#: Variables that would authenticate a caller or select another credential mode.
CONFLICTING_VARIABLES = (
    config.ENV_STATIC_BEARER,
    config.ENV_APP_PASSWORD,
    config.ENV_USER,
    config.ENV_APP_ID,
    config.ENV_APP_SECRET,
)

_SECRET_FORBIDDEN_BITS = stat.S_IRWXO | stat.S_IWGRP
_SECRET_MAX_BYTES = 4096

_HINT = "See docs/standalone-oauth.md for the variables of the standalone OAuth deployment."

logger = logging.getLogger("mcp_connector.entry_oauth")


@dataclass(frozen=True, slots=True)
class StandaloneSettings:
    """Everything the standalone application needs, validated once at startup."""

    nextcloud: NextcloudTarget
    public_url: str
    storage_directory: Path
    data_key_file: Path
    oidc: oidc.OidcSettings
    #: The validated token exchange configuration of milestone v1.6, or ``None`` for the
    #: factory state. It travels with the settings so that the application built from them
    #: reads the namespace at the place every other value is read as well, and an armed
    #: answer here decides: :func:`build_oauth_app` builds its chain from this field and
    #: never disarms it. What that function still reads for itself is the environment it is
    #: handed, and it reads it to refuse a half configuration of that environment and to arm
    #: a path these settings knew nothing about, never to replace an answer they carry.
    exchange: chain.ExchangeConfig | None = None


def load_settings(env: Mapping[str, str] | None = None) -> StandaloneSettings:
    """Read and validate the standalone configuration, or raise a named :class:`ToolError`."""
    source = os.environ if env is None else env
    if not config.oauth_configured(source):
        raise ToolError(
            message=f"{config.ENV_AUTH_MODE} is not '{config.AUTH_MODE_OAUTH}'.", hint=_HINT
        )
    for name in CONFLICTING_VARIABLES:
        if (source.get(name) or "").strip():
            raise ToolError(
                message=f"{name} is set in the standalone OAuth process.",
                hint=(
                    "This mode authenticates every MCP call with its own OAuth tokens only. "
                    f"Remove {name}; a second credential channel would be a silent fallback."
                ),
            )
    nextcloud = NextcloudTarget.from_url(config.load_base_url(source))
    public_url = _required(source, config.ENV_PUBLIC_URL).rstrip("/")
    if not public_url.startswith("https://"):
        raise ToolError(
            message=f"{config.ENV_PUBLIC_URL} must be an https address.",
            hint="The browser identity uses __Host- cookies, which browsers only keep over HTTPS.",
        )
    storage = config.storage_directory(
        source.get(config.ENV_OAUTH_STORAGE_DIR) or "",
        variable=config.ENV_OAUTH_STORAGE_DIR,
        hint=_HINT,
    )
    key_file = Path(_required(source, config.ENV_OAUTH_DATA_KEY_FILE))
    provider_raw = _required(source, config.ENV_OIDC_PROVIDER_ID)
    if not provider_raw.isdigit():
        raise ToolError(
            message=f"{config.ENV_OIDC_PROVIDER_ID} must be a positive number.", hint=_HINT
        )
    algorithms_raw = (source.get(config.ENV_OIDC_ALGORITHMS) or "").strip()
    algorithms = (
        tuple(part.strip() for part in algorithms_raw.split(",") if part.strip())
        if algorithms_raw
        else oidc.DEFAULT_ALGORITHMS
    )
    secret_file = (source.get(config.ENV_OIDC_CLIENT_SECRET_FILE) or "").strip()
    try:
        settings = oidc.OidcSettings(
            issuer=_required(source, config.ENV_OIDC_ISSUER),
            client_id=_required(source, config.ENV_OIDC_CLIENT_ID),
            redirect_uri=f"{public_url}{OIDC_CALLBACK_PATH}",
            provider_id=int(provider_raw),
            strategy=_required(source, config.ENV_OIDC_MAPPING),
            client_secret=read_secret_file(Path(secret_file)) if secret_file else None,
            algorithms=algorithms,
        )
    except ValueError as exc:
        raise ToolError(message=f"The OIDC configuration is invalid: {exc}", hint=_HINT) from None
    # The token exchange path of milestone v1.6, validated with the other values and before
    # anything is built: armed without its required values, or configured without the switch
    # that arms it, and this process does not start (T-22-01, T-22-02). The ToolError falls
    # into the existing handler of ``main`` and becomes a named message with exit code 2.
    exchange = chain.load_exchange_config(source)
    return StandaloneSettings(
        nextcloud=nextcloud,
        public_url=public_url,
        storage_directory=storage,
        data_key_file=key_file,
        oidc=settings,
        exchange=exchange,
    )


def read_secret_file(path: Path) -> str:
    """The OIDC client secret from a mounted file; the content is never part of an error."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ToolError(
            message="The OIDC client secret file is not readable.", hint=_HINT
        ) from None
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise ToolError(message="The OIDC client secret path is not a file.", hint=_HINT)
        if os.name != "nt" and status.st_mode & _SECRET_FORBIDDEN_BITS:
            raise ToolError(
                message="The OIDC client secret file permissions are too open.", hint=_HINT
            )
        raw = os.read(descriptor, _SECRET_MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) > _SECRET_MAX_BYTES:
        raise ToolError(message="The OIDC client secret file is too large.", hint=_HINT)
    try:
        secret = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise ToolError(message="The OIDC client secret file is not text.", hint=_HINT) from None
    if not secret:
        raise ToolError(message="The OIDC client secret file is empty.", hint=_HINT)
    return secret


def _announce_exchange_path(loaded: chain.ExchangeConfig | None) -> None:
    """One line when the path is armed, and nothing at all when it is not.

    Called from :func:`build_oauth_app` and from nowhere else, which is what makes "one line
    per start" true rather than intended (WR-01 of 22-REVIEW.md). It used to run in
    :func:`load_settings` as well, and ``main`` calls both, so an armed standalone start
    wrote the line twice: in the one log an auditor later counts armed starts in.
    :func:`build_oauth_app` is where the two call paths meet, and ``main`` reaches it once.

    Named variables and never values: the configuration can name an internal provider, and
    a container log is read by everyone who reads container logs (T-22-04).
    """
    if loaded is None:
        return
    logger.info(
        "the token exchange path is armed; tokens of the configured provider are verified "
        "in addition to the ones this app issued itself"
    )


def build_oauth_app(
    env: Mapping[str, str] | None = None, *, settings: StandaloneSettings | None = None
) -> Starlette:
    """The standalone application: MCP behind the bearer boundary, OAuth, consent, SSO."""
    resolved = settings if settings is not None else load_settings(env)
    exchange_config = resolved.exchange
    if settings is not None:
        # The reader is a pure function of its environment and costs nothing, so it runs on
        # both call paths into this function: through ``load_settings`` above for ``main``,
        # and here for a caller that builds the application with settings in hand. That
        # caller must not be able to skip the refusal of a half configured path, which is
        # the whole reason this second read exists.
        #
        # What it may do with its answer is bounded in one direction (WR-02 of
        # 22-REVIEW.md). It used to overwrite the field unconditionally, so a caller who
        # built settings from mapping A and called this without ``env`` got an application
        # without a chain over a clean ``os.environ``: armed in hand, unarmed in service,
        # no refusal and no line. That is the silent half state T-22-02 is written against,
        # one level up. So the read can arm a path the settings did not know about, and it
        # can never disarm one they did: the answer that travelled with the settings wins
        # wherever it exists. For ``main`` both sources are the same mapping anyway.
        reread = chain.load_exchange_config(env)
        if exchange_config is None:
            exchange_config = reread
    # After the last line that can still change the answer, and on both call paths: this is
    # where they meet, and ``main`` passes here exactly once per start (WR-01).
    _announce_exchange_path(exchange_config)
    config.files_root(env)

    security = TransportSecuritySettings(
        allowed_hosts=config.allowed_hosts(env),
        enable_dns_rebinding_protection=config.dns_rebinding_protection(env),
    )
    app = mcp.streamable_http_app(transport_security=security)

    async def data_key() -> bytes:
        return crypto.file_key(resolved.data_key_file)

    store = explicit_store_opener(
        directory=lambda: resolved.storage_directory, key=data_key, strict=True
    )
    policy = client_policy(env)
    provider = NextcloudOAuthProvider(
        nextcloud=resolved.nextcloud, env=env, policy=policy, store_provider=store
    )
    verifier = StoreTokenVerifier(store_provider=store, get_client=provider.get_client, env=env)
    # The account source of this mode (CRED-02) exists only while the path is armed, and it
    # is built from the very store opener the provider and the verifier use, not from a
    # second one: a second instance would be a second view on the same revocation.
    accounts = exchange_binding.BoundAccounts(store) if exchange_config is not None else None
    # The one place this deployment hangs the chain in, and in the factory state the very
    # object above rather than a wrapper around it. The revocation goes to the chain, not to
    # the verifier inside it: the exchange half caches signature keys for five minutes, and a
    # rotated key must not outlive the revocation that emptied the other half.
    #
    # ``refusals=None``, and that is a decision of plan 24-04 rather than an omission
    # (AUDIT-07, T-24-21). The ExApp mode writes one row per refused exchange attempt; this
    # mode writes none, because it has none of the three things that make such a row worth
    # anything. It builds no ``audit/record.Recorder``, so no tool call of this process is
    # recorded either and the switch of D-14 decides nothing here today: a wire that made it
    # decide refusals alone would give one variable two different meanings in two modes. It
    # runs no sweep, because the expiry of D-11 rides on the recorder's write path and the
    # other sweep is ``entry_exapp._audit_startup``, so the rows would sit out neither the
    # retention window nor the size limit that ``docs/privacy.md`` promises them. And it has
    # no occ and none of the audit routes, so nothing in this mode could read them back.
    # Together that would be a file that grows on a path a stranger drives, that nobody
    # sweeps and that nobody reads. What would change this is an audit path for the fifth
    # operating mode, and that is a phase of its own, not a keyword argument here.
    boundary = chain.build_chain(
        verifier, env=env, config=exchange_config, accounts=accounts, refusals=None
    )
    provider.on_revocation(boundary.invalidate)

    counters = throttle.Throttle()
    browser_identity = OidcBrowserIdentitySource(store=store)
    identity_client = oidc.OidcClient(resolved.oidc)

    async def access_disabled(principal: str) -> bool:
        opened = await store()
        return await opened.access_disabled(principal)

    guarded = 0
    for route in app.router.routes:
        if isinstance(route, Route) and route.path == MCP_PATH:
            route.app = RequireOAuthBearer(
                route.app, env, token_verifier=boundary, access_check=access_disabled
            )
            if exchange_config is not None:
                # Outside the boundary, for the reason the ExApp entry point states at
                # the same line: the refusal this counts is the 401 the boundary writes,
                # and a wrapper inside it would see none of them (EXCH-05). While the
                # path is disarmed nothing is wrapped at all, so the off state is the
                # same structure as before this milestone and not merely the same
                # behaviour.
                route.app = throttle.Throttled(
                    route.app,
                    counters,
                    throttle.CLASS_EXCHANGE,
                    machine=True,
                    env=env,
                    limit=throttle.EXCHANGE_LIMIT,
                    applies=chain.exchange_shaped_request,
                )

            guarded += 1
    if guarded != 1:
        raise RuntimeError(
            f"the standalone application has {guarded} guarded {MCP_PATH} routes instead of one"
        )

    app.router.routes.append(Route("/health", _health, methods=["GET"]))
    discovery = metadata_routes(
        env, dcr_enabled=policy.dcr_enabled, cimd_enabled=policy.cimd_enabled
    )
    if not urlsplit(resolved.public_url).path.strip("/"):
        # On its own host the RFC 8414 path is reachable at the domain root, so the OpenID
        # Connect variant is not needed to find the document. Served anyway, it tells clients
        # that this is an OpenID provider, which it is not (no ID token, no userinfo), and
        # ChatGPT then turns on its OIDC mode for the connector. Under a path prefix it stays,
        # because there it is the variant a client finds without help.
        discovery = [
            route
            for route in discovery
            if not (isinstance(route, Route) and route.path == OPENID_CONFIGURATION_SUFFIX)
        ]
    # The enrollment page of the exchange binding (CRED-02, plan 23-06) exists only while
    # the path is armed, and in the off state the address does not exist at all rather than
    # answering emptily: an address that is not there is the smallest attack surface, and
    # the factory state stays the very structure of every release before this milestone,
    # not merely the same behaviour (the rule of the throttle wrapper above).
    # ``end_connection`` is the provider's, so the withdrawal runs over the one revocation
    # path of this deployment and empties the verifier caches with it (T-04-35).
    enrollment = (
        exchange_enroll.exchange_routes(
            env,
            nextcloud=resolved.nextcloud,
            store_provider=store,
            browser_identity=browser_identity,
            end_connection=provider.end_connection,
            acting_party=", ".join(exchange_config.settings.azp_allowed),
            throttle=counters,
        )
        if exchange_config is not None
        else []
    )
    for route in (
        *discovery,
        *auth_routes(env, provider=provider, throttle=counters),
        *consent_routes(
            env,
            provider=provider,
            browser_identity=browser_identity,
            nextcloud=resolved.nextcloud,
            throttle=counters,
        ),
        *oidc_routes(env, provider=provider, client=identity_client, throttle=counters),
        *enrollment,
    ):
        if isinstance(route, Route):
            route.app = BodyLimit(route.app, MAX_BROWSER_BODY_BYTES)
        app.router.routes.append(route)
    return app


async def _health(request: Request) -> JSONResponse:
    """Liveness probe, the same dull answer ``entry_http`` gives: status and version only."""
    return JSONResponse({"status": "ok", "version": __version__}, headers=NO_STORE)


class RedactCallbackQuery(logging.Filter):
    """Drop the query string of the OIDC callback from uvicorn's access log.

    uvicorn logs every request with its full path and query. The callback query carries a
    single-use authorization code and the sign-in state, so the line keeps the path and
    status and replaces the query with a marker. Other paths are left as they are.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            path = args[2]
            if path.split("?", 1)[0] == OIDC_CALLBACK_PATH and "?" in path:
                record.args = (*args[:2], f"{OIDC_CALLBACK_PATH}?[redacted]", *args[3:])
        return True


def redact_access_log() -> None:
    """Install :class:`RedactCallbackQuery` on uvicorn's access logger, once."""
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactCallbackQuery) for item in access.filters):
        access.addFilter(RedactCallbackQuery())


class BodyLimit:
    """Refuse a request body larger than ``limit`` before the route reads it.

    An announced length above the limit is refused at once; a chunked or understated body
    is cut off while it streams. The answer is a bare 413 with ``no-store``.
    """

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self._app = app
        self._limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    announced = int(value)
                except ValueError:
                    announced = self._limit + 1
                if announced > self._limit:
                    await _too_large(scope, receive, send)
                    return
        seen = 0
        too_large = False

        async def limited() -> Message:
            # Past the limit the route sees a disconnect, whatever its parser does with it,
            # and whatever it answers is replaced by the 413 below.
            nonlocal seen, too_large
            if too_large:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self._limit:
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        async def watch(message: Message) -> None:
            if not too_large:
                await send(message)

        try:
            await self._app(scope, limited, watch)
        except Exception:
            if not too_large:
                raise
        if too_large:
            await _too_large(scope, receive, send)


async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
    await Response(status_code=413, headers=NO_STORE)(scope, receive, send)


def _required(source: Mapping[str, str], name: str) -> str:
    value = (source.get(name) or "").strip()
    if not value:
        raise ToolError(message=f"{name} is not set.", hint=_HINT)
    return value


def main() -> None:
    """Validate the configuration, check the data key, then serve until stopped."""
    configure_logging()
    try:
        settings = load_settings()
        crypto.file_key(settings.data_key_file)
        app = build_oauth_app(settings=settings)
    except ToolError as exc:
        logger.error("%s %s", exc.message, exc.hint)
        raise SystemExit(2) from None
    host = (os.environ.get(config.ENV_BIND_HOST) or DEFAULT_BIND_HOST).strip()
    port_raw = (os.environ.get(config.ENV_BIND_PORT) or str(DEFAULT_BIND_PORT)).strip()
    if not port_raw.isdigit() or not 0 < int(port_raw) < 65536:
        logger.error("%s must be a port number.", config.ENV_BIND_PORT)
        raise SystemExit(2)
    redact_access_log()
    uvicorn.run(app, host=host, port=int(port_raw), proxy_headers=True, server_header=False)

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
from .oauth import crypto, oidc, throttle
from .oauth.consent import consent_routes
from .oauth.metadata import metadata_routes
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
    return StandaloneSettings(
        nextcloud=nextcloud,
        public_url=public_url,
        storage_directory=storage,
        data_key_file=key_file,
        oidc=settings,
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


def build_oauth_app(
    env: Mapping[str, str] | None = None, *, settings: StandaloneSettings | None = None
) -> Starlette:
    """The standalone application: MCP behind the bearer boundary, OAuth, consent, SSO."""
    resolved = settings if settings is not None else load_settings(env)
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
    provider.on_revocation(verifier.invalidate)
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
                route.app, env, token_verifier=verifier, access_check=access_disabled
            )
            guarded += 1
    if guarded != 1:
        raise RuntimeError(
            f"the standalone application has {guarded} guarded {MCP_PATH} routes instead of one"
        )

    app.router.routes.append(Route("/health", _health, methods=["GET"]))
    for route in (
        *metadata_routes(env, dcr_enabled=policy.dcr_enabled, cimd_enabled=policy.cimd_enabled),
        *auth_routes(env, provider=provider, throttle=counters),
        *consent_routes(
            env,
            provider=provider,
            browser_identity=browser_identity,
            nextcloud=resolved.nextcloud,
            throttle=counters,
        ),
        *oidc_routes(env, provider=provider, client=identity_client, throttle=counters),
    ):
        if isinstance(route, Route):
            route.app = BodyLimit(route.app, MAX_BROWSER_BODY_BYTES)
        app.router.routes.append(route)
    return app


async def _health(request: Request) -> JSONResponse:
    """Liveness probe, the same dull answer ``entry_http`` gives: status and version only."""
    return JSONResponse({"status": "ok", "version": __version__}, headers=NO_STORE)


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
    uvicorn.run(app, host=host, port=int(port_raw), proxy_headers=True, server_header=False)

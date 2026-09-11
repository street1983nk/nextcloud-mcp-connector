"""ASGI entry point: the MCP server over Streamable HTTP (SRV-01, SRV-05).

Start it with::

    uv run uvicorn mcp_connector.entry_http:app --host 127.0.0.1 --port 8765

One endpoint, ``POST /mcp``, serves both protocol eras. The SDK routes each request by
its ``MCP-Protocol-Version`` header, so a 2026 client and a client on SDK 1.29 are served
from the same process without configuration, and nothing in this module tries to select
an era. That is not a convenience, it is the whole reason the class of failure behind
nextcloud/context_agent#227 cannot occur here, and ``tests/compat/test_client_matrix.py``
keeps it that way.

Two decisions worth the comment they cost:

* ``transport_security`` is the go-live gate. Without it the app answers **421
  Misdirected Request** to every Host header that is not localhost, the check runs before
  any MCP code, and the reason appears only as one line in the server log while the
  client sees a generic transport error. ``--host 0.0.0.0`` allowlists nothing: bind
  address and Host allowlist are unrelated. Hence ``NC_MCP_ALLOWED_HOSTS`` from day one,
  and since issue #4 the public address of the deployment is in the allowlist without it:
  ``config.allowed_hosts`` derives the host of ``NC_MCP_PUBLIC_URL`` as well.
* ``/health`` is a custom route, and custom routes are never authenticated, even when the
  rest of the server is. That is exactly right for a health probe and forbidden for
  anything else, so this module still registers exactly one. The AppAPI lifecycle routes
  of phase 2 are deliberately not registered here: ``entry_exapp.build_exapp_app``
  attaches them to its own application object, so this standalone mode stays exactly the
  server phase 1 shipped (D-23).

Not built here on purpose: mounting this app into a host application. A mounted sub-app
gets no lifespan of its own, so the host would have to enter ``mcp.session_manager.run()``
in its own lifespan or fail on the first request. The ExApp shell of phase 2 avoids that
question instead of answering it: it builds its own top level application and adds the
three lifecycle routes to it, without FastAPI and without a second framework layer
(D-24).
"""

from collections.abc import Mapping

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__, config
from .errors import ToolError
from .nextcloud.http import configure_logging
from .server import mcp

__all__ = ["app", "build_app"]

configure_logging()


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness probe for deployments and for the client matrix test.

    Deliberately unauthenticated and deliberately dull: status and version, no
    configuration, no host names, no mode (threat T-01-29).
    """
    return JSONResponse({"status": "ok", "version": __version__})


def build_app(env: Mapping[str, str] | None = None) -> Starlette:
    """Build the ASGI application with the host allowlist of this deployment.

    The first thing it does is refuse to be an ExApp by accident (WR-03). ``APP_ID`` and
    ``APP_SECRET`` are the only two mode switches without an ``NC_MCP_`` prefix, because
    the AppAPI deploy daemon dictates their names, and they are common enough that a base
    image, a systemd drop-in or a CI variable can set them for something else entirely.
    ``config.select_mode`` then picks the ExApp mode per request, the credential source
    changes from the Basic header of the caller to an ``AUTHORIZATION-APP-API`` header
    this deployment never receives, and every user is locked out with "no valid AppAPI
    authentication" although nothing in the configuration of this server was touched.
    ``entry_exapp.main`` guards the opposite direction the same way, with exit code 2.
    """
    if config.exapp_configured(env):
        raise ToolError(
            message=(
                f"{config.ENV_APP_ID} and {config.ENV_APP_SECRET} are set in a standalone "
                "HTTP process."
            ),
            hint=(
                "Those two select the ExApp credential mode, so this server would look for "
                "an AppAPI header it never gets and lock out every user. Unset them here, "
                "or run the entry point AppAPI deploys, 'nc-mcp-exapp', which serves the "
                "same MCP endpoint plus the three lifecycle routes."
            ),
        )
    security = TransportSecuritySettings(
        allowed_hosts=config.allowed_hosts(env),
        enable_dns_rebinding_protection=config.dns_rebinding_protection(env),
    )
    return mcp.streamable_http_app(transport_security=security)


#: The application uvicorn imports. Built from the process environment at import time.
app = build_app()

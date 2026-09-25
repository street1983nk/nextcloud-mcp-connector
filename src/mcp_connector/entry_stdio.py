"""Console script ``nc-mcp``: the MCP server over stdio (SRV-02, D-02).

In stdio mode stdout *is* the wire (pitfall 7). Therefore: no ``print`` anywhere in the
package, no output at import time, every diagnostic through logging to stderr. The
credentials are validated before ``mcp.run()`` so a misconfigured environment fails with
one readable line instead of a protocol error in the client.

The security boundary of this transport is the process that starts the server: there are
no headers and no Authorization, the app password comes from the environment (D-11).
"""

import logging

from . import config
from .config import load_stdio_credentials
from .errors import ToolError
from .nextcloud.http import configure_logging
from .server import mcp

logger = logging.getLogger("mcp_connector.entry_stdio")


def main() -> None:
    """Validate the environment, then serve MCP over stdio until stdin closes."""
    configure_logging()
    try:
        load_stdio_credentials()
        # Validate the optional file sandbox before the stdio wire starts.
        config.files_root()
    except ToolError as exc:
        logger.error("%s %s", exc.message, exc.hint)
        raise SystemExit(2) from None

    logger.info("MCP Connector is serving over stdio")
    mcp.run()


if __name__ == "__main__":
    main()

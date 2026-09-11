"""MCP Connector for Nextcloud.

Import side effects are forbidden in this package: in stdio mode stdout is the
protocol channel, so a stray print would corrupt the transport.
"""

__version__ = "0.1.13"

__all__ = ["__version__"]

"""The Nextcloud target of an AppAPI deployment, resolved at the composition root.

AppAPI tells this process where its Nextcloud lives through ``NEXTCLOUD_URL``. That read
happens here, once, when :func:`mcp_connector.entry_exapp.build_exapp_app` assembles the
application; the login flow, the consent surface, the onboarding and the purge receive the
resulting :class:`~mcp_connector.nextcloud.target.NextcloudTarget` and never read the
environment for it themselves.
"""

from collections.abc import Mapping

from .. import config
from ..nextcloud.target import NextcloudTarget

__all__ = ["exapp_target"]


def exapp_target(env: Mapping[str, str] | None = None) -> NextcloudTarget:
    """The Nextcloud of this ExApp, raising the named ``ToolError`` of the deploy check."""
    return NextcloudTarget.from_url(config.exapp_settings(env).base_url)

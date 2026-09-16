"""The one Nextcloud instance a deployment signs users in against, as an explicit value.

The Login Flow v2 start, its poll, the app password revocation and the check of the sign in
link all address the same Nextcloud. Until the standalone OAuth work each of them read the
base URL from :func:`mcp_connector.config.exapp_settings` on its own, which tied the whole
browser half of the authorization server to the AppAPI deploy environment.

A deployment now resolves its target once, when it assembles the application, and hands the
same object to every consumer. No consumer reads the environment for it, and no request
value can select or replace it: the target is administrator configuration, like the public
URL of this app.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from .. import config

__all__ = ["NextcloudTarget"]


@dataclass(frozen=True, slots=True)
class NextcloudTarget:
    """A validated Nextcloud base URL: http or https, a host, an optional subpath.

    Construct it with :meth:`from_url`. The direct constructor accepts only a value that is
    already in the normalized form, so an object of this type never carries a trailing
    slash, whitespace, a foreign scheme or credentials in the URL.
    """

    base_url: str

    def __post_init__(self) -> None:
        if config.normalize_base_url(self.base_url) != self.base_url:
            raise ValueError("a Nextcloud target needs a normalized base URL")

    @classmethod
    def from_url(cls, raw: str) -> "NextcloudTarget":
        """Normalize and validate a configured address, naming the problem when it fails."""
        return cls(base_url=config.normalize_base_url(raw))

    @property
    def netloc(self) -> str:
        """Host and port of the target, as a sign in link has to carry them."""
        return urlsplit(self.base_url).netloc

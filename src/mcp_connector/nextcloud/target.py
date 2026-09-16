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
from ..errors import ToolError

__all__ = ["NextcloudTarget"]


@dataclass(frozen=True, slots=True)
class NextcloudTarget:
    """A validated Nextcloud base URL: http or https, a host, an optional subpath.

    Construct it with :meth:`from_url`. The direct constructor accepts only a value that is
    already in the normalized form, so an object of this type never carries a trailing
    slash, whitespace, a foreign scheme, credentials, a query or a fragment. The last two
    matter because every consumer appends a path to this value as text: a ``?`` or ``#``
    in the base would swallow that path.
    """

    base_url: str

    def __post_init__(self) -> None:
        # One exception type for every refusal of the direct constructor; the named
        # ToolError with a hint belongs to from_url, which reads configuration.
        try:
            normalized = config.normalize_base_url(self.base_url)
        except ToolError:
            raise ValueError("a Nextcloud target needs a valid base URL") from None
        if normalized != self.base_url or _has_query_or_fragment(self.base_url):
            raise ValueError("a Nextcloud target needs a normalized base URL")

    @classmethod
    def from_url(cls, raw: str) -> "NextcloudTarget":
        """Normalize and validate a configured address, naming the problem when it fails."""
        normalized = config.normalize_base_url(raw)
        if _has_query_or_fragment(normalized):
            raise ToolError(
                message="The Nextcloud address must not contain a query or a fragment.",
                hint="Use the plain base URL, for example https://cloud.example.com/nextcloud.",
            )
        return cls(base_url=normalized)

    @property
    def netloc(self) -> str:
        """Host and port of the target, as a sign in link has to carry them."""
        return urlsplit(self.base_url).netloc


def _has_query_or_fragment(url: str) -> bool:
    """Also true for an empty query or fragment: ``https://host/nc?`` is not a base URL."""
    return "?" in url or "#" in url

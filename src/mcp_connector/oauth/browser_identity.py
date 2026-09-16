"""The independent authority that binds a consent decision to one account.

The Login Flow v2 result proves which account produced an app password.  It does not
prove who is pressing the consent button, because the party that started a relayed flow
also holds the flow id and its anti-forgery value.  A deployment therefore supplies one
independent browser identity source to the consent boundary (CR-01).

This module defines only that boundary.  Deployment-specific implementations live with
their trust anchor: AppAPI in :mod:`mcp_connector.exapp.browser_identity`, and the future
standalone OIDC implementation in its own adapter.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from starlette.requests import Request

__all__ = ["BrowserIdentitySource", "IdentityStep"]


@dataclass(frozen=True, slots=True)
class IdentityStep:
    """A step this browser has to take before the consent screen offers a decision.

    ``action_path`` is a route of this application the step posts to, ``fields`` are the
    hidden values of that form. A source that needs no step (AppAPI) never returns one.
    """

    action_path: str
    fields: Mapping[str, str] = field(default_factory=dict)


class BrowserIdentitySource(Protocol):
    """Decide whether this browser is independently known as one expected account.

    Implementations return ``False`` for a missing, malformed, ambiguous or different
    identity.  The method is asynchronous because a standalone source may consume a
    short-lived proof from the persistent OAuth store; the AppAPI implementation remains
    a local header verification.
    """

    async def identifies(
        self, request: Request, expected_account_id: str, *, flow_id: str | None = None
    ) -> bool:
        """Return whether the trusted source identifies the browser as the account.

        ``flow_id`` names the authorization request the decision belongs to. A source that
        binds its proof to one request refuses when it is missing.
        """
        ...

    async def pending_step(
        self, request: Request, *, flow_id: str, expected_account_id: str
    ) -> IdentityStep | None:
        """The step the consent screen offers instead of the decision, or ``None``.

        Display only: the decision itself still asks :meth:`identifies`.
        """
        ...

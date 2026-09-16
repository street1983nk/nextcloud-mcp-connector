"""The independent authority that binds a consent decision to one account.

The Login Flow v2 result proves which account produced an app password.  It does not
prove who is pressing the consent button, because the party that started a relayed flow
also holds the flow id and its anti-forgery value.  A deployment therefore supplies one
independent browser identity source to the consent boundary (CR-01).

This module defines only that boundary.  Deployment-specific implementations live with
their trust anchor: AppAPI in :mod:`mcp_connector.exapp.browser_identity`, and the future
standalone OIDC implementation in its own adapter.
"""

from typing import Protocol

from starlette.requests import Request

__all__ = ["BrowserIdentitySource"]


class BrowserIdentitySource(Protocol):
    """Decide whether this browser is independently known as one expected account.

    Implementations return ``False`` for a missing, malformed, ambiguous or different
    identity.  The method is asynchronous because a standalone source may consume a
    short-lived proof from the persistent OAuth store; the AppAPI implementation remains
    a local header verification.
    """

    async def identifies(self, request: Request, expected_account_id: str) -> bool:
        """Return whether the trusted source identifies the browser as the account."""
        ...

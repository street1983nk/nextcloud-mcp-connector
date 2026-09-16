"""The existing AppAPI trust anchor as a consent browser identity source."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from starlette.requests import Request

from ..oauth.browser_identity import IdentityStep
from ..oauth.principal import same_principal
from .auth import appapi_user

__all__ = ["AppApiBrowserIdentitySource"]


@dataclass(frozen=True, slots=True)
class AppApiBrowserIdentitySource:
    """Identify the deciding browser through AppAPI's authenticated user header."""

    env: Mapping[str, str] | None = None

    async def identifies(
        self, request: Request, expected_account_id: str, *, flow_id: str | None = None
    ) -> bool:
        """Preserve the current CR-01 comparison without adding another identity path."""
        return same_principal(appapi_user(request, env=self.env), expected_account_id)

    async def pending_step(
        self, request: Request, *, flow_id: str, expected_account_id: str
    ) -> IdentityStep | None:
        """HaRP resolves the account on every request, so there is never a step."""
        return None

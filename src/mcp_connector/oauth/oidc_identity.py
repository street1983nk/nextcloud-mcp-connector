"""The standalone browser identity: the proof a single sign-on callback left behind.

The consent boundary asks one injected source whether the deciding browser is the account
the Nextcloud sign in produced (CR-01). In a standalone deployment that source is this one.
Its only evidence is a proof row that :mod:`mcp_connector.oauth.oidc_routes` writes after a
fully validated OIDC callback, bound to one flow and one account, and named by an opaque
handle in a ``__Host-`` cookie of this browser.

* :meth:`OidcBrowserIdentitySource.pending_step` only reads. While this browser has no
  live proof for the flow and account, the consent screen offers the sign-on instead of the
  decision buttons.
* :meth:`OidcBrowserIdentitySource.identifies` consumes the proof, exactly once, and
  compares its account with the expected one. A missing flow id, a missing or ambiguous
  cookie, a spent or expired proof and another account are all the same ``False``.
"""

from dataclasses import dataclass

from starlette.requests import Request

from ..exapp.ui.consent import CONFIRM_PARAM, FLOW_PARAM
from . import crypto
from .browser_identity import IdentityStep
from .oidc_routes import OIDC_START_PATH, PROOF_COOKIE, browser_cookie
from .principal import same_principal
from .store import StoreProvider

__all__ = ["OidcBrowserIdentitySource"]


@dataclass(frozen=True, slots=True)
class OidcBrowserIdentitySource:
    """Identify the deciding browser through its single sign-on proof for this flow."""

    store: StoreProvider

    async def identifies(
        self, request: Request, expected_account_id: str, *, flow_id: str | None = None
    ) -> bool:
        """Consume this browser's proof for ``flow_id`` and compare its account."""
        if not flow_id or not expected_account_id:
            return False
        handle = browser_cookie(request, PROOF_COOKIE)
        if handle is None:
            return False
        opened = await self.store()
        principal = await opened.redeem_browser_proof(proof_handle=handle, flow_id=flow_id)
        return principal is not None and same_principal(principal, expected_account_id)

    async def pending_step(
        self, request: Request, *, flow_id: str, expected_account_id: str
    ) -> IdentityStep | None:
        """``None`` when this browser holds a live proof for this flow and account."""
        opened = await self.store()
        handle = browser_cookie(request, PROOF_COOKIE)
        if handle is not None:
            principal = await opened.browser_proof_principal(proof_handle=handle, flow_id=flow_id)
            if principal is not None and same_principal(principal, expected_account_id):
                return None
        return IdentityStep(
            action_path=OIDC_START_PATH,
            fields={
                FLOW_PARAM: flow_id,
                CONFIRM_PARAM: opened.form_token(flow_id, purpose=crypto.PURPOSE_OIDC_START),
            },
        )

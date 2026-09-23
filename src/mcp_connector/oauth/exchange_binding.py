"""The account source of the standalone mode: a pre-granted authorization as identity.

This way adds no new mandate (way B of D-v1.6-01): it only selects an authorization the
user granted in the browser beforehand, so the connector can do exactly what it could do
before, under a credential that already existed. Nothing here ever writes, and that holds
when no binding is found as well: no silent provisioning, which is the reversal of MAP-02
read in the second operating mode. Every failure is the same answer, so from outside it is
not visible whether the account exists, whether it has a binding or whether the store was
unreadable at that moment. And the read happens deliberately per request and enters no
cache, because exactly that is what makes the revocation of plan 23-06 act at once.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .exchange_accounts import EXCHANGE_CLIENT_ID, acting_party
from .principal import login_name_of, principal_of, same_principal
from .store import StoreProvider
from .verifier import CREDENTIAL_APP_PASSWORD, OAuthIdentity

__all__ = ["BoundAccounts"]

logger = logging.getLogger("mcp_connector.oauth.exchange_binding")


@dataclass(frozen=True, slots=True)
class BoundAccounts:
    """The ``ExchangeAccounts`` implementation of the standalone deployment.

    Holds the one store opener of the application, the same shape ``connect.py`` and
    ``connections.py`` take, and the reserved client its bindings are booked under. The
    client identifier is a field with a default rather than a constant in the method, so a
    test can point the source at any reserved row while every deployment keeps the one of
    :data:`~mcp_connector.oauth.exchange_accounts.EXCHANGE_CLIENT_ID`.
    """

    _store: StoreProvider
    _client_id: str = EXCHANGE_CLIENT_ID

    async def identity_for(self, principal: str, claims: Mapping[str, Any]) -> OAuthIdentity | None:
        """The identity of the one living binding of this principal, or ``None``.

        Built in the form of ``StoreTokenVerifier.resolve_identity``: read fresh for this
        one request, every exception one refusal and one line naming only the type of the
        failure, never a principal, an id or a password. The ``same_principal`` comparison
        against the row is belt and braces (T-23-16): the query has already filtered on the
        principal, but this method is where it is decided which account is acted under, and
        an ownership check may not rest alone with a query one level below it, the same
        reason ``provider.end_connection`` gives for its own comparison.
        """
        if not principal:
            # The app context owns nothing here, and the refusal costs no read at all.
            return None
        try:
            store = await self._store()
            row = await store.binding_of(principal, self._client_id)
            if row is None:
                return None
            if not same_principal(principal, principal_of(row)):
                return None
            password = await store.app_password(row.auth_id)
        except Exception as exc:
            logger.error("a bound account could not be read: %s", type(exc).__name__)
            return None
        if not password:
            # Empty could also be a broken read, so it never acts (the credential layer
            # reads the credential field and never the emptiness of the password).
            return None
        return OAuthIdentity(
            nc_user=login_name_of(row),
            app_password=password,
            auth_id=row.auth_id,
            client_id=self._client_id,
            principal=principal_of(row),
            revoked=row.revoked_at is not None,
            client_name=acting_party(claims),
            credential=CREDENTIAL_APP_PASSWORD,
        )

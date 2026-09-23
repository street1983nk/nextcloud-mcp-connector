"""The account source of the ExApp operation: existence fail closed, identity by impersonation.

This is the ``ExchangeAccounts`` implementation the ExApp deployment hands into the chain,
and it carries the deliberate reversal MAP-02 asks for. The account list is read through the
one reader in ``audit/accounts.py``, whose ``None`` means "unknown". There a doubt is a
keeping: the sweep of D-12 drops no chain it cannot prove orphaned. Here the very same
``None`` is the opposite, a refusal: an identity this source cannot prove to exist does not
act, because a passed uncertainty would cost somebody's data while a kept chain only costs
storage.

There can be no silent account creation on this way, structurally: this source creates
nothing and could not. It answers one question about one principal against the list of
accounts the instance itself names, and its only positive answer is an identity for an
account that already exists. And the permission boundary stays where it always was, with
Nextcloud: this way only chooses in whose name a call is asked, never what that name may
read or write, because the impersonation header is judged by Nextcloud on every request.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Final

from ..audit import accounts
from .exchange_accounts import EXCHANGE_CLIENT_ID, acting_party
from .verifier import CREDENTIAL_IMPERSONATE, OAuthIdentity

__all__ = ["ACCOUNT_CACHE_TTL", "ACCOUNT_FAILURE_RETRY_SECONDS", "AppApiAccounts"]

#: How long a fetched account list is reused. The list is the whole instance in one answer
#: (ten thousand identifiers on a large deployment), so it must never be fetched per tool
#: call; a minute keeps concurrent assistants at one fetch while staying close to the truth.
#: The honest sentence about that freshness: an account Nextcloud deletes in this minute is
#: still treated as existing for up to a minute here, and that is harmless, because the
#: impersonation of a deleted account fails at Nextcloud itself.
ACCOUNT_CACHE_TTL: Final[float] = 60.0

#: After a failed read, no further read is started for this long; every call that arrives
#: meanwhile is refused straight away. Without it an unreachable Nextcloud would turn every
#: incoming exchange call into an outgoing fetch, amplifying the load exactly while the
#: instance is struggling. Half the TTL: a refusal window should end well before a truth
#: window would.
ACCOUNT_FAILURE_RETRY_SECONDS: Final[float] = 30.0


class AppApiAccounts:
    """The one account cache of this process, built once per application.

    Every dependency is handed in, so every rule of this class is measurable without a
    network: the deploy environment the list is read with, the list reader itself
    (defaulting to the one reader of the AppAPI account route), the clock and the TTL.
    The clock defaults to the monotonic one and never the wall clock, for the reason
    ``oidc.OidcClient`` names: a wall clock jumps, and freshness arithmetic on a jumping
    clock turns a cache into a coin toss.
    """

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        users: Callable[
            [Mapping[str, str] | None], Awaitable[frozenset[str] | None]
        ] = accounts.existing_users,
        clock: Callable[[], float] | None = None,
        ttl: float = ACCOUNT_CACHE_TTL,
    ) -> None:
        self._env = env
        self._users = users
        self._clock = clock if clock is not None else time.monotonic
        self._ttl = ttl
        # Minus infinity, not zero: a cache nobody filled has to be stale under every
        # clock, and a failure stamp nobody set has to be outside every grace period.
        self._known_accounts: frozenset[str] | None = None
        self._fetched_at = float("-inf")
        self._failed_at = float("-inf")
        self._lock = asyncio.Lock()

    async def identity_for(self, principal: str, claims: Mapping[str, Any]) -> OAuthIdentity | None:
        """The contract of ``ExchangeAccounts``: an existing account acts, everything else not.

        An empty principal is refused before anything is fetched: it would be the app
        context without a user, which this path may never produce. An unknown list and a
        principal the list does not name are one answer from outside, ``None``, without a
        reason. Never raises for any input and writes no principal, no claim and no header
        into a log line; there is no logger in this module at all.
        """
        if not principal:
            return None
        known = await self._known()
        if known is None or principal not in known:
            return None
        return OAuthIdentity(
            # The same value twice on purpose: the AppAPI header takes the user id, and the
            # user id is the principal of this project (oauth/principal.py). A second,
            # guessed name here would be the confused deputy this phase is written against.
            nc_user=principal,
            # No password, because none exists on this way; the credential layer reads the
            # way below and never the emptiness of this field.
            app_password="",
            # No stored authorization either: the audit line recognises this path by the
            # reserved client id, so an empty auth id names the truth instead of inventing
            # a row nobody could look up.
            auth_id="",
            client_id=EXCHANGE_CLIENT_ID,
            principal=principal,
            client_name=acting_party(claims),
            credential=CREDENTIAL_IMPERSONATE,
        )

    async def _known(self) -> frozenset[str] | None:
        """The account list of the instance, out of the cache whenever the cache is fresh.

        The cost brake and the only place with state. A fresh cache answers without the
        lock; everything else takes it, re-checks behind it (whoever waited takes the
        outcome of the flight that just finished), refuses for free during the grace
        period after a failure, and otherwise pays for one fetch. A failure is never
        cached as an empty set: the cache keeps whatever it held, and only the stamp of
        the failure moves.
        """
        now = self._clock()
        if self._known_accounts is not None and now - self._fetched_at < self._ttl:
            # The fast path takes no lock: nothing is awaited between the check and the
            # read, so the cache cannot be exchanged underneath it.
            return self._known_accounts
        async with self._lock:
            now = self._clock()
            if self._known_accounts is not None and now - self._fetched_at < self._ttl:
                return self._known_accounts
            if now - self._failed_at < ACCOUNT_FAILURE_RETRY_SECONDS:
                return None
            # The stamp is set before the outgoing fetch, not after: a slow Nextcloud must
            # not stretch the refusal window its own slowness caused (the shape of the
            # miss stamp in oauth/jwks.py).
            self._failed_at = now
            names = await self._users(self._env)
            if not names:
                # ``None`` and the empty set are one refusal: the reader never answers an
                # empty set, but this rule must not depend on that.
                return None
            self._known_accounts = names
            self._fetched_at = self._clock()
            return names

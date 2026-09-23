"""The seam between a mapped principal and the identity it may act under (MAP-01, MAP-02).

The two operating modes of the exchange path differ in exactly one question: how does a
canonical principal become an :class:`~mcp_connector.oauth.verifier.OAuthIdentity` this
server may act with. Everything before that question (the signature, the claim rules, the
mapping) and everything after it (the pause switch, the audit chain, the credential layer)
is the same code for both. So the question is one protocol with one method, handed into the
chain of ``oauth/chain.py``, and this module is where its contract is written down once.

Nothing here talks to anything. The module holds a protocol, a reserved identifier and one
pure function; the implementations of the protocol arrive with plans 23-03 and 23-04, and
they are the ones that may open a store or ask Nextcloud.
"""

from collections.abc import Mapping
from typing import Any, Final, Protocol, runtime_checkable

from .verifier import OAuthIdentity

__all__ = [
    "EXCHANGE_CLIENT_ID",
    "MAX_ACTING_PARTY_LENGTH",
    "ExchangeAccounts",
    "acting_party",
]

#: The reserved client id every exchange identity is booked under. The exchange path has no
#: registered client, because the acting party is a client of a foreign realm: it registered
#: over there, not here, and a row in our client table would be a registration nobody made.
#: The identifier stands in the identity and therefore in every audit line, so a reader can
#: tell an exchange call from a call of a registered client at a glance. The chain grew no
#: column for it: the acting party of such a call took the one the schema already had for
#: who acted, ``entries.actor`` (AUDIT-07), and this identifier stays the name the identity
#: itself is booked under. Same form and same kind of reasoning as
#: ``connect.CONNECT_CLIENT_ID``, and a different value, so the two reserved paths can never
#: be confused.
EXCHANGE_CLIENT_ID: Final[str] = "urn:mcp-connector:token-exchange"

#: The upper bound of the acting party on its way into an identity. The same number as
#: ``mapping.MAX_PRINCIPAL_LENGTH``, and deliberately below the eighty characters the audit
#: store grants a registered client name: the value is never looked up, only printed.
MAX_ACTING_PARTY_LENGTH: Final[int] = 64


@runtime_checkable
class ExchangeAccounts(Protocol):
    """The one interface at which the two operating modes of the exchange path differ.

    The contract both implementations have to keep:

    * ``None`` always means "this account does not act here", without saying why. Not
      found, not provisioned, not readable and not allowed are one answer from outside,
      for the reason every refusal of ``verifier.py`` is one answer.
    * The method never creates anything: no account, no connection, no credential. It
      answers a question, and the answer is an identity that already has a basis or
      nothing.
    * The existence of the account is checked fail closed (MAP-02): uncertainty is a
      refusal and never a pass. This is the deliberate opposite of the audit sweep of
      D-12, which keeps a chain when the account list cannot be read, because there a kept
      chain costs storage while here a passed uncertainty would cost somebody's data.
    * The checked claim set rides along so the implementation can write the acting party
      into the ``actor`` field of the identity (:func:`acting_party`); it never reads an
      identity out of it. The principal is the first parameter and the only name an account
      may be found under.
    """

    async def identity_for(
        self, principal: str, claims: Mapping[str, Any]
    ) -> OAuthIdentity | None: ...


def acting_party(claims: Mapping[str, Any]) -> str:
    """The ``azp`` of a checked claim set, as the value that may enter an identity.

    This becomes ``actor`` of the exchange identity and therefore the ``actor`` column of
    every audit line of this path, next to :data:`EXCHANGE_CLIENT_ID` and never in
    ``client_name``: no client is registered here, so a registered name would be a claim
    nobody can look up. The value comes from a foreign realm, so it is treated exactly like
    the name a client gives itself at registration: carried unquoted, quoted only where it
    is written into a line or onto a page. ``audit/store.py`` cleans it again on its way
    into a row, under its own bound ``ACTOR_LIMIT`` and under the one rule of
    ``audit/text.py``, which is wider than the filter below.

    Text or the empty string, never an exception: control and format characters are
    removed (a line break could fake a log line, a right-to-left override could turn one
    around, the lesson of R-18-06), the rest is capped at
    :data:`MAX_ACTING_PARTY_LENGTH`. Anything that is not a string names nobody and is the
    empty string, including ``True``, which is an ``int`` and passes no ``isinstance``
    check against ``str``.
    """
    value = claims.get("azp")
    if not isinstance(value, str):
        return ""
    cleaned = "".join(character for character in value if character.isprintable())
    return cleaned[:MAX_ACTING_PARTY_LENGTH]

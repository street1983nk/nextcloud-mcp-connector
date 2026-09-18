"""Who a connection belongs to, answered in one place (the central principal rule).

Two names describe a Nextcloud account in this project, and they are not interchangeable:

* The **login name** is what Login Flow v2 returns. Nextcloud Basic authentication and the
  revocation of an app password need exactly this value.
* The **principal** is the value every identity comparison uses: the browser that decides a
  consent or receives an onboarding result, the ownership of a connection, the per account
  pause switch and the audit subject.

Every new connection stores both: ``nc_user`` is the login name, ``nc_account_id`` the
canonical Nextcloud account id that OCS (``cloud/user``) returns for the app password right
after the sign in. The principal is that account id. Rows written by an ExApp before the
column existed have no account id; for them, and only for them, the principal stays the login
name. That is the single legacy branch of this rule, and it invents or backfills nothing.

Audit chains are keyed by the principal (``u:<principal>``). A legacy row keeps writing to
the chain of its login name, exactly as before, so no existing chain forks. A connection
with an account id writes to the chain of that id, which is the chain AppAPI callers of the
same account already use; where login name and account id differ (LDAP), the older OAuth
entries stay readable under the login name chain and new ones follow the account id.

A third name exists and is not part of the rule above: the **display name** is what the
instance calls the account in its own interface. It is for reading only. It is never
compared, never stored as identity, and a connection without one reads exactly as every
connection read before the column existed, because the fallback is the login name.

No call site picks a name or compares identities on its own; it asks :func:`principal_of`,
:func:`login_name_of`, :func:`display_name_of` and :func:`same_principal`. Before a row
exists, the principal of a finished sign in is the resolved account id itself.
"""

import secrets
from typing import Protocol

__all__ = ["display_name_of", "login_name_of", "principal_of", "same_principal"]


class Authorized(Protocol):
    """What this rule reads from a stored connection to answer an identity question."""

    @property
    def nc_user(self) -> str: ...

    @property
    def nc_account_id(self) -> str | None: ...


class Named(Protocol):
    """What this rule reads to answer a display question, which is not every row.

    Deliberately a second protocol. An access token row carries identity and no display
    name, and widening :class:`Authorized` to demand one would either put a column on rows
    that have no use for it or invite a ``None`` default that means "not asked" in one place
    and "no name" in another.
    """

    @property
    def nc_user(self) -> str: ...

    @property
    def nc_display_name(self) -> str | None: ...


def principal_of(authorization: Authorized) -> str:
    """The value identity comparisons, ownership, pause and audit use for this connection.

    The canonical account id, or the login name for a legacy ExApp row that has none.
    """
    return authorization.nc_account_id or authorization.nc_user


def login_name_of(authorization: Authorized) -> str:
    """The value Basic authentication and app password revocation need for this connection."""
    return authorization.nc_user


def display_name_of(authorization: Named) -> str:
    """The name a page shows for this connection. Never an identity, never a comparison.

    The display name the instance answered with at sign in time, or the login name when
    there is none. The fallback is the whole compatibility story of this value: a row from
    before the column, an instance that sets no display name and an answer that carried
    nothing usable all read the way they always read.
    """
    return authorization.nc_display_name or authorization.nc_user


def same_principal(received: str, expected: str) -> bool:
    """Whether two principals are the same account. An empty value never matches.

    Constant time on UTF-8 bytes: one of the two values is decided by a request, and
    ``compare_digest`` raises on non-ASCII strings. An empty value fails before the
    comparison, so a request without an identity can never pass as the owner of a row that
    has none either (fail closed, D-37).
    """
    if not received or not expected:
        return False
    return secrets.compare_digest(received.encode("utf-8"), expected.encode("utf-8"))

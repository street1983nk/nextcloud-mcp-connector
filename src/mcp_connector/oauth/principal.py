"""Who a connection belongs to, answered in one place (the central principal rule).

Two names describe a Nextcloud account in this project, and they are not interchangeable:

* The **login name** is what Login Flow v2 returns. Nextcloud Basic authentication and the
  revocation of an app password need exactly this value.
* The **principal** is the value every identity comparison uses: the browser that decides a
  consent or receives an onboarding result, the ownership of a connection, the per account
  pause switch and the audit subject.

The store records only the login name today (``nc_user``). For every existing row the
principal therefore *is* the login name, and that is the single legacy branch of this rule.
A later step adds the canonical Nextcloud account id and switches the principal to it for new
rows, here and nowhere else. No call site picks a name or compares identities on its own; it
asks :func:`principal_of`, :func:`login_name_of` and :func:`same_principal`.
"""

import secrets
from typing import Protocol

__all__ = ["login_name_of", "principal_of", "same_principal", "sign_in_principal"]


class Authorized(Protocol):
    """What this rule reads from a stored connection."""

    @property
    def nc_user(self) -> str: ...


def principal_of(authorization: Authorized) -> str:
    """The value identity comparisons, ownership, pause and audit use for this connection."""
    return authorization.nc_user


def sign_in_principal(login_name: str) -> str:
    """The principal of a finished sign in, before any connection row exists for it.

    Login Flow v2 returns only the login name, so today it is the principal as well (the
    legacy branch). Once the canonical account id is resolved right after the poll, this is
    where it takes over.
    """
    return login_name


def login_name_of(authorization: Authorized) -> str:
    """The value Basic authentication and app password revocation need for this connection."""
    return authorization.nc_user


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

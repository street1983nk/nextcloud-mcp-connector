"""The account mapping of the exchange path: a checked claim set becomes one principal.

The result of this file is always the canonical principal in the sense of ``principal.py``
and never a login name: the one function below has no parameter that could carry a login
name and no return path on which one could come out, and that structure, not a promise, is
its answer to pitfall 5 of the research. The pause switch, the audit chain and the sweep all
compare principals; a login name that slipped into any of them would fork all three.

A claim value is freight of a foreign realm. The signature of the exchanged token covers it
and nothing else has checked it (see ``ExchangeTokenChecker.claims_of``), so it is judged
here and never repaired: a value that is trimmed, truncated or case folded into shape names
a different account than the one the provider wrote, and two spellings that map onto one
account are how " alice" takes over alice. A value outside the rules yields ``None``, which
always means "this token points at no account".

Which profile is right when:

* :data:`MAPPING_ACCOUNT_ID_V1` when the provider itself carries the canonical Nextcloud
  account id in a claim. This is the LDAP-capable case, in which the login name and the
  account id go separate ways and the login name never occurs on this path at all.
* :data:`MAPPING_USER_OIDC_SUB_V1` when the instance keeps its accounts through the
  ``user_oidc`` app with "unique user id" enabled and ``sub`` as the mapping claim. The
  derivation is the one of ``oidc.user_oidc_unique_uid_sub_v1`` and is called, not copied.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from .oidc import STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1, user_oidc_unique_uid_sub_v1

__all__ = [
    "MAPPING_ACCOUNT_ID_V1",
    "MAPPING_STRATEGIES",
    "MAPPING_USER_OIDC_SUB_V1",
    "MAX_PRINCIPAL_LENGTH",
    "MAX_SUBJECT_LENGTH",
    "MappingSettings",
    "principal_from_claims",
]

#: The profile that takes the configured claim value unchanged as the canonical principal.
MAPPING_ACCOUNT_ID_V1: Final[str] = "account_id_v1"

#: The profile that derives the account id ``user_oidc`` creates with unique user ids from
#: the raw claim value. Deliberately the very name of ``oidc.STRATEGY_USER_OIDC_UNIQUE_UID_
#: SUB_V1``, because it is the same derivation; assigning instead of retyping is what keeps
#: the two from drifting.
MAPPING_USER_OIDC_SUB_V1: Final[str] = STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1

#: Every profile this file knows. A name outside this tuple is refused while building the
#: settings, never discovered at mapping time.
MAPPING_STRATEGIES: Final[tuple[str, ...]] = (MAPPING_ACCOUNT_ID_V1, MAPPING_USER_OIDC_SUB_V1)

#: The upper bound of a Nextcloud user id, and therefore of anything the account id profile
#: may answer. A longer value is no account and yields nothing.
MAX_PRINCIPAL_LENGTH: Final[int] = 64

#: The upper bound the sub profile puts on the raw claim value before deriving from it. Its
#: result is a fixed-length digest, so the bound guards the input, not the answer.
MAX_SUBJECT_LENGTH: Final[int] = 255

#: The characters Nextcloud refuses in a user id. A principal carrying one of them could
#: smuggle a path, a redirect or a second name into every place that prints or compares it.
_FORBIDDEN_CHARACTERS: Final[frozenset[str]] = frozenset('\\/<>:"|?*')


@dataclass(frozen=True, slots=True)
class MappingSettings:
    """One validated mapping profile with its parameters. Nothing here is guessed.

    Frozen with slots like every other settings object of this package: a mapping that a
    later line could repoint would decide identities twice. Every field is typed first and
    read second, in the form of ``ExchangeSettings.__post_init__``, and every violation is
    a :class:`ValueError` that names the field and never repeats the value: the value can
    have travelled here over HTTP through the settings overlay of the ExApp (T-23-04).
    """

    strategy: str
    account_claim: str
    oidc_provider_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, str):
            raise ValueError("strategy must be a string")
        if self.strategy not in MAPPING_STRATEGIES:
            raise ValueError("strategy is not one of the named mapping profiles")
        if not isinstance(self.account_claim, str):
            raise ValueError("account_claim must be a string")
        if not self.account_claim or self.account_claim != self.account_claim.strip():
            raise ValueError("account_claim must be a non-empty name without edge whitespace")
        if self.strategy == MAPPING_USER_OIDC_SUB_V1:
            # ``bool`` is an ``int`` in Python, and ``True`` would derive the accounts of
            # provider 1: the same trap ``OidcSettings`` already refuses by type.
            if isinstance(self.oidc_provider_id, bool) or not isinstance(
                self.oidc_provider_id, int
            ):
                raise ValueError(
                    "oidc_provider_id is required by the sub profile and must be a whole number"
                )
            if self.oidc_provider_id <= 0:
                raise ValueError("oidc_provider_id must be a positive number")
        elif self.oidc_provider_id is not None:
            # Refused and not ignored, for the reason ``chain._optional`` refuses an empty
            # variable: a value nobody reads is a half state, and an operator who set it
            # believes it does something until somebody measures the opposite.
            raise ValueError("oidc_provider_id is set, but the configured profile does not read it")


def principal_from_claims(claims: Mapping[str, Any], settings: MappingSettings) -> str | None:
    """The canonical principal an exchanged token points at, or ``None`` for no account.

    ``None`` always means "this token points at no account", and the caller turns it into a
    refusal. The function raises under no input: it stands in the hot path of every tool
    call, and a mishap that flew instead of refusing would be a 500 at the transport
    boundary where a 401 belongs (T-23-03). It calls nothing but the one derivation named
    in the module docstring, reads nothing from the environment and knows no login name.
    """
    value = claims.get(settings.account_claim)
    if not isinstance(value, str) or not value:
        # A missing claim, ``None``, a number, ``True``, a list, a dictionary and the empty
        # string are all the same answer. ``bool`` never passes ``isinstance(..., str)``.
        return None
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        # Control characters are refused on both profiles: on a principal they poison logs
        # and comparisons, and on a raw subject they are nothing a provider writes.
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        # A lone surrogate is not text. Refused here rather than caught deeper down, so the
        # promise that this function never raises does not rest on the derivation.
        return None

    if settings.strategy == MAPPING_USER_OIDC_SUB_V1:
        # The raw subject is checked for text, non-emptiness, control characters and its
        # own length bound, never for the character rules of a name: the result of this
        # branch is a lowercase hexadecimal digest and not a name (T-23-02 holds through
        # the derivation).
        if len(value) > MAX_SUBJECT_LENGTH:
            return None
        if settings.oidc_provider_id is None:
            # Unreachable through a built ``MappingSettings``; kept because this function
            # promises to raise under no input, whatever object a caller hands in.
            return None
        return user_oidc_unique_uid_sub_v1(settings.oidc_provider_id, value)

    # The account id profile: the value is the principal, so the rules of a Nextcloud user
    # id apply to it in full. Judged, never repaired (T-23-01): a trimmed name would be
    # another account, and " alice" must never become alice.
    if value != value.strip():
        return None
    if any(character in _FORBIDDEN_CHARACTERS for character in value):
        return None
    if len(value) > MAX_PRINCIPAL_LENGTH:
        return None
    return value

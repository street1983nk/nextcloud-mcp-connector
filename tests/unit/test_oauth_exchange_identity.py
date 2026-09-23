"""The identity of the exchange path (MAP-01, plan 23-02): one seam, one branch, one proof.

Two things are pinned here. First the seam itself, ``oauth/exchange_accounts.py``: the one
interface at which the two operating modes of the exchange path differ, its reserved client
identifier and the reading of the acting party out of a checked foreign claim set. Second,
the ``EXCHANGE_CLAIM`` branch of ``ChainedVerifier.resolve_identity``: the one place a
checked exchange token becomes an identity, and the measured proof that the pause switch,
the audit chain and the sweep treat a mapped account exactly like a signed in one.

No Nextcloud and no socket: the account source is a stand-in of this file, the stores are
SQLite files in ``tmp_path``, and both directions of "never asked" are stand-ins that raise
:class:`AssertionError` the moment they are touched (the shape of 22-02).
"""

import pytest

from mcp_connector.oauth import connect, exchange_accounts

AZP = "f13-orchestrator"


# --- the reserved client identifier of the exchange path -----------------------------------


def test_the_exchange_client_id_is_the_reserved_urn_of_this_path() -> None:
    """The value every audit line of an exchange call carries as its client."""
    assert exchange_accounts.EXCHANGE_CLIENT_ID == "urn:mcp-connector:token-exchange"


def test_the_exchange_client_id_differs_from_the_onboarding_client() -> None:
    """Two reserved identifiers, two different paths: a reader must be able to tell them."""
    assert exchange_accounts.EXCHANGE_CLIENT_ID != connect.CONNECT_CLIENT_ID


# --- the acting party out of a checked foreign claim set -----------------------------------


def test_the_acting_party_is_the_azp_of_the_checked_claim_set() -> None:
    assert exchange_accounts.acting_party({"azp": AZP}) == AZP


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"azp": ""},
        {"azp": None},
        {"azp": 1},
        {"azp": True},
        {"azp": ["f13"]},
        {"azp": {"name": "f13"}},
        {"azp": b"f13"},
    ],
    ids=["missing", "empty", "none", "number", "bool", "list", "dict", "bytes"],
)
def test_a_missing_empty_or_untextual_azp_is_the_empty_string(claims: dict) -> None:
    """The value is freight of a foreign realm: anything that is not text names nobody."""
    assert exchange_accounts.acting_party(claims) == ""


def test_the_acting_party_is_capped_at_its_named_bound() -> None:
    assert exchange_accounts.MAX_ACTING_PARTY_LENGTH == 64
    capped = exchange_accounts.acting_party({"azp": "x" * 200})
    assert len(capped) == exchange_accounts.MAX_ACTING_PARTY_LENGTH


def test_the_acting_party_carries_no_control_or_format_character() -> None:
    """A line break could fake a log line, an RTL override could turn one around."""
    assert exchange_accounts.acting_party({"azp": "f13\x00\x07"}) == "f13"
    assert exchange_accounts.acting_party({"azp": "f\r\n13"}) == "f13"
    assert exchange_accounts.acting_party({"azp": "a‮b"}) == "ab"
    assert exchange_accounts.acting_party({"azp": "\x1b[31m"}) == "[31m"


def test_the_acting_party_never_raises_under_a_hostile_corpus() -> None:
    """The function stands next to the hot path and refusal is its only failure mode."""
    corpus = [
        {"azp": "\ud800"},
        {"azp": "\x00" * 300},
        {"azp": 3.14},
        {"azp": object()},
        {"azp": "x" * 100_000},
        {"other": AZP},
    ]
    for claims in corpus:
        result = exchange_accounts.acting_party(claims)
        assert isinstance(result, str)
        assert len(result) <= exchange_accounts.MAX_ACTING_PARTY_LENGTH


# --- the protocol of the account source -----------------------------------------------------


def test_an_object_with_the_one_method_satisfies_the_protocol() -> None:
    """The runtime checkable shape both operating modes have to fit."""

    class Fitting:
        async def identity_for(self, principal, claims):
            return None

    class NotFitting:
        pass

    assert isinstance(Fitting(), exchange_accounts.ExchangeAccounts)
    assert not isinstance(NotFitting(), exchange_accounts.ExchangeAccounts)

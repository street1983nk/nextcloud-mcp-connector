"""The account mapping of the exchange path: two named profiles, one function, one principal.

Every case here is a pure function of its input: nothing opens a socket, nothing reads the
environment, and no test builds an identity. What is measured is the one security promise of
MAP-01 against pitfall 5: the result of a mapping is always the canonical principal and never
a login name, and a claim that cannot name an account yields nothing rather than an exception.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from mcp_connector.oauth import mapping, oidc

CLAIM = "nextcloud_uid"


def account_id_settings(claim: str = CLAIM) -> mapping.MappingSettings:
    return mapping.MappingSettings(strategy=mapping.MAPPING_ACCOUNT_ID_V1, account_claim=claim)


def sub_settings(provider_id: int = 1) -> mapping.MappingSettings:
    return mapping.MappingSettings(
        strategy=mapping.MAPPING_USER_OIDC_SUB_V1,
        account_claim="sub",
        oidc_provider_id=provider_id,
    )


# --- the named profiles and their bounds ---------------------------------------------------


def test_the_two_profiles_and_their_bounds_are_the_documented_ones() -> None:
    assert mapping.MAPPING_ACCOUNT_ID_V1 == "account_id_v1"
    assert sorted(mapping.MAPPING_STRATEGIES) == ["account_id_v1", "user_oidc_unique_uid_sub_v1"]
    assert mapping.MAX_PRINCIPAL_LENGTH == 64
    assert mapping.MAX_SUBJECT_LENGTH == 255


def test_the_sub_profile_carries_the_name_of_the_oidc_strategy_it_reuses() -> None:
    """The same name because it is the same derivation, held here so the two never drift."""
    assert mapping.MAPPING_USER_OIDC_SUB_V1 == oidc.STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1


def test_both_profiles_are_buildable() -> None:
    assert account_id_settings().strategy == mapping.MAPPING_ACCOUNT_ID_V1
    assert account_id_settings().oidc_provider_id is None
    assert sub_settings().oidc_provider_id == 1


def test_the_settings_are_frozen() -> None:
    """Nothing downstream may repoint a mapping after the start has accepted it."""
    with pytest.raises(AttributeError):
        account_id_settings().account_claim = "sub"  # type: ignore[misc]


# --- a half built mapping is a ValueError, named after its field ---------------------------


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"strategy": "email_v1", "account_claim": "email"}, "strategy"),
        ({"strategy": 1, "account_claim": "sub"}, "strategy"),
        ({"strategy": None, "account_claim": "sub"}, "strategy"),
        ({"strategy": mapping.MAPPING_ACCOUNT_ID_V1, "account_claim": ""}, "account_claim"),
        ({"strategy": mapping.MAPPING_ACCOUNT_ID_V1, "account_claim": "  uid "}, "account_claim"),
        ({"strategy": mapping.MAPPING_ACCOUNT_ID_V1, "account_claim": 7}, "account_claim"),
        (
            {"strategy": mapping.MAPPING_USER_OIDC_SUB_V1, "account_claim": "sub"},
            "oidc_provider_id",
        ),
        (
            {
                "strategy": mapping.MAPPING_USER_OIDC_SUB_V1,
                "account_claim": "sub",
                "oidc_provider_id": 0,
            },
            "oidc_provider_id",
        ),
        (
            {
                "strategy": mapping.MAPPING_USER_OIDC_SUB_V1,
                "account_claim": "sub",
                "oidc_provider_id": -1,
            },
            "oidc_provider_id",
        ),
        (
            {
                "strategy": mapping.MAPPING_USER_OIDC_SUB_V1,
                "account_claim": "sub",
                "oidc_provider_id": True,
            },
            "oidc_provider_id",
        ),
        (
            {
                "strategy": mapping.MAPPING_USER_OIDC_SUB_V1,
                "account_claim": "sub",
                "oidc_provider_id": "7",
            },
            "oidc_provider_id",
        ),
        (
            {
                "strategy": mapping.MAPPING_ACCOUNT_ID_V1,
                "account_claim": "uid",
                "oidc_provider_id": 1,
            },
            "oidc_provider_id",
        ),
    ],
)
def test_a_half_built_mapping_is_a_value_error_that_names_the_field(
    kwargs: dict[str, Any], field: str
) -> None:
    """A value nobody reads is a half state, so a provider id on the account id profile is
    refused and never ignored; a missing one on the sub profile is refused the same way."""
    with pytest.raises(ValueError, match=field):
        mapping.MappingSettings(**kwargs)


def test_a_refusal_of_the_settings_never_repeats_the_value_it_read() -> None:
    """The value can have travelled here over HTTP through the settings overlay (T-23-04
    reads the same as T-22-04): a refusal names the field, never what stood in it."""
    with pytest.raises(ValueError, match="strategy") as excinfo:
        mapping.MappingSettings(strategy="a-secret-profile-name", account_claim="sub")

    assert "a-secret-profile-name" not in str(excinfo.value)


# --- what the two profiles answer ----------------------------------------------------------


def test_the_account_id_profile_passes_the_claim_value_through_unchanged() -> None:
    assert mapping.principal_from_claims({CLAIM: "alice"}, account_id_settings()) == "alice"


def test_the_account_id_profile_reads_exactly_the_configured_claim() -> None:
    claims = {"sub": "somebody-else", CLAIM: "alice"}
    assert mapping.principal_from_claims(claims, account_id_settings()) == "alice"


def test_the_sub_profile_derives_the_account_id_user_oidc_creates() -> None:
    derived = mapping.principal_from_claims({"sub": "abc"}, sub_settings(provider_id=1))
    assert derived == oidc.user_oidc_unique_uid_sub_v1(1, "abc")


def test_the_sub_profile_uses_the_configured_provider_id() -> None:
    derived = mapping.principal_from_claims({"sub": "abc"}, sub_settings(provider_id=7))
    assert derived == oidc.user_oidc_unique_uid_sub_v1(7, "abc")
    assert derived != oidc.user_oidc_unique_uid_sub_v1(1, "abc")


def test_a_principal_of_exactly_the_maximum_length_is_served() -> None:
    value = "a" * mapping.MAX_PRINCIPAL_LENGTH
    assert mapping.principal_from_claims({CLAIM: value}, account_id_settings()) == value


# --- a claim that cannot name an account yields nothing, never an exception ----------------


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {CLAIM: None},
        {CLAIM: 1},
        {CLAIM: 1.5},
        {CLAIM: True},
        {CLAIM: ["alice"]},
        {CLAIM: {"name": "alice"}},
        {CLAIM: b"alice"},
        {CLAIM: ""},
        {CLAIM: "   "},
        {CLAIM: " alice"},
        {CLAIM: "alice "},
        {CLAIM: "ali\x00ce"},
        {CLAIM: "ali\x1fce"},
        {CLAIM: "ali\nce"},
        {CLAIM: "ali\x7fce"},
        {CLAIM: "a" * (mapping.MAX_PRINCIPAL_LENGTH + 1)},
    ],
)
def test_an_unusable_claim_is_no_account(claims: dict[str, Any]) -> None:
    """A claim value is never repaired, only judged: a trimmed name would be another account
    (T-23-01), and a missing or wrongly typed one points at no account at all."""
    assert mapping.principal_from_claims(claims, account_id_settings()) is None


@pytest.mark.parametrize("character", sorted('\\/<>:"|?*'))
def test_a_forbidden_nextcloud_character_is_no_account(character: str) -> None:
    """The characters Nextcloud refuses in a user id, refused here before any identity
    could be built from them (T-23-02)."""
    claims = {CLAIM: f"ali{character}ce"}
    assert mapping.principal_from_claims(claims, account_id_settings()) is None


@pytest.mark.parametrize(
    "sub",
    [None, 1, True, ["abc"], {"sub": "abc"}, "", "a\x00b", "a\x1fb", "a\x7fb", "a" * 256],
)
def test_an_unusable_sub_is_no_account_either(sub: Any) -> None:
    """The sub profile checks the raw value for text, non-emptiness, control characters and
    its own length bound; a value outside them derives nothing."""
    assert mapping.principal_from_claims({"sub": sub}, sub_settings()) is None


def test_the_sub_profile_does_not_apply_the_character_rules_of_a_name() -> None:
    """Its result is a hexadecimal digest and never a name, so a slash in the raw value is
    the provider's business: user_oidc derives the very same account id from it."""
    derived = mapping.principal_from_claims({"sub": "a/b"}, sub_settings())
    assert derived == oidc.user_oidc_unique_uid_sub_v1(1, "a/b")


def test_a_sub_of_exactly_the_maximum_length_is_derived() -> None:
    value = "a" * mapping.MAX_SUBJECT_LENGTH
    derived = mapping.principal_from_claims({"sub": value}, sub_settings())
    assert derived == oidc.user_oidc_unique_uid_sub_v1(1, value)


HOSTILE_CLAIM_SETS: tuple[dict[str, Any], ...] = (
    {},
    {CLAIM: object()},
    {CLAIM: type},
    {CLAIM: Exception("boom")},
    {CLAIM: float("nan")},
    {CLAIM: "\ud800"},
    {CLAIM: "\udfff-tail"},
    {CLAIM: ("a",)},
    {CLAIM: {1: 2}, "sub": object()},
    {"sub": "\ud800"},
    {"sub": b"\xff"},
    {"sub": 10**100},
)


@pytest.mark.parametrize("claims", HOSTILE_CLAIM_SETS)
@pytest.mark.parametrize("profile", ["account_id", "sub"])
def test_the_function_raises_under_no_input(profile: str, claims: dict[str, Any]) -> None:
    """The function stands in the hot path of every tool call, and a mishap that flies
    instead of refusing would be a 500 at the transport boundary (T-23-03)."""
    settings = account_id_settings() if profile == "account_id" else sub_settings()

    result = mapping.principal_from_claims(claims, settings)

    assert result is None or isinstance(result, str)


# --- the structural promises of the module -------------------------------------------------


def code_of(module: Any) -> str:
    text = Path(module.__file__).read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not re.match(r"^\s*#", line))


def test_the_module_knows_no_login_name_no_environment_no_network() -> None:
    """There is no return path on which a login name could come out of this file, and the
    function reads nothing and calls nothing: that is its promise against pitfall 5."""
    code = code_of(mapping)
    for banned in ("nc_user", "login" + "_name", "os.environ", "httpx", "await "):
        assert banned not in code, f"mapping.py must not mention {banned!r}"


def test_the_derivation_is_called_and_never_rebuilt() -> None:
    """One derivation of the user_oidc account id exists, in oidc.py; a second copy here
    would drift from it the first time either is corrected."""
    text = Path(mapping.__file__).read_text(encoding="utf-8")
    assert "hash" + "lib" not in text
    assert "user_oidc_unique_uid_sub_v1" in text

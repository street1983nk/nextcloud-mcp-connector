"""The central principal rule: one place decides who a connection belongs to.

Commit scope: the rule exists and every consent, onboarding, connection page, provider and
purge path uses it. The canonical account id and the verifier, pause and audit paths follow.
"""

import re
from pathlib import Path

import pytest

from mcp_connector.oauth import principal
from mcp_connector.oauth.store import AuthorizationRow

SRC = Path(principal.__file__).resolve().parents[1]

ROW = AuthorizationRow(
    auth_id="auth-1",
    client_id="client-1",
    nc_user="alice",
    scopes="nextcloud",
    resource="https://mcp.example.com/mcp",
    created_at=1,
    revoked_at=None,
)


@pytest.mark.parametrize(
    ("received", "expected", "same"),
    [
        ("alice", "alice", True),
        ("alice", "bob", False),
        ("Alice", "alice", False),
        ("", "", False),
        ("", "alice", False),
        ("alice", "", False),
        ("jürgen", "jürgen", True),
        ("jürgen", "jurgen", False),
    ],
)
def test_same_principal(received: str, expected: str, same: bool) -> None:
    assert principal.same_principal(received, expected) is same


def test_the_legacy_branch_uses_the_login_name_for_both_names() -> None:
    assert principal.principal_of(ROW) == "alice"
    assert principal.login_name_of(ROW) == "alice"
    assert principal.sign_in_principal("alice") == "alice"


def test_the_comparison_is_constant_time() -> None:
    source = Path(principal.__file__).read_text(encoding="utf-8")
    assert "compare_digest" in source


# Files that decide ownership or identity for a connection. None of them may read the stored
# name directly or compare identities on its own; they ask the principal rule.
RULED = (
    "oauth/consent.py",
    "oauth/connect.py",
    "oauth/connections.py",
    "oauth/provider.py",
    "exapp/purge.py",
    "exapp/browser_identity.py",
)


def code_of(relative: str) -> str:
    text = (SRC / relative).read_text(encoding="utf-8")
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


@pytest.mark.parametrize("relative", RULED)
def test_no_ruled_file_reads_the_stored_name_directly(relative: str) -> None:
    assert ".nc_user" not in code_of(relative)


@pytest.mark.parametrize("relative", RULED)
def test_no_ruled_file_compares_identities_on_its_own(relative: str) -> None:
    code = code_of(relative)
    assert "is_user(" not in code
    if relative != "oauth/provider.py":
        assert "compare_digest" not in code


def test_the_old_helper_is_gone() -> None:
    from mcp_connector.exapp import auth

    assert not hasattr(auth, "is_user")

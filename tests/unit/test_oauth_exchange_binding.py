"""The account source of the standalone mode (CRED-02, plan 23-04): a binding, read only.

``BoundAccounts`` answers the one question the two operating modes differ in, and it does
so against a real SQLite store in ``tmp_path``, so the decryption of the app password runs
for real in every test. The contract under test is the contract of the seam
(``oauth/exchange_accounts.py``): ``None`` always means "this account does not act here"
without saying why, nothing here ever writes, and the read happens per request so a
revocation is seen by the very next call. The row counter before and after every refusal is
part of the tests, because "writes nothing" has to be a measurement and not a sentence
(T-23-18).
"""

import asyncio
import base64
import json
import logging
import sqlite3
import time
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from mcp.server.auth.provider import AccessToken
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config, deps, entry_oauth
from mcp_connector.exapp.middleware import RequireOAuthBearer
from mcp_connector.oauth import chain, exchange_binding
from mcp_connector.oauth.exchange_accounts import EXCHANGE_CLIENT_ID, ExchangeAccounts
from mcp_connector.oauth.metadata import RESOURCE_SUFFIX
from mcp_connector.oauth.store import AuthorizationRow, OAuthStore
from mcp_connector.oauth.verifier import CREDENTIAL_APP_PASSWORD, OAuthIdentity

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

#: The mapped principal an exchange token acts as, and the login name of its binding. Two
#: different values on purpose: a test that used one for both could pass for the wrong
#: reason (an LDAP account is exactly the case where they differ).
MAPPED = "f13-account-7"
LOGIN = "alice-login"

BOUND_PASSWORD = "the-bound-app-password-xyz"
AZP = "f13-orchestrator"

STORE_FILE = "oauth.sqlite3"


def open_store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / STORE_FILE, KEY)


def opener_of(subject: OAuthStore):
    async def opener() -> OAuthStore:
        return subject

    return opener


def exploding_opener():
    async def opener() -> OAuthStore:
        raise AssertionError("the store was opened although nothing may be read")

    return opener


async def with_binding(
    subject: OAuthStore,
    *,
    auth_id: str = "binding-1",
    client_id: str = EXCHANGE_CLIENT_ID,
    login: str = LOGIN,
    account: str = MAPPED,
    password: str = BOUND_PASSWORD,
    moment: int = 1_000,
) -> None:
    """One living authorization under the reserved client: the row plan 23-05 will write."""
    await subject.save_client(client_id, metadata_json='{"client_id": "reserved"}', allowed=False)
    await subject.create_authorization(
        auth_id,
        client_id=client_id,
        nc_user=login,
        nc_account_id=account,
        app_password=password,
        scopes="nextcloud",
        resource="https://mcp.example.org/mcp",
        now=moment,
    )


def checked_claims(**overrides: Any) -> dict[str, Any]:
    """The checked claim set of an exchanged token, as the chain hands it over."""
    values: dict[str, Any] = {
        "iss": "https://idp.example.org/realms/f13",
        "sub": MAPPED,
        "azp": AZP,
    }
    values.update(overrides)
    return values


def authorization_rows(tmp_path: Path) -> int:
    """The row count of ``authorizations``, read out of the file behind the store's back."""
    conn = sqlite3.connect(tmp_path / STORE_FILE)
    try:
        return conn.execute("SELECT COUNT(*) FROM authorizations").fetchone()[0]
    finally:
        conn.close()


def corrupt_password_blob(tmp_path: Path, auth_id: str) -> None:
    """Damage the ciphertext of one row, which is what a changed data key looks like."""
    conn = sqlite3.connect(tmp_path / STORE_FILE)
    try:
        conn.execute(
            "UPDATE authorizations SET app_password_enc = ? WHERE auth_id = ?",
            (b"not-a-ciphertext", auth_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- the protocol and the happy path -------------------------------------------------------


def test_bound_accounts_satisfies_the_account_source_protocol(tmp_path: Path) -> None:
    """The one interface the chain asks; both operating modes have to fit it."""
    source = exchange_binding.BoundAccounts(opener_of(open_store(tmp_path)))
    assert isinstance(source, ExchangeAccounts)


@pytest.mark.anyio
async def test_a_bound_account_becomes_the_identity_of_its_authorization(tmp_path: Path) -> None:
    """The binding is an authorization like any other, and the identity is built from it."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    source = exchange_binding.BoundAccounts(opener_of(subject))
    claims = checked_claims()

    identity = await source.identity_for(MAPPED, claims)

    assert identity is not None
    assert identity.principal == MAPPED
    assert identity.nc_user == LOGIN
    assert identity.app_password == BOUND_PASSWORD
    assert identity.auth_id == "binding-1"
    assert identity.client_id == EXCHANGE_CLIENT_ID
    assert identity.actor == AZP
    assert identity.client_name == "", (
        "no client is registered here, so there is no registered name to carry"
    )
    assert identity.credential == CREDENTIAL_APP_PASSWORD
    assert identity.revoked is False


@pytest.mark.anyio
async def test_the_acting_party_is_read_from_the_claims_and_may_be_empty(tmp_path: Path) -> None:
    """No ``azp`` names nobody; the identity still stands, the audit line stays honest."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    source = exchange_binding.BoundAccounts(opener_of(subject))

    identity = await source.identity_for(MAPPED, {"sub": MAPPED})

    assert identity is not None
    assert identity.actor == ""


# --- every other state is one silent refusal, and none of them writes ----------------------


@pytest.mark.anyio
async def test_without_a_binding_the_answer_is_none_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    """No silent provisioning: a refusal leaves exactly the rows that were there before."""
    subject = open_store(tmp_path)
    await with_binding(subject, account="somebody-else", login="somebody-else")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    assert await source.identity_for(MAPPED, checked_claims()) is None
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_a_revoked_binding_is_a_refusal_that_writes_nothing(tmp_path: Path) -> None:
    """The read already skips a revoked row, and the refusal leaves the store untouched."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    await subject.revoke_authorization("binding-1")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    assert await source.identity_for(MAPPED, checked_claims()) is None
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_a_revocation_is_seen_by_the_very_next_call(tmp_path: Path) -> None:
    """Per request and without a cache: the widerruf of plan 23-06 acts at once."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    source = exchange_binding.BoundAccounts(opener_of(subject))
    assert await source.identity_for(MAPPED, checked_claims()) is not None

    await subject.revoke_authorization("binding-1")

    assert await source.identity_for(MAPPED, checked_claims()) is None


@pytest.mark.anyio
async def test_a_binding_of_another_client_is_a_refusal(tmp_path: Path) -> None:
    """A connection of a registered client is never the binding of the exchange path."""
    subject = open_store(tmp_path)
    await with_binding(subject, client_id="client-4711")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    assert await source.identity_for(MAPPED, checked_claims()) is None
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_an_unreadable_app_password_is_a_refusal_and_one_line_naming_the_type(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T-23-19: the line carries the exception type and never a principal, id or password."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    corrupt_password_blob(tmp_path, "binding-1")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    with caplog.at_level(logging.ERROR, logger="mcp_connector.oauth.exchange_binding"):
        assert await source.identity_for(MAPPED, checked_claims()) is None

    lines = [entry.getMessage() for entry in caplog.records]
    assert len(lines) == 1
    assert "DecryptionRejected" in lines[0]
    assert MAPPED not in lines[0]
    assert "binding-1" not in lines[0]
    assert BOUND_PASSWORD not in lines[0]
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_an_empty_stored_password_is_a_refusal(tmp_path: Path) -> None:
    """Empty is refused by its own check: it could also be a broken read, so it never acts."""
    subject = open_store(tmp_path)
    await with_binding(subject, password="")
    source = exchange_binding.BoundAccounts(opener_of(subject))

    assert await source.identity_for(MAPPED, checked_claims()) is None


@pytest.mark.anyio
async def test_a_store_that_cannot_be_opened_is_a_refusal_not_an_exception() -> None:
    """Fail closed without a 500: an unreadable store refuses this one call and nothing more."""

    async def broken_opener() -> OAuthStore:
        raise OSError("the volume is gone")

    source = exchange_binding.BoundAccounts(broken_opener)

    assert await source.identity_for(MAPPED, checked_claims()) is None


@pytest.mark.anyio
async def test_an_empty_principal_never_touches_the_store() -> None:
    """The app context owns nothing here, and the refusal costs no store call at all."""
    source = exchange_binding.BoundAccounts(exploding_opener())

    assert await source.identity_for("", checked_claims()) is None


@pytest.mark.anyio
async def test_a_row_of_another_principal_is_refused_by_the_ownership_check() -> None:
    """Belt and braces (T-23-16): the decision holds its own comparison, not only the query."""

    class WrongRowStore:
        """A store whose read answers with somebody else's row: the query filter is bypassed."""

        async def binding_of(self, principal: str, client_id: str) -> AuthorizationRow | None:
            del principal, client_id
            return AuthorizationRow(
                auth_id="binding-of-somebody-else",
                client_id=EXCHANGE_CLIENT_ID,
                nc_user="somebody-else",
                scopes="nextcloud",
                resource="https://mcp.example.org/mcp",
                created_at=1_000,
                revoked_at=None,
                nc_account_id="somebody-else",
            )

        async def app_password(self, auth_id: str) -> str | None:
            del auth_id
            return "a-password-that-may-never-act"

    async def opener() -> Any:
        return WrongRowStore()

    source = exchange_binding.BoundAccounts(opener)

    assert await source.identity_for(MAPPED, checked_claims()) is None


# --- what this module is forbidden to do, held as structure --------------------------------


def test_the_module_never_writes_and_never_logs_a_value() -> None:
    """The source is a read and a refusal, nothing else; the greps of the plan, held here."""
    import inspect

    src = inspect.getsource(exchange_binding)
    meaningful = [line for line in src.splitlines() if not line.lstrip().startswith("#")]
    body = "\n".join(meaningful)
    assert "create_authorization" not in body
    assert "INSERT" not in body
    assert "_write" not in body
    assert body.count("return None") >= 4
    assert "same_principal" in body
    assert "type(exc).__name__" in body


def test_the_claims_parameter_takes_any_mapping(tmp_path: Path) -> None:
    """The contract of the seam: the claim set rides along as a mapping, never a dict only."""
    import inspect

    signature = inspect.signature(exchange_binding.BoundAccounts.identity_for)
    annotation = signature.parameters["claims"].annotation
    assert annotation in (Mapping[str, Any], "Mapping[str, Any]")


# --- the standalone deployment: the binding acts, everything else is one 401 ----------------

ISSUER = "https://idp.example.org/realms/f13"
PUBLIC_URL = "https://mcp.example.org"
AUDIENCE = f"{PUBLIC_URL}{RESOURCE_SUFFIX}"
JWKS_URL = f"{ISSUER}{chain.DEFAULT_JWKS_PATH}"
KID = "key-1"
BASE_URL = "http://nc.test"
SECRET_KEY_HEX = "ab" * 32

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)

ARMED_ENV = {
    config.ENV_EXCHANGE_ENABLED: "1",
    config.ENV_EXCHANGE_ISSUER: ISSUER,
    config.ENV_EXCHANGE_AZP: AZP,
    config.ENV_PUBLIC_URL: PUBLIC_URL,
}


def serve_jwks() -> respx.Route:
    entry = json.loads(RSAAlgorithm.to_jwk(PRIVATE.public_key()))
    entry.update({"kid": KID, "use": "sig", "alg": "RS256"})
    return respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [entry]}))


def exchange_token(**overrides: Any) -> str:
    now = int(time.time())
    values: dict[str, Any] = {
        "iss": ISSUER,
        "sub": MAPPED,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "typ": "Bearer",
        "azp": AZP,
    }
    values.update(overrides)
    return jwt.encode(values, PRIVATE, algorithm="RS256", headers={"kid": KID})


def broken_signature_token() -> str:
    """The same token with a signature that holds nothing: valid shape, invalid proof."""
    header, payload, signature = exchange_token().split(".")
    return f"{header}.{payload}.{'A' * len(signature)}"


def standalone_env(tmp_path: Path) -> dict[str, str]:
    """The standalone deployment of ``entry_oauth`` with the exchange path armed."""
    storage = tmp_path / "storage"
    storage.mkdir()
    storage.chmod(0o700)
    key_file = tmp_path / "key"
    key_file.write_text(SECRET_KEY_HEX)
    key_file.chmod(0o600)
    return {
        config.ENV_URL: BASE_URL,
        config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH,
        config.ENV_PUBLIC_URL: PUBLIC_URL,
        config.ENV_OAUTH_STORAGE_DIR: str(storage),
        config.ENV_OAUTH_DATA_KEY_FILE: str(key_file),
        config.ENV_OIDC_ISSUER: "https://idp.example.com",
        config.ENV_OIDC_CLIENT_ID: "the-client-id",
        config.ENV_OIDC_PROVIDER_ID: "7",
        config.ENV_OIDC_MAPPING: "user_oidc_unique_uid_sub_v1",
        **{name: value for name, value in ARMED_ENV.items() if name != config.ENV_PUBLIC_URL},
    }


def app_store(tmp_path: Path) -> OAuthStore:
    """The very store file of the built application, opened with its configured data key.

    The file is laid down owner-only before the first write, because the application opens
    this same path strictly afterwards and its opener refuses any group or other bits on
    POSIX; SQLite alone would create the file with the umask default (0644).
    """
    path = tmp_path / "storage" / STORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    path.chmod(0o600)
    return OAuthStore(path, bytes.fromhex(SECRET_KEY_HEX))


def app_store_rows(tmp_path: Path) -> int:
    """The authorization rows of the application's store file; none when nothing wrote it."""
    path = tmp_path / "storage" / STORE_FILE
    if not path.exists():
        return 0
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM authorizations").fetchone()[0]
    finally:
        conn.close()


def post_mcp(client: TestClient, token: str) -> Any:
    return client.post(
        "/mcp",
        json={},
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )


@respx.mock
def test_the_401_without_a_binding_matches_the_401_of_a_broken_signature(tmp_path: Path) -> None:
    """Success criterion 4 of the phase, as a comparison of two real answers (T-23-17).

    The first token passes every rule of phase 21 and fails only at the missing binding; the
    second fails at the signature. Status, body and the complete headers have to be equal,
    so no caller can learn which of the checks fired, whether the account exists or whether
    it has a binding. And the refusal writes nothing: the store holds the same number of
    rows afterwards (T-23-18).
    """
    route = serve_jwks()
    app = entry_oauth.build_oauth_app(standalone_env(tmp_path))
    before = app_store_rows(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        first = post_mcp(client, exchange_token())
        second = post_mcp(client, broken_signature_token())

    assert first.status_code == 401
    assert second.status_code == 401
    assert first.content == second.content
    assert dict(first.headers) == dict(second.headers)
    assert "resource_metadata=" in first.headers["www-authenticate"]
    assert route.call_count >= 1, "the first token went through the whole checker"
    assert app_store_rows(tmp_path) == before, "the refusal left no row behind"


@respx.mock
def test_with_a_binding_the_same_token_passes_the_boundary_of_the_built_app(
    tmp_path: Path,
) -> None:
    """The wiring of the entry point, measured end to end: the very 401 of the test above
    becomes a pass the moment the account has a pre-granted binding in the store."""
    serve_jwks()
    env = standalone_env(tmp_path)
    asyncio.run(with_binding(app_store(tmp_path)))
    app = entry_oauth.build_oauth_app(env)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = post_mcp(client, exchange_token())

    assert response.status_code != 401, "the boundary resolved the binding to an identity"


class _ExplodingStoreBranch:
    """A store branch that flies apart on contact: the scaffold below never asks it."""

    async def verify_token(self, token: str) -> AccessToken | None:
        raise AssertionError("the store branch was asked about an exchange token")

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        raise AssertionError("the store branch was asked to resolve an exchange token")

    def invalidate(self) -> None:
        raise AssertionError("the store branch was emptied by a test that does not revoke")


@respx.mock
def test_a_bound_account_acts_towards_nextcloud_with_its_own_basic_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole credential way in one measurement: a real signed exchange token, the real
    chain over a real store, the real transport boundary, and the outgoing Nextcloud request
    of the tool carries Basic authentication with the login name and the bound app password.

    The tool is a stand-in for the same reason the proof of plan 23-02 used one: what this
    plan built is everything up to and including the credentials of the call, not the MCP
    protocol framing around a tool. ``deps.resolve_credentials`` is the real credential
    layer, and the captured request is a real outgoing request.
    """
    for name in (
        "NC_MCP_STATIC_BEARER",
        "NC_MCP_APP_PASSWORD",
        "NC_MCP_USER",
        "APP_ID",
        "APP_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(config.ENV_AUTH_MODE, config.AUTH_MODE_OAUTH)
    monkeypatch.setenv(config.ENV_URL, BASE_URL)
    serve_jwks()
    nextcloud = respx.get(f"{BASE_URL}/status.php").mock(return_value=httpx.Response(200, json={}))

    subject = open_store(tmp_path)
    asyncio.run(with_binding(subject))
    boundary = chain.build_chain(
        _ExplodingStoreBranch(),
        env=ARMED_ENV,
        accounts=exchange_binding.BoundAccounts(opener_of(subject)),
    )

    async def tool(request: Request) -> Response:
        ctx = SimpleNamespace(
            headers=dict(request.headers), request_context=SimpleNamespace(request=request)
        )
        credentials = deps.resolve_credentials(ctx)
        async with httpx.AsyncClient() as outgoing:
            answer = await outgoing.get(
                f"{credentials.base_url}/status.php",
                auth=(credentials.user, credentials.secret),
            )
        return PlainTextResponse("served" if answer.status_code == 200 else "failed")

    async def never_disabled(principal: str) -> bool:
        del principal
        return False

    app = Starlette(routes=[Route("/mcp", tool, methods=["POST"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = RequireOAuthBearer(
                route.app,
                {config.ENV_PUBLIC_URL: PUBLIC_URL},
                token_verifier=boundary,
                access_check=never_disabled,
            )

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post("/mcp", headers={"Authorization": f"Bearer {exchange_token()}"})

    assert response.status_code == 200
    assert response.text == "served"
    assert nextcloud.call_count == 1
    sent = nextcloud.calls.last.request
    expected = "Basic " + base64.b64encode(f"{LOGIN}:{BOUND_PASSWORD}".encode()).decode()
    assert sent.headers["Authorization"] == expected

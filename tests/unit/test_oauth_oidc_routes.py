"""The standalone OIDC browser routes: start a sign in, finish it, leave a proof.

Real SQLite store, real signed ID tokens, the provider mocked with respx. What is under test
is the part of the design that no library does for us: the start as a POST with its own
anti forgery value, the cookie binding of a sign in, one refusal page for every failed
callback, the account comparison before a proof exists, and the rotation of the browser
handle after success.
"""

import asyncio
import base64
import hashlib
import json
import logging
import sqlite3
import time
from collections.abc import Coroutine, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import crypto, oidc, oidc_routes, registry
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.store import FLOW_TTL, OAuthStore, token_hash

PUBLIC_URL = "https://mcp.example.com"
NEXTCLOUD_URL = "https://cloud.example.com"
ISSUER = "https://auth.example.com"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
AUTHORIZE_URL = f"{ISSUER}/oauth/v2/authorize"
TOKEN_URL = f"{ISSUER}/oauth/v2/token"
JWKS_URL = f"{ISSUER}/oauth/v2/keys"
OIDC_CLIENT_ID = "391054166463676676"
REDIRECT = f"{PUBLIC_URL}{oidc_routes.OIDC_CALLBACK_PATH}"
PROVIDER_ID = 2
SUB = "390763839257313538"
OTHER_SUB = "390763951463334146"
ACCOUNT = oidc.user_oidc_unique_uid_sub_v1(PROVIDER_ID, SUB)
KID = "key-1"

MCP_CLIENT_ID = "client-4711"
FLOW_ID = "flow-0001"
CODE = "authorization-code-from-the-provider"
KEY = bytes(range(32))

ENV = {config.ENV_PUBLIC_URL: PUBLIC_URL}
PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)

START = oidc_routes.OIDC_START_PATH
CALLBACK = oidc_routes.OIDC_CALLBACK_PATH
SIGN_IN = oidc_routes.SIGN_IN_COOKIE
PROOF = oidc_routes.PROOF_COOKIE


# --- fixtures ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / "oauth.sqlite3", KEY, oidc=True)


def run(awaitable: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(awaitable)


def with_flow(
    subject: OAuthStore,
    flow_id: str = FLOW_ID,
    *,
    account_id: str | None = ACCOUNT,
    signed_in: bool = True,
) -> None:
    async def work() -> None:
        await subject.save_client(MCP_CLIENT_ID, metadata_json="{}")
        await subject.create_flow(
            flow_id,
            client_id=MCP_CLIENT_ID,
            redirect_uri="https://client.example/callback",
            redirect_uri_explicit=True,
            code_challenge="challenge",
            state=None,
            scopes="nextcloud",
            resource=f"{PUBLIC_URL}/mcp",
            poll_token="poll-token",
        )
        if signed_in:
            await subject.create_authorization(
                flow_id,
                client_id=MCP_CLIENT_ID,
                nc_user="alice",
                nc_account_id=account_id or "placeholder",
                app_password="app-password",
                scopes="nextcloud",
                resource=f"{PUBLIC_URL}/mcp",
            )

    run(work())
    if signed_in and not account_id:
        # A row written before the account id column existed (None), or a damaged one ("").
        # The store no longer writes either, so the file is changed directly.
        conn = sqlite3.connect(subject.path)
        try:
            conn.execute(
                "UPDATE authorizations SET nc_account_id = ? WHERE auth_id = ?",
                (account_id, flow_id),
            )
            conn.commit()
        finally:
            conn.close()


def application(subject: OAuthStore, **settings_overrides: Any) -> Starlette:
    async def provide() -> OAuthStore:
        return subject

    provider = provider_module.NextcloudOAuthProvider(
        nextcloud=NextcloudTarget.from_url(NEXTCLOUD_URL),
        env=ENV,
        policy=registry.client_policy(ENV),
        store_provider=provide,
    )
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": REDIRECT,
        "provider_id": PROVIDER_ID,
    }
    values.update(settings_overrides)
    client = oidc.OidcClient(oidc.OidcSettings(**values))
    routes = oidc_routes.oidc_routes(
        ENV, provider=provider, client=client, throttle=throttle_module.Throttle()
    )
    return Starlette(routes=routes)


def browser(app: Starlette) -> TestClient:
    return TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)


class Idp:
    """The mocked provider plus what the last start sent to it."""

    def __init__(self, router: respx.MockRouter) -> None:
        self.router = router
        self.state: dict[str, str] = {}

    def post(self, url: str) -> respx.Route:
        return self.router.post(url)


@pytest.fixture
def idp() -> Iterator[Idp]:
    with respx.mock(assert_all_called=False) as router:
        router.get(DISCOVERY_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": AUTHORIZE_URL,
                    "token_endpoint": TOKEN_URL,
                    "jwks_uri": JWKS_URL,
                    "response_modes_supported": ["query"],
                    "code_challenge_methods_supported": ["S256"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        )
        public = json.loads(RSAAlgorithm.to_jwk(PRIVATE.public_key()))
        public.update({"kid": KID, "use": "sig", "alg": "RS256"})
        router.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [public]}))
        yield Idp(router)


def id_token(nonce: str, **overrides: Any) -> str:
    now = int(time.time())
    values: dict[str, Any] = {
        "iss": ISSUER,
        "sub": SUB,
        "aud": OIDC_CLIENT_ID,
        "exp": now + 300,
        "iat": now,
        "nonce": nonce,
    }
    values.update(overrides)
    return jwt.encode(values, PRIVATE, algorithm="RS256", headers={"kid": KID})


def answer_with(idp: Idp, **overrides: Any) -> respx.Route:
    """The token endpoint answers with an ID token for the nonce of the last start."""

    def reply(request: httpx.Request) -> httpx.Response:
        nonce = idp.state["nonce"]
        return httpx.Response(200, json={"id_token": id_token(nonce, **overrides)})

    return idp.post(TOKEN_URL).mock(side_effect=reply)


def confirm(subject: OAuthStore, flow_id: str = FLOW_ID) -> str:
    return subject.form_token(flow_id, purpose=crypto.PURPOSE_OIDC_START)


def set_cookies(response: Any) -> dict[str, str]:
    """``Any``: the test client answers with the ``httpx2`` response type (see test_oauth_abuse)."""
    return {line.split("=", 1)[0]: line for line in response.headers.get_list("set-cookie")}


def cookie_value(response: Any, name: str) -> str:
    return set_cookies(response)[name].split(";", 1)[0].split("=", 1)[1]


def start(
    client: TestClient,
    subject: OAuthStore,
    idp: Idp | None = None,
    *,
    cookie: str | None = None,
    flow_id: str = FLOW_ID,
) -> Any:
    client.cookies.clear()
    headers = {} if cookie is None else {"cookie": cookie}
    response = client.post(
        START,
        data={"flow": flow_id, "confirm": confirm(subject, flow_id)},
        headers=headers,
    )
    client.cookies.clear()
    if idp is not None and response.status_code == 303:
        query = parse_qs(urlsplit(response.headers["location"]).query)
        idp.state = {
            "state": query["state"][0],
            "nonce": query["nonce"][0],
            "challenge": query["code_challenge"][0],
            "handle": cookie_value(response, SIGN_IN),
        }
    return response


def callback(
    client: TestClient, query: str, *, cookie: str | None = None, method: str = "GET"
) -> Any:
    client.cookies.clear()
    headers = {} if cookie is None else {"cookie": cookie}
    response = client.request(method, f"{CALLBACK}?{query}", headers=headers)
    client.cookies.clear()
    return response


def good_query(idp: Idp, **extra: str) -> str:
    return f"state={idp.state['state']}&code={CODE}" + "".join(
        f"&{key}={value}" for key, value in extra.items()
    )


def own_cookie(idp: Idp) -> str:
    return f"{SIGN_IN}={idp.state['handle']}"


def open_sign_ins(subject: OAuthStore) -> int:
    conn = sqlite3.connect(subject.path)
    try:
        return conn.execute("SELECT COUNT(*) FROM oidc_transactions").fetchone()[0]
    finally:
        conn.close()


def proofs(subject: OAuthStore) -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(subject.path)
    try:
        return conn.execute("SELECT proof_hash, flow_id, principal FROM oidc_proofs").fetchall()
    finally:
        conn.close()


# --- start ------------------------------------------------------------------------------


def test_a_start_sends_the_browser_to_the_provider(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    response = start(browser(application(store)), store, idp)

    assert response.status_code == 303
    target = urlsplit(response.headers["location"])
    assert f"{target.scheme}://{target.netloc}{target.path}" == AUTHORIZE_URL
    query = parse_qs(target.query)
    assert query["response_type"] == ["code"]
    assert query["response_mode"] == ["query"]
    assert query["client_id"] == [OIDC_CLIENT_ID]
    assert query["redirect_uri"] == [REDIRECT]
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid"]
    assert len(query["state"][0]) == 43
    assert len(query["nonce"][0]) == 43
    assert query["state"] != query["nonce"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert open_sign_ins(store) == 1


def test_the_sign_in_cookie_is_a_host_cookie(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    response = start(browser(application(store)), store, idp)

    line = set_cookies(response)[SIGN_IN]
    attributes = {part.strip().lower() for part in line.split(";")[1:]}
    assert {"secure", "httponly", "samesite=lax", "path=/", "max-age=300"} <= attributes
    assert not any(part.startswith("domain") for part in attributes)
    assert PROOF not in set_cookies(response)


def test_the_store_keeps_only_digests_of_state_and_handle(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    start(browser(application(store)), store, idp)
    conn = sqlite3.connect(store.path)
    try:
        state_hash, browser_hash = conn.execute(
            "SELECT state_hash, browser_hash FROM oidc_transactions"
        ).fetchone()
    finally:
        conn.close()
    assert state_hash == token_hash(idp.state["state"])
    assert browser_hash == token_hash(idp.state["handle"])
    raw = b"".join(p.read_bytes() for p in store.path.parent.iterdir() if p.is_file())
    for secret in (idp.state["state"], idp.state["nonce"], idp.state["handle"]):
        assert secret.encode() not in raw


def test_a_get_starts_nothing(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    response = browser(application(store)).get(f"{START}?flow={FLOW_ID}&confirm={confirm(store)}")
    assert response.status_code == 405
    assert open_sign_ins(store) == 0


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"flow": FLOW_ID},
        {"flow": FLOW_ID, "confirm": "forged"},
        {"flow": "", "confirm": "x"},
    ],
    ids=["nothing", "no value", "forged value", "no flow"],
)
def test_a_start_without_its_anti_forgery_value_is_refused(
    store: OAuthStore, idp: Idp, data: dict[str, str]
) -> None:
    with_flow(store)
    response = browser(application(store)).post(START, data=data)
    assert response.status_code == 400
    assert open_sign_ins(store) == 0
    assert SIGN_IN not in set_cookies(response)


def test_the_consent_value_does_not_start_a_sign_in(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    consent_value = store.form_token(FLOW_ID, purpose=crypto.PURPOSE_CONSENT)
    response = browser(application(store)).post(
        START, data={"flow": FLOW_ID, "confirm": consent_value}
    )
    assert response.status_code == 400
    assert open_sign_ins(store) == 0


def test_the_value_of_another_flow_is_refused(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    with_flow(store, "flow-0002")
    response = browser(application(store)).post(
        START, data={"flow": FLOW_ID, "confirm": confirm(store, "flow-0002")}
    )
    assert response.status_code == 400
    assert open_sign_ins(store) == 0


@pytest.mark.parametrize(
    ("signed_in", "account_id"),
    [(False, ACCOUNT), (True, None), (True, "")],
    ids=["sign in not finished", "legacy row without account id", "empty account id"],
)
def test_a_start_needs_an_authorization_with_an_account_id(
    store: OAuthStore, idp: Idp, signed_in: bool, account_id: str | None
) -> None:
    with_flow(store, signed_in=signed_in, account_id=account_id)
    response = start(browser(application(store)), store)
    assert response.status_code == 400
    assert open_sign_ins(store) == 0


def test_a_start_for_an_unknown_flow_is_refused(store: OAuthStore, idp: Idp) -> None:
    response = start(browser(application(store)), store, flow_id="flow-unknown")
    assert response.status_code == 400


def test_an_unreachable_provider_leaves_no_sign_in(store: OAuthStore) -> None:
    with_flow(store)
    with respx.mock() as mocked:
        mocked.get(DISCOVERY_URL).mock(return_value=httpx.Response(503))
        response = start(browser(application(store)), store)
    assert response.status_code == 500
    assert open_sign_ins(store) == 0


def test_a_browser_keeps_its_handle_and_its_cap(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    first = start(client, store, idp)
    handle = cookie_value(first, SIGN_IN)
    for _ in range(2):
        again = start(client, store, cookie=f"{SIGN_IN}={handle}")
        assert again.status_code == 303
        assert cookie_value(again, SIGN_IN) == handle
    capped = start(client, store, cookie=f"{SIGN_IN}={handle}")
    assert capped.status_code == 400
    assert open_sign_ins(store) == 3


@pytest.mark.parametrize(
    "cookie",
    [f"{SIGN_IN}=short", f"{SIGN_IN}={'a' * 43}; {SIGN_IN}={'b' * 43}"],
    ids=["malformed", "ambiguous"],
)
def test_an_unusable_handle_is_replaced(store: OAuthStore, idp: Idp, cookie: str) -> None:
    with_flow(store)
    response = start(browser(application(store)), store, cookie=cookie)
    assert response.status_code == 303
    handle = cookie_value(response, SIGN_IN)
    assert handle not in (("a" * 43), ("b" * 43), "short")
    assert len(handle) == 43


def test_every_start_is_counted(store: OAuthStore, idp: Idp) -> None:
    client = browser(application(store))
    statuses = [
        client.post(START, data={}).status_code for _ in range(throttle_module.FLOW_LIMIT + 1)
    ]
    assert statuses[:-1] == [400] * throttle_module.FLOW_LIMIT
    assert statuses[-1] == 429


def test_an_exapp_store_cannot_start_a_sign_in(tmp_path: Path, idp: Idp) -> None:
    subject = OAuthStore(tmp_path / "exapp.sqlite3", KEY)
    with_flow(subject)
    response = start(browser(application(subject)), subject)
    assert response.status_code == 500


# --- callback ---------------------------------------------------------------------------


def test_a_callback_leaves_a_proof_and_goes_back_to_consent(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    token_route = answer_with(idp)

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 303
    assert response.headers["location"] == f"/authorize/consent?flow={FLOW_ID}"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    cookies = set_cookies(response)
    proof = cookie_value(response, PROOF)
    assert len(proof) == 43
    assert proof != idp.state["handle"]
    proof_attributes = {part.strip().lower() for part in cookies[PROOF].split(";")[1:]}
    assert {"secure", "httponly", "samesite=lax", "path=/", "max-age=300"} <= proof_attributes
    dropped = {part.strip().lower() for part in cookies[SIGN_IN].split(";")[1:]}
    assert "max-age=0" in dropped
    assert {"secure", "path=/"} <= dropped

    assert run(store.browser_proof_principal(proof_handle=proof, flow_id=FLOW_ID)) == ACCOUNT
    assert proofs(store) == [(token_hash(proof), FLOW_ID, ACCOUNT)]
    assert open_sign_ins(store) == 0

    sent = parse_qs(token_route.calls.last.request.content.decode())
    assert sent["code"] == [CODE]
    assert sent["redirect_uri"] == [REDIRECT]
    verifier = sent["code_verifier"][0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge.rstrip(b"=").decode() == idp.state["challenge"]


def test_a_callback_is_single_use(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    token_route = answer_with(idp)

    assert callback(client, good_query(idp), cookie=own_cookie(idp)).status_code == 303
    replay = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert replay.status_code == 400
    assert token_route.call_count == 1
    assert len(proofs(store)) == 1


@pytest.mark.parametrize(
    "cookie",
    [None, f"{SIGN_IN}={'c' * 43}", "ambiguous"],
    ids=["no cookie", "another browser", "ambiguous cookie"],
)
def test_a_callback_from_another_browser_ends_the_sign_in(
    store: OAuthStore, idp: Idp, cookie: str | None
) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    token_route = answer_with(idp)
    if cookie == "ambiguous":
        cookie = f"{own_cookie(idp)}; {SIGN_IN}={'c' * 43}"

    refused = callback(client, good_query(idp), cookie=cookie)
    late = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert refused.status_code == 400
    assert late.status_code == 400
    assert token_route.call_count == 0
    assert proofs(store) == []
    assert PROOF not in set_cookies(refused)


def test_an_unknown_state_touches_no_other_sign_in(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp)

    assert (
        callback(client, f"state={'x' * 43}&code={CODE}", cookie=own_cookie(idp)).status_code == 400
    )
    assert open_sign_ins(store) == 1
    assert callback(client, good_query(idp), cookie=own_cookie(idp)).status_code == 303


@pytest.mark.parametrize(
    "query",
    [
        "code=abc",
        "state=&code=abc",
        "state=short&code=abc",
        "state={state}&state={state}&code=abc",
    ],
    ids=["no state", "empty state", "malformed state", "repeated state"],
)
def test_a_callback_without_one_usable_state_consumes_nothing(
    store: OAuthStore, idp: Idp, query: str
) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp)

    response = callback(client, query.format(state=idp.state["state"]), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert open_sign_ins(store) == 1


@pytest.mark.parametrize(
    "query",
    [
        "state={state}",
        "state={state}&code=",
        "state={state}&code=a&code=b",
        "state={state}&code=" + "a" * (oidc_routes.MAX_CODE_LENGTH + 1),
        "state={state}&error=access_denied",
        "state={state}&code=abc&error=access_denied",
        "state={state}&code=abc&iss=https://evil.example.com",
        f"state={{state}}&code=abc&iss={ISSUER}&iss={ISSUER}",
    ],
    ids=[
        "no code",
        "empty code",
        "repeated code",
        "oversized code",
        "cancelled",
        "code and error",
        "foreign issuer",
        "repeated issuer",
    ],
)
def test_a_bad_answer_ends_the_sign_in_without_an_exchange(
    store: OAuthStore, idp: Idp, query: str
) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    token_route = answer_with(idp)

    response = callback(client, query.format(state=idp.state["state"]), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert token_route.call_count == 0
    assert open_sign_ins(store) == 0
    assert proofs(store) == []


def test_a_matching_issuer_parameter_is_accepted(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp)
    response = callback(client, good_query(idp, iss=ISSUER), cookie=own_cookie(idp))
    assert response.status_code == 303


@pytest.mark.parametrize(
    "overrides",
    [
        {"sub": OTHER_SUB},
        {"nonce": "another-nonce"},
        {"aud": "another-client"},
        {"iss": "https://evil.example.com"},
        {"exp": int(time.time()) - 3600},
    ],
    ids=["another account", "another nonce", "another audience", "another issuer", "expired"],
)
def test_no_proof_without_a_valid_token_for_this_account(
    store: OAuthStore, idp: Idp, overrides: dict[str, Any]
) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    if "nonce" in overrides:
        idp.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"id_token": id_token(**overrides)})
        )
    else:
        answer_with(idp, **overrides)

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert proofs(store) == []
    assert PROOF not in set_cookies(response)


def test_a_token_error_is_one_refusal(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    idp.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert proofs(store) == []


def test_an_unreachable_token_endpoint_is_one_refusal(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    idp.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("down"))

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert proofs(store) == []


def test_a_revoked_authorization_gets_no_proof(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp)
    run(store.revoke_authorization(FLOW_ID))

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert proofs(store) == []


def test_a_login_name_is_never_the_standalone_identity(store: OAuthStore, idp: Idp) -> None:
    """A row whose account id equals its login name still needs the mapped id to match."""
    with_flow(store, account_id="alice")
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp, sub="alice")

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert proofs(store) == []


@pytest.mark.parametrize("method", ["HEAD", "POST"])
def test_only_a_get_can_finish_a_sign_in(store: OAuthStore, idp: Idp, method: str) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp)

    response = callback(client, good_query(idp), cookie=own_cookie(idp), method=method)

    assert response.status_code == 405
    assert open_sign_ins(store) == 1


def test_a_flow_that_ran_out_gets_no_proof(store: OAuthStore, idp: Idp) -> None:
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp)
    conn = sqlite3.connect(store.path)
    try:
        conn.execute("UPDATE flows SET expires_at = ?", (int(time.time()) - 1,))
        conn.commit()
    finally:
        conn.close()

    response = callback(client, good_query(idp), cookie=own_cookie(idp))

    assert response.status_code == 400
    assert proofs(store) == []


def test_refused_callbacks_are_counted(store: OAuthStore, idp: Idp) -> None:
    client = browser(application(store))
    statuses = [
        callback(client, f"state={'x' * 43}&code=abc").status_code
        for _ in range(throttle_module.FAILURE_LIMIT + 1)
    ]
    assert statuses[-1] == 429


def test_an_exapp_store_refuses_a_callback_without_an_error(tmp_path: Path, idp: Idp) -> None:
    subject = OAuthStore(tmp_path / "exapp.sqlite3", KEY)
    response = callback(browser(application(subject)), f"state={'x' * 43}&code=abc")
    assert response.status_code == 400


def test_no_secret_reaches_the_log(
    store: OAuthStore, idp: Idp, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with_flow(store)
    client = browser(application(store))
    start(client, store, idp)
    answer_with(idp, sub=OTHER_SUB)

    callback(client, good_query(idp), cookie=own_cookie(idp))

    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("mcp_connector")
    )
    assert "another account" in logged
    for secret in (idp.state["state"], idp.state["nonce"], idp.state["handle"], CODE, OTHER_SUB):
        assert secret not in logged


def test_the_flow_lifetime_is_the_outer_bound(store: OAuthStore, idp: Idp) -> None:
    """A sign in never outlives the flow it belongs to (store rule, seen through the route)."""
    with_flow(store)
    start(browser(application(store)), store, idp)
    conn = sqlite3.connect(store.path)
    try:
        (expires_at,) = conn.execute("SELECT expires_at FROM oidc_transactions").fetchone()
        (flow_expires_at,) = conn.execute("SELECT expires_at FROM flows").fetchone()
    finally:
        conn.close()
    assert expires_at <= flow_expires_at
    assert flow_expires_at - int(time.time()) <= FLOW_TTL

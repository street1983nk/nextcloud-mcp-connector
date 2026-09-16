"""The OIDC client of the standalone browser identity, against a simulated provider.

Keys are generated per test run, every provider answer is served by respx, and nothing
opens a socket. The rules under test are the ones of ``oauth/oidc.py``: pinned issuer and
origin, S256 only, asymmetric algorithms only, strict ID token validation and the named
user_oidc mapping.
"""

import base64
import hashlib
import json
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from mcp_connector.oauth import oidc

ISSUER = "https://auth.example.com"
CLIENT_ID = "391054166463676676"
REDIRECT = "https://mcp.example.com/oidc/callback"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
AUTHORIZE_URL = f"{ISSUER}/oauth/v2/authorize"
TOKEN_URL = f"{ISSUER}/oauth/v2/token"
JWKS_URL = f"{ISSUER}/oauth/v2/keys"
NONCE = "nonce-of-this-sign-in"
SUB = "390763839257313538"
KID = "key-1"
SHARED_SECRET = "client-secret-long-enough-for-hmac-sha256-0123456789"

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwk_of(private: rsa.RSAPrivateKey, kid: str = KID, **extra: str) -> dict[str, Any]:
    entry = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    entry.update({"kid": kid, "use": "sig", "alg": "RS256"}, **extra)
    return entry


def unsigned_token() -> str:
    """An ID token with ``alg: none`` and an empty signature."""

    def part(value: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT', 'kid': KID})}.{part(claims())}."


def discovery(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "issuer": ISSUER,
        "authorization_endpoint": AUTHORIZE_URL,
        "token_endpoint": TOKEN_URL,
        "jwks_uri": JWKS_URL,
        "response_modes_supported": ["query", "fragment", "form_post"],
        "code_challenge_methods_supported": ["S256"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["EdDSA", "RS256", "ES256"],
    }
    document.update(overrides)
    return {key: value for key, value in document.items() if value is not None}


def claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    values: dict[str, Any] = {
        "iss": ISSUER,
        "sub": SUB,
        "aud": CLIENT_ID,
        "exp": now + 300,
        "iat": now,
        "nonce": NONCE,
    }
    values.update(overrides)
    return {key: value for key, value in values.items() if value is not None}


def token(
    private: Any = PRIVATE, *, algorithm: str = "RS256", kid: str | None = KID, **overrides: Any
) -> str:
    headers = {} if kid is None else {"kid": kid}
    return jwt.encode(claims(**overrides), private, algorithm=algorithm, headers=headers)


def settings(**overrides: Any) -> oidc.OidcSettings:
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
        "provider_id": 2,
        "client_secret": "client-secret",
    }
    values.update(overrides)
    return oidc.OidcSettings(**values)


def provider(
    document: dict[str, Any] | None = None, keys: list[dict[str, Any]] | None = None
) -> None:
    respx.get(DISCOVERY_URL).mock(
        return_value=httpx.Response(200, json=document if document is not None else discovery())
    )
    respx.get(JWKS_URL).mock(
        return_value=httpx.Response(
            200, json={"keys": keys if keys is not None else [jwk_of(PRIVATE)]}
        )
    )


# --- settings ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"issuer": "http://auth.example.com"},
        {"issuer": "https://auth.example.com/"},
        {"issuer": "https://auth.example.com?x=1"},
        {"redirect_uri": "http://mcp.example.com/cb"},
        {"client_id": " "},
        {"provider_id": 0},
        {"provider_id": True},
        {"strategy": "something_else"},
        {"subject_type": "pairwise"},
        {"client_secret": ""},
        {"algorithms": ("HS256",)},
        {"algorithms": ("none",)},
        {"algorithms": ()},
    ],
)
def test_a_bad_configuration_is_refused(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"."):
        settings(**overrides)


def test_the_secret_never_shows_in_the_repr() -> None:
    assert "client-secret" not in repr(settings())


def test_the_mapping_reproduces_user_oidc() -> None:
    expected = hashlib.sha256(f"2_0_{SUB}".encode()).hexdigest()
    assert oidc.user_oidc_unique_uid_sub_v1(2, SUB) == expected
    assert oidc.OidcClient(settings()).account_id_for({"sub": SUB}) == expected


def test_the_pkce_challenge_is_s256() -> None:
    verifier = oidc.new_code_verifier()
    assert 43 <= len(verifier) <= 128
    digest = hashlib.sha256(verifier.encode()).digest()
    assert oidc.code_challenge(verifier) == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# --- discovery --------------------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_the_authorization_url_carries_every_required_parameter() -> None:
    provider()
    url = await oidc.OidcClient(settings()).authorization_url(
        state="s", nonce=NONCE, code_verifier="v" * 43
    )

    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == AUTHORIZE_URL
    query = {key: values[0] for key, values in parse_qs(parts.query).items()}
    assert query == {
        "response_type": "code",
        "response_mode": "query",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
        "scope": "openid",
        "state": "s",
        "nonce": NONCE,
        "code_challenge": oidc.code_challenge("v" * 43),
        "code_challenge_method": "S256",
    }


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "document",
    [
        discovery(issuer="https://auth.example.com/"),
        discovery(issuer="https://evil.example.com"),
        discovery(token_endpoint="https://evil.example.com/token"),
        discovery(jwks_uri="http://auth.example.com/keys"),
        discovery(authorization_endpoint="https://auth.example.com:8443/authorize"),
        discovery(code_challenge_methods_supported=["plain"]),
        discovery(code_challenge_methods_supported=None),
        discovery(response_modes_supported=["form_post"]),
        discovery(subject_types_supported=["pairwise"]),
        discovery(id_token_signing_alg_values_supported=["HS256"]),
    ],
    ids=[
        "trailing slash",
        "other issuer",
        "foreign token endpoint",
        "plain http jwks",
        "other port",
        "no S256",
        "no PKCE methods",
        "no query mode",
        "pairwise only",
        "no shared algorithm",
    ],
)
async def test_a_discovery_that_breaks_a_rule_is_refused(document: dict[str, Any]) -> None:
    provider(document)
    with pytest.raises(oidc.OidcRefused):
        await oidc.OidcClient(settings()).metadata()


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://evil.example.com/"}),
        httpx.Response(500),
        httpx.Response(200, text="not json"),
        httpx.Response(200, content=b"{" + b" " * (oidc.MAX_RESPONSE_BYTES + 1) + b"}"),
    ],
    ids=["redirect", "server error", "not json", "too large"],
)
async def test_an_unusable_discovery_answer_is_refused(response: httpx.Response) -> None:
    respx.get(DISCOVERY_URL).mock(return_value=response)
    with pytest.raises(oidc.OidcRefused):
        await oidc.OidcClient(settings()).metadata()


# --- token exchange ---------------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_the_exchange_sends_pkce_and_client_auth_and_validates_the_token() -> None:
    provider()
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"id_token": token(), "access_token": "x"})
    )

    found = await oidc.OidcClient(settings()).exchange(
        code="the-code", code_verifier="v" * 43, nonce=NONCE
    )

    assert found["sub"] == SUB
    sent = route.calls.last.request
    form = {key: values[0] for key, values in parse_qs(sent.content.decode()).items()}
    assert form == {
        "grant_type": "authorization_code",
        "code": "the-code",
        "redirect_uri": REDIRECT,
        "code_verifier": "v" * 43,
        "client_id": CLIENT_ID,
    }
    expected = base64.b64encode(f"{CLIENT_ID}:client-secret".encode()).decode()
    assert sent.headers["Authorization"] == f"Basic {expected}"
    assert "cookie" not in {name.lower() for name in sent.headers}


@respx.mock
@pytest.mark.anyio
async def test_a_public_client_sends_no_authorization_header() -> None:
    provider()
    route = respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"id_token": token()}))

    await oidc.OidcClient(settings(client_secret=None)).exchange(
        code="c", code_verifier="v" * 43, nonce=NONCE
    )

    assert "authorization" not in {name.lower() for name in route.calls.last.request.headers}


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": "invalid_grant"}),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"id_token": ""}),
    ],
    ids=["refused grant", "no id token", "empty id token"],
)
async def test_a_failed_exchange_is_refused(response: httpx.Response) -> None:
    provider()
    respx.post(TOKEN_URL).mock(return_value=response)
    with pytest.raises(oidc.OidcRefused):
        await oidc.OidcClient(settings()).exchange(code="c", code_verifier="v" * 43, nonce=NONCE)


# --- ID token ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_valid_token_passes() -> None:
    provider()
    found = await oidc.OidcClient(settings()).validate_id_token(token(), nonce=NONCE)
    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad",
    [
        lambda: token(iss="https://evil.example.com"),
        lambda: token(aud="another-client"),
        lambda: token(aud=[CLIENT_ID, "another-client"]),
        lambda: token(aud=[CLIENT_ID, "another-client"], azp="another-client"),
        lambda: token(azp="another-client"),
        lambda: token(exp=int(time.time()) - 3600),
        lambda: token(nonce="another-nonce"),
        lambda: token(nonce=None),
        lambda: token(sub=None),
        lambda: token(sub=""),
        lambda: token(sub=" padded"),
        lambda: token(iat=None),
        lambda: token(OTHER_PRIVATE),
        lambda: token(kid="unknown-key"),
        lambda: token(kid=None),
        lambda: token(algorithm="RS512"),
        lambda: jwt.encode(claims(), SHARED_SECRET, algorithm="HS256", headers={"kid": KID}),
        unsigned_token,
        lambda: token() + "x",
        lambda: "not.a.token",
    ],
    ids=[
        "issuer",
        "audience",
        "several audiences without azp",
        "azp of another party",
        "azp mismatch",
        "expired",
        "nonce",
        "no nonce",
        "no sub",
        "empty sub",
        "padded sub",
        "no iat",
        "foreign signature",
        "unknown kid",
        "no kid",
        "unconfigured algorithm",
        "symmetric algorithm",
        "no signature",
        "tampered",
        "garbage",
    ],
)
async def test_a_token_that_breaks_a_rule_is_refused(bad: Any) -> None:
    provider()
    with pytest.raises(oidc.OidcRefused):
        await oidc.OidcClient(settings()).validate_id_token(bad(), nonce=NONCE)


@respx.mock
@pytest.mark.anyio
async def test_several_audiences_with_the_right_azp_pass() -> None:
    provider()
    found = await oidc.OidcClient(settings()).validate_id_token(
        token(aud=[CLIENT_ID, "other"], azp=CLIENT_ID), nonce=NONCE
    )
    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "entry",
    [
        {"kty": "oct", "k": base64.urlsafe_b64encode(SHARED_SECRET.encode()).decode(), "kid": KID},
        jwk_of(PRIVATE, use="enc"),
        jwk_of(PRIVATE, alg="RS512"),
    ],
    ids=["symmetric key", "encryption key", "key for another algorithm"],
)
async def test_a_key_that_may_not_sign_is_ignored(entry: dict[str, Any]) -> None:
    provider(keys=[entry])
    with pytest.raises(oidc.OidcRefused):
        await oidc.OidcClient(settings()).validate_id_token(token(), nonce=NONCE)


@respx.mock
@pytest.mark.anyio
async def test_an_unknown_kid_refetches_the_keys_once() -> None:
    respx.get(DISCOVERY_URL).mock(return_value=httpx.Response(200, json=discovery()))
    keys = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE), jwk_of(OTHER_PRIVATE, "key-2")]}),
            httpx.Response(200, json={"keys": []}),
        ]
    )
    client = oidc.OidcClient(settings())

    await client.validate_id_token(token(), nonce=NONCE)
    await client.validate_id_token(token(), nonce=NONCE)
    assert keys.call_count == 1, "a known kid is served from the cache"
    await client.validate_id_token(token(OTHER_PRIVATE, kid="key-2"), nonce=NONCE)
    assert keys.call_count == 2, "an unknown kid costs exactly one refetch"


@respx.mock
@pytest.mark.anyio
async def test_the_key_cache_expires() -> None:
    respx.get(DISCOVERY_URL).mock(return_value=httpx.Response(200, json=discovery()))
    keys = respx.get(JWKS_URL).mock(
        return_value=httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]})
    )
    moment = [1_000.0]
    client = oidc.OidcClient(settings(), clock=lambda: moment[0])

    await client.validate_id_token(token(), nonce=NONCE)
    moment[0] += oidc.JWKS_CACHE_SECONDS + 1
    await client.validate_id_token(token(), nonce=NONCE)

    assert keys.call_count == 2


@respx.mock
@pytest.mark.anyio
async def test_refusals_log_no_token_nonce_or_secret(caplog: pytest.LogCaptureFixture) -> None:
    provider()
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"id_token": token(nonce="x")})
    )
    with caplog.at_level("DEBUG", logger="mcp_connector"), pytest.raises(oidc.OidcRefused):
        await oidc.OidcClient(settings()).exchange(
            code="the-code", code_verifier="v" * 43, nonce=NONCE
        )

    for secret in ("the-code", "v" * 43, NONCE, "client-secret", SUB):
        assert secret not in caplog.text

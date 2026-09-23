"""The provider half of the authorization server: who may register, and who may come back.

The SDK owns the HTTP shape of ``/authorize``, ``/token``, ``/register`` and ``/revoke``;
what it deliberately does not own is the policy behind them. These checks cover the two
places this plan fills: ``register_client``, which is the door, and ``get_client``, which
is the enforcement point every later request passes through (pitfall 9, T-03-40).

Threats covered here: T-03-40 (a blocked client that keeps working), T-03-41 (an open
redirect through a registered address), T-03-44 (a registry that grows without a bound),
T-03-45 (a registration answer in a proxy cache) and T-03-47 (an error that tells the
caller which check fired).

Nothing here starts a container or opens a socket: the store is a SQLite file in
``tmp_path`` and no Nextcloud is called at all.
"""

import ast
import base64
import hashlib
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    IdentityAssertionParams,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import InvalidRedirectUriError, OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config, entry_http
from mcp_connector.entry_exapp import MCP_PATH, build_exapp_app
from mcp_connector.exapp.middleware import RequireAppApi
from mcp_connector.exapp.target import exapp_target
from mcp_connector.oauth import cimd, exchange_accounts, loginflow, metadata, registry
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.store import (
    ACCESS_TOKEN_TTL,
    FLOW_TTL,
    IDLE_CLIENT_TTL,
    UNUSED_CLIENT_TTL,
    OAuthStore,
    token_hash,
)
from mcp_connector.oauth.verifier import StoreTokenVerifier

PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
BASE_URL = "http://nc.test"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
SECRET = "0123456789abcdef0123456789abcdef"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

ENV = {
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.1.0",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}

AS_PATHS = ("/authorize", "/token", "/register", "/revoke")

#: What Cursor sends to ``/register`` in one body, measured against staging on 2026-08-16
#: (03-09-MEASUREMENTS.md, run 4). The first entry is a private-use URI scheme, which D-35
#: refuses and BL-04 keeps refusing; the other two are registrable.
CURSOR_URIS = [
    "cursor://anysphere.cursor-mcp/oauth/callback",
    "https://www.cursor.com/agents/mcp/oauth/callback",
    "http://localhost:8787/callback",
]
CURSOR_REGISTRABLE = CURSOR_URIS[1:]

#: The candidate client of AUTH-08 and its document, measured on 2026-08-20 (the same run
#: ``test_oauth_cimd.py`` carries its copy from). Both return addresses are port less, which
#: is what the port rule of plan 06-03 is about.
CIMD_ID = "https://claude.ai/oauth/claude-code-client-metadata"
CIMD_URIS = ["http://localhost/callback", "http://127.0.0.1/callback"]
CIMD_DOCUMENT: dict[str, object] = {
    "client_id": CIMD_ID,
    "client_name": "Claude Code",
    "client_uri": "https://claude.ai",
    "redirect_uris": CIMD_URIS,
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}

#: The address the name of the identifier resolves to in this file, and the URL a pinned
#: fetch therefore asks for. No name is ever resolved here: every provider these tests build
#: carries a resolver that answers this literal, so ``respx`` sees the pinned request and no
#: socket is opened (the injection form of ``clock`` and ``store_provider``).
CIMD_IP = "93.184.216.34"
CIMD_FETCH_URL = "https://93.184.216.34/oauth/claude-code-client-metadata"


def opener(subject: OAuthStore) -> Callable[[], Awaitable[OAuthStore]]:
    async def open_it() -> OAuthStore:
        return subject

    return open_it


def resolving(*addresses: str) -> Callable[[str, int], Awaitable[list[str]]]:
    """A resolver that answers with these literals, so no name of a test is looked up."""

    async def resolve(host: str, port: int) -> list[str]:
        return list(addresses)

    return resolve


def build(tmp_path: Path, **env: str) -> tuple[provider_module.NextcloudOAuthProvider, OAuthStore]:
    """A provider on a real store file, with the policy of the given environment."""
    subject = OAuthStore(tmp_path / "oauth.sqlite3", KEY)
    policy = registry.client_policy(ENV | env)
    return (
        provider_module.NextcloudOAuthProvider(
            nextcloud=exapp_target(ENV | env),
            env=ENV | env,
            policy=policy,
            store_provider=opener(subject),
            resolver=resolving(CIMD_IP),
        ),
        subject,
    )


def cimd_document(**overrides: object) -> dict[str, object]:
    """The measured document with these properties replaced, as a fetch would return it."""
    return CIMD_DOCUMENT | overrides


def cimd_route(
    document: dict[str, object] | None = None,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> respx.Route:
    """The transport of one document fetch, answered at the pinned address."""
    return respx.get(CIMD_FETCH_URL).mock(
        return_value=httpx.Response(
            status, json=CIMD_DOCUMENT if document is None else document, headers=headers
        )
    )


def registration(
    client_id: str = CLIENT_ID,
    *,
    redirect_uris: list[str] | None = None,
    secret: str | None = None,
) -> OAuthClientInformationFull:
    """What the SDK hands the provider after it validated and minted a registration."""
    return OAuthClientInformationFull.model_validate(
        {
            "client_id": client_id,
            "client_secret": secret,
            "client_name": "Claude",
            "redirect_uris": redirect_uris or [REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none" if secret is None else "client_secret_post",
            "scope": metadata.TOOL_SCOPE,
        }
    )


# --- register_client ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_registration_is_stored_while_dynamic_registration_is_on(tmp_path: Path) -> None:
    subject, store = build(tmp_path)

    await subject.register_client(registration())

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert row.allowed is True
    assert json.loads(row.metadata_json)["client_name"] == "Claude"


@pytest.mark.anyio
async def test_a_registration_is_refused_with_its_reason_while_the_switch_is_off(
    tmp_path: Path,
) -> None:
    """D-40: with the switch off the registration fails with a message that names why."""
    subject, store = build(tmp_path, **{registry.ENV_DCR: "off"})

    with pytest.raises(RegistrationError) as raised:
        await subject.register_client(registration())

    assert raised.value.error == "invalid_client_metadata"
    assert "registration" in (raised.value.error_description or "").lower()
    assert await store.load_client(CLIENT_ID) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uri",
    ["http://claude.ai/callback", "http://192.168.1.10/cb", "myapp://cb", "https://a@b.example/cb"],
)
async def test_a_redirect_address_that_is_not_https_or_loopback_is_dropped(
    tmp_path: Path, uri: str
) -> None:
    """T-03-41 and BL-04: the address is refused, the registration around it is not.

    The rule of D-35 is unchanged, only its blast radius is: an entry this server would
    never redirect to is dropped, and a client that sent one allowed address next to it is
    registered with that one address.
    """
    subject, store = build(tmp_path)

    await subject.register_client(registration(redirect_uris=[REDIRECT, uri]))

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert json.loads(row.metadata_json)["redirect_uris"] == [REDIRECT]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uri",
    ["http://claude.ai/callback", "http://192.168.1.10/cb", "myapp://cb", "https://a@b.example/cb"],
)
async def test_a_registration_of_nothing_but_forbidden_addresses_is_still_refused(
    tmp_path: Path, uri: str
) -> None:
    """The other half of BL-04: dropping every entry leaves no client, so it is a refusal.

    A registration with an empty ``redirect_uris`` would be a client that can never be sent
    anywhere, and the SDK would hand it the single registered address it does not have.
    """
    subject, store = build(tmp_path)

    with pytest.raises(RegistrationError) as raised:
        await subject.register_client(registration(redirect_uris=[uri]))

    assert raised.value.error == "invalid_redirect_uri"
    assert await store.load_client(CLIENT_ID) is None


@pytest.mark.anyio
async def test_the_three_addresses_of_cursor_register_as_the_two_that_are_allowed(
    tmp_path: Path,
) -> None:
    """BL-04, measured against staging on 2026-08-16 (03-09-MEASUREMENTS.md, run 4).

    Cursor sends a private-use scheme next to two registrable addresses and used to be
    refused as a whole, error message and all. The answer names what was registered and not
    what was sent, which RFC 7591 section 3.2.1 asks for and which is the only way the
    client can pick a target it will get through ``/authorize`` with.
    """
    subject, store = build(tmp_path)
    info = registration(redirect_uris=CURSOR_URIS)

    await subject.register_client(info)

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert json.loads(row.metadata_json)["redirect_uris"] == CURSOR_REGISTRABLE
    assert [str(uri) for uri in info.redirect_uris or []] == CURSOR_REGISTRABLE


@pytest.mark.anyio
async def test_an_address_that_was_dropped_is_no_target_of_the_registration(
    tmp_path: Path,
) -> None:
    """Dropping is not quiet acceptance: the exact matching refuses the dropped entry.

    D-35 stands (private-use schemes belong to nobody exclusively), so the value Cursor
    would like best is the one value it cannot authorize with.
    """
    subject, _ = build(tmp_path)
    await subject.register_client(registration(redirect_uris=CURSOR_URIS))

    client = await subject.get_client(CLIENT_ID)

    assert client is not None
    with pytest.raises(InvalidRedirectUriError):
        client.validate_redirect_uri(AnyUrl(CURSOR_URIS[0]))
    assert str(client.validate_redirect_uri(AnyUrl(CURSOR_REGISTRABLE[0]))) == CURSOR_REGISTRABLE[0]


@pytest.mark.anyio
async def test_a_loopback_address_stays_registrable(tmp_path: Path) -> None:
    subject, store = build(tmp_path)

    await subject.register_client(registration(redirect_uris=["http://127.0.0.1:41234/cb"]))

    assert await store.load_client(CLIENT_ID) is not None


@pytest.mark.anyio
async def test_in_the_allowlist_mode_only_a_registered_address_can_carry_the_listing(
    tmp_path: Path,
) -> None:
    """A dropped entry must not let a client in: it is not a target of this registration."""
    subject, store = build(
        tmp_path,
        **{registry.ENV_ALLOWLIST_ONLY: "1", registry.ENV_ALLOWED_CLIENTS: CURSOR_URIS[0]},
    )

    await subject.register_client(registration(redirect_uris=CURSOR_URIS))

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert row.allowed is False


@pytest.mark.anyio
async def test_in_the_allowlist_mode_an_unlisted_client_is_stored_as_not_allowed(
    tmp_path: Path,
) -> None:
    subject, store = build(tmp_path, **{registry.ENV_ALLOWLIST_ONLY: "1"})

    await subject.register_client(registration())

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert row.allowed is False


@pytest.mark.anyio
async def test_in_the_allowlist_mode_a_listed_return_address_is_stored_as_allowed(
    tmp_path: Path,
) -> None:
    """The only spelling an administrator can write down before a client ever registers."""
    subject, store = build(
        tmp_path, **{registry.ENV_ALLOWLIST_ONLY: "1", registry.ENV_ALLOWED_CLIENTS: REDIRECT}
    )

    await subject.register_client(registration())

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert row.allowed is True


@pytest.mark.anyio
async def test_the_client_secret_is_stored_as_a_hash_and_never_as_itself(
    tmp_path: Path,
) -> None:
    """T-03-11: the same rule the tokens follow. A stolen file must not authenticate."""
    subject, store = build(tmp_path)

    await subject.register_client(registration(secret=SECRET))

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert row.client_secret_hash == token_hash(SECRET)
    assert SECRET not in row.metadata_json
    assert SECRET not in (tmp_path / "oauth.sqlite3").read_bytes().decode("latin-1")


# --- get_client, the enforcement point ---------------------------------------------------


@pytest.mark.anyio
async def test_a_registered_client_comes_back_as_the_sdk_model(tmp_path: Path) -> None:
    subject, _ = build(tmp_path)
    await subject.register_client(registration())

    client = await subject.get_client(CLIENT_ID)

    assert client is not None
    assert client.client_id == CLIENT_ID
    assert [str(uri) for uri in client.redirect_uris or []] == [REDIRECT]


@pytest.mark.anyio
async def test_unknown_blocked_unlisted_and_expired_are_one_answer(tmp_path: Path) -> None:
    """T-03-47: an answer that separates the four is an information service (pitfall 9)."""
    subject, store = build(tmp_path)
    await subject.register_client(registration("blocked-client"))
    await store.save_client(
        "blocked-client", metadata_json='{"client_id": "blocked-client"}', allowed=False
    )
    await store.save_client(
        "stale-client",
        metadata_json='{"client_id": "stale-client"}',
        now=int(time.time()) - UNUSED_CLIENT_TTL - 60,
    )
    listed, _unused = build(tmp_path, **{registry.ENV_ALLOWLIST_ONLY: "1"})
    await store.save_client("live-client", metadata_json='{"client_id": "live-client"}')

    assert await subject.get_client("never-registered") is None
    assert await subject.get_client("blocked-client") is None
    assert await subject.get_client("stale-client") is None
    assert await listed.get_client("live-client") is None


@pytest.mark.anyio
async def test_a_registration_nobody_used_is_removed_when_it_is_looked_up(
    tmp_path: Path,
) -> None:
    """T-03-44: the registry is swept where it is read, because this project has no cron."""
    subject, store = build(tmp_path)
    await store.save_client(
        CLIENT_ID,
        metadata_json='{"client_id": "x"}',
        now=int(time.time()) - UNUSED_CLIENT_TTL - 60,
    )

    assert await subject.get_client(CLIENT_ID) is None
    assert await store.load_client(CLIENT_ID) is None


@pytest.mark.anyio
async def test_a_client_that_was_used_and_then_forgotten_expires_later(tmp_path: Path) -> None:
    """A used registration lives on the longer window and takes its rows with it."""
    subject, store = build(tmp_path)
    moment = int(time.time())
    await store.save_client(CLIENT_ID, metadata_json='{"client_id": "x"}', now=moment - 10)
    await store.touch_client(CLIENT_ID, now=moment - IDLE_CLIENT_TTL - 60)

    assert await subject.get_client(CLIENT_ID) is None
    assert await store.load_client(CLIENT_ID) is None


@pytest.mark.anyio
async def test_a_stored_row_that_cannot_be_read_is_refused_and_not_raised(
    tmp_path: Path,
) -> None:
    """Fail closed (D-37): a row this code cannot parse is not a client, and not a 500."""
    subject, store = build(tmp_path)
    await store.save_client(CLIENT_ID, metadata_json="not json at all")

    assert await subject.get_client(CLIENT_ID) is None


# --- AUTH-08: the client that shows a document instead of registering --------------------

CIMD_AUTH_ID = "the-connection-of-a-client-that-showed-a-document"
CIMD_NC_USER = "jane"
CIMD_APP_PASSWORD = "fffff-ggggg-hhhhh-iiiii-jjjjj"

STALE_METADATA = json.dumps(
    {
        "client_id": CIMD_ID,
        "client_name": "The name of an earlier reading",
        "redirect_uris": ["http://127.0.0.1/callback"],
        # What ``_resolve_cimd`` writes for every row of this path: a document client is
        # public by definition, and the authenticator of ``/token`` reads this field.
        "token_endpoint_auth_method": "none",
    }
)


async def with_a_document_row(
    store: OAuthStore, *, fetched_at: int, expires_at: int, registered_at: int | None = None
) -> None:
    """A row of the document path, placed in time by hand: the freshness is a deadline."""
    await store.save_client(
        CIMD_ID,
        metadata_json=STALE_METADATA,
        now=registered_at if registered_at is not None else fetched_at,
        cimd_fetched_at=fetched_at,
        cimd_expires_at=expires_at,
    )


@pytest.mark.anyio
async def test_a_client_that_shows_a_document_is_resolved_and_gets_a_row_of_its_own(
    tmp_path: Path,
) -> None:
    """The whole of AUTH-08 in one run: the identifier is the address of the document.

    The row is not a convenience. ``flows.client_id`` and ``authorizations.client_id``
    reference ``clients(client_id)``, so a client that lived only in a cache would fail the
    first authorization request with an integrity error (pitfall 3).
    """
    subject, store = build(tmp_path)

    with respx.mock:
        route = cimd_route()
        client = await subject.get_client(CIMD_ID)

    assert route.call_count == 1
    assert client is not None
    assert client.client_id == CIMD_ID
    assert client.client_name == "Claude Code"
    assert [str(uri) for uri in client.redirect_uris or []] == CIMD_URIS
    assert client.scope == metadata.REGISTERED_SCOPE

    row = await store.load_client(CIMD_ID)
    assert row is not None
    assert row.client_secret_hash is None, "a client of this path is public by definition"
    assert row.allowed is True
    assert row.cimd_fetched_at is not None
    assert row.cimd_expires_at is not None
    assert row.cimd_expires_at > row.cimd_fetched_at


@pytest.mark.anyio
async def test_the_row_of_a_document_client_carries_the_foreign_key_of_a_flow(
    tmp_path: Path,
) -> None:
    """Pitfall 3, spelled out as the insert that used to fail: the first flow of the client."""
    subject, store = build(tmp_path)

    with respx.mock:
        cimd_route()
        assert await subject.get_client(CIMD_ID) is not None

    await store.create_flow(
        "the-first-flow-of-a-document-client",
        client_id=CIMD_ID,
        redirect_uri=CIMD_URIS[0],
        redirect_uri_explicit=True,
        code_challenge=CHALLENGE,
        state=None,
        scopes=metadata.TOOL_SCOPE,
        resource=f"{PUBLIC_URL}/mcp",
        poll_token="the-poll-token-of-this-sign-in",
    )

    flow = await store.load_flow("the-first-flow-of-a-document-client")
    assert flow is not None
    assert flow.client_id == CIMD_ID


@pytest.mark.anyio
async def test_a_url_client_id_is_refused_while_the_cimd_switch_is_off(tmp_path: Path) -> None:
    """T-06-28: a switched off feature that still makes outbound requests is an SSRF tool.

    The switch is asked before the form of the identifier and before any resolution, so the
    proof is not "the answer was none" but "this target was never contacted".
    """
    subject, store = build(tmp_path, **{registry.ENV_CIMD: "off"})

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        client = await subject.get_client(CIMD_ID)

    assert client is None
    assert route.called is False
    assert await store.load_client(CIMD_ID) is None


@pytest.mark.anyio
async def test_a_url_client_id_is_refused_while_dcr_is_off(tmp_path: Path) -> None:
    """The locked decision of this phase: a disabled DCR must not be bypassable through CIMD.

    It holds without a second reading of a second switch here, because ``cimd_enabled`` is
    derived fail closed from both in ``registry`` (T-06-26). The switch of this path may even
    be set to ``on`` at the same time, which is the case this test names.
    """
    subject, store = build(tmp_path, **{registry.ENV_DCR: "off", registry.ENV_CIMD: "on"})

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        client = await subject.get_client(CIMD_ID)

    assert client is None
    assert route.called is False
    assert await store.load_client(CIMD_ID) is None


@pytest.mark.anyio
async def test_the_allowlist_mode_refuses_an_unlisted_document_client_before_any_packet(
    tmp_path: Path,
) -> None:
    """WR-02: in the hardest configuration no packet leaves on a stranger's word.

    The identifier of this path is a published URL an administrator can list in advance
    (which is where the allowlist finally works the way one expects, against the random
    UUID of a registration). The other side of that coin: an unlisted identifier used to
    be fetched first and refused after, which made ``/authorize`` an unauthenticated
    request reflector against any public https target. The refusal now costs no packet and
    writes no row.
    """
    subject, store = build(tmp_path, **{registry.ENV_ALLOWLIST_ONLY: "on"})

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        assert await subject.get_client(CIMD_ID) is None

    assert route.called is False, "the allowlist decides before the fetch, not after"
    assert await store.load_client(CIMD_ID) is None


@pytest.mark.anyio
async def test_the_allowlist_mode_refuses_a_stale_unlisted_row_without_a_packet(
    tmp_path: Path,
) -> None:
    """WR-02 with a row that already exists: a listing that went away ends the refetch too.

    The freshness deadline passed and the client is on no list, so the read that would
    normally follow never leaves the machine, and the shared rest of ``get_client`` keeps
    refusing the stored row either way (T-06-27).
    """
    subject, store = build(tmp_path, **{registry.ENV_ALLOWLIST_ONLY: "on"})
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        assert await subject.get_client(CIMD_ID) is None

    assert route.called is False
    assert await store.load_client(CIMD_ID) is not None, "the refusal deletes nothing"


@pytest.mark.anyio
async def test_a_listed_document_client_comes_through_the_allowlist(tmp_path: Path) -> None:
    subject, _ = build(
        tmp_path,
        **{registry.ENV_ALLOWLIST_ONLY: "on", registry.ENV_ALLOWED_CLIENTS: CIMD_ID},
    )

    with respx.mock:
        cimd_route()
        client = await subject.get_client(CIMD_ID)

    assert client is not None
    assert client.client_name == "Claude Code"


@pytest.mark.anyio
async def test_a_forbidden_return_address_of_a_document_is_dropped_and_the_rest_registered(
    tmp_path: Path,
) -> None:
    """D-35 through the same function as a registration, with the same partial acceptance."""
    subject, store = build(tmp_path)

    with respx.mock:
        cimd_route(cimd_document(redirect_uris=CURSOR_URIS))
        client = await subject.get_client(CIMD_ID)

    assert client is not None
    assert [str(uri) for uri in client.redirect_uris or []] == CURSOR_REGISTRABLE
    row = await store.load_client(CIMD_ID)
    assert row is not None
    assert json.loads(row.metadata_json)["redirect_uris"] == CURSOR_REGISTRABLE


@pytest.mark.anyio
async def test_a_document_of_nothing_but_forbidden_addresses_writes_no_row(
    tmp_path: Path,
) -> None:
    """T-06-29: a client with no admissible return target is one this server never sends to."""
    subject, store = build(tmp_path)

    with respx.mock:
        cimd_route(cimd_document(redirect_uris=[CURSOR_URIS[0]]))
        assert await subject.get_client(CIMD_ID) is None

    assert await store.load_client(CIMD_ID) is None


@pytest.mark.anyio
async def test_a_document_that_carries_a_secret_still_becomes_a_public_client(
    tmp_path: Path,
) -> None:
    """T-06-30: there is no channel over which a secret of this client could be agreed.

    ``validate_document`` refuses every authentication method built on a shared secret
    already; this is the other half, the one that holds if a document names an admissible
    method and puts a secret next to it anyway.
    """
    subject, store = build(tmp_path)

    with respx.mock:
        cimd_route(cimd_document(client_secret="a-secret-nobody-ever-handed-out"))
        assert await subject.get_client(CIMD_ID) is not None

    row = await store.load_client(CIMD_ID)
    assert row is not None
    assert row.client_secret_hash is None
    assert '"client_secret":' not in row.metadata_json
    assert "a-secret-nobody-ever-handed-out" not in row.metadata_json
    assert json.loads(row.metadata_json)["token_endpoint_auth_method"] == "none"


@pytest.mark.anyio
async def test_a_row_that_is_still_fresh_answers_without_a_second_request(
    tmp_path: Path,
) -> None:
    """The whole cache: a deadline in the future is one this server does not pay for again."""
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 10, expires_at=moment + 200)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        client = await subject.get_client(CIMD_ID)

    assert route.called is False
    assert client is not None
    assert client.client_name == "The name of an earlier reading"


@pytest.mark.anyio
async def test_a_row_whose_freshness_ran_out_is_read_again(tmp_path: Path) -> None:
    """T-06-32: the deadline of the freshness costs a fetch, and the fetch is what happens."""
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)

    with respx.mock:
        route = cimd_route()
        client = await subject.get_client(CIMD_ID)

    assert route.call_count == 1
    assert client is not None
    assert client.client_name == "Claude Code", "the new reading is what answers"
    row = await store.load_client(CIMD_ID)
    assert row is not None
    assert row.cimd_expires_at is not None
    assert row.cimd_expires_at > moment


@pytest.mark.anyio
async def test_a_reading_that_fails_is_a_refusal_and_not_a_walk_on_with_the_old_one(
    tmp_path: Path,
) -> None:
    """T-06-32, the other half: fail closed, and the row is not destroyed by a bad answer."""
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)

    with respx.mock:
        route = cimd_route(status=500)
        assert await subject.get_client(CIMD_ID) is None

    assert route.call_count == 1
    assert await store.load_client(CIMD_ID) is not None, "a refusal deletes nothing"


# --- WR-01/WR-03: no packet on the hot paths ----------------------------------------------


@pytest.mark.anyio
async def test_a_stale_row_keeps_answering_where_fetching_is_forbidden(tmp_path: Path) -> None:
    """WR-01: the hot paths read the stored identity and never pay a stranger's fetch.

    The row is past its freshness deadline, which is exactly the moment the old code made
    an outbound request in the middle of a tool call. With ``may_fetch=False`` the stored
    identity answers unchanged, nothing is written, and the deadline stays where it was:
    the next ``/authorize`` pays the refetch.
    """
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        client = await subject.get_client(CIMD_ID, may_fetch=False)

    assert route.called is False
    assert client is not None
    assert client.client_name == "The name of an earlier reading"
    row = await store.load_client(CIMD_ID)
    assert row is not None
    assert row.cimd_expires_at == moment - 1, "and no store write on the hot path either"


@pytest.mark.anyio
async def test_an_unknown_document_client_is_a_plain_refusal_where_fetching_is_forbidden(
    tmp_path: Path,
) -> None:
    """WR-01, the negative half: an identity that was never read cannot be reused.

    It can only be fetched, and fetching is exactly what is forbidden on the hot paths, so
    the answer is the one every unknown client gets, and no packet leaves.
    """
    subject, store = build(tmp_path)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        assert await subject.get_client(CIMD_ID, may_fetch=False) is None

    assert route.called is False
    assert await store.load_client(CIMD_ID) is None


@pytest.mark.anyio
async def test_a_blocked_document_client_stays_blocked_where_fetching_is_forbidden(
    tmp_path: Path,
) -> None:
    """WR-01 weakens no policy: the shared rest of ``get_client`` still refuses a block.

    ``may_fetch=False`` skips the fetch, never the questions: a stored block reaches the
    verifier and the token endpoints exactly as before (pitfall 9, T-03-55).
    """
    subject, store = build(tmp_path)
    moment = int(time.time())
    await store.save_client(
        CIMD_ID,
        metadata_json=STALE_METADATA,
        allowed=False,
        now=moment - 4_000,
        cimd_fetched_at=moment - 4_000,
        cimd_expires_at=moment - 1,
    )

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        assert await subject.get_client(CIMD_ID, may_fetch=False) is None

    assert route.called is False


@pytest.mark.anyio
async def test_the_dcr_switch_reaches_the_hot_paths_as_well(tmp_path: Path) -> None:
    """The locked decision holds under ``may_fetch=False`` too (T-06-26).

    A stored row of a path an administrator closed answers nobody, packet or no packet:
    the switch is still the first question of ``_resolve_cimd``, before the reuse branch.
    """
    subject, store = build(tmp_path, **{registry.ENV_DCR: "off"})
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 10, expires_at=moment + 200)

    assert await subject.get_client(CIMD_ID, may_fetch=False) is None


@pytest.mark.anyio
async def test_a_running_session_survives_a_document_host_outage(tmp_path: Path) -> None:
    """WR-01, the verifier's own sentence held against a foreign host.

    The token is valid, Nextcloud is untouched, and the document host is down at the
    freshness deadline. The old code refetched on the cache miss, got nothing and refused
    a running session mid conversation; the fix reads the stored row and the session lives.
    """
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)
    await store.create_authorization(
        CIMD_AUTH_ID,
        client_id=CIMD_ID,
        nc_user=CIMD_NC_USER,
        nc_account_id=CIMD_NC_USER,
        app_password=CIMD_APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )
    bearer = "the-access-token-of-a-running-cimd-session"
    await store.create_access_token(
        bearer,
        auth_id=CIMD_AUTH_ID,
        family_id="the-family-of-this-session",
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
        now=moment,
    )
    checker = StoreTokenVerifier(
        store_provider=opener(store), get_client=subject.get_client, env=ENV
    )

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        access = await checker.verify_token(bearer)

    assert route.called is False
    assert access is not None
    assert access.client_id == CIMD_ID


@pytest.mark.anyio
async def test_a_rotation_at_the_freshness_deadline_waits_on_no_document_host(
    tmp_path: Path,
) -> None:
    """WR-03: the token endpoint's promise, held against the host a client id names.

    "Nothing here talks to Nextcloud" has to mean "nothing here talks to anybody", or a
    slow document host delays every rotation of its client by up to five seconds and a
    down one fails an otherwise valid rotation at the freshness deadline.
    """
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)
    await store.create_authorization(
        CIMD_AUTH_ID,
        client_id=CIMD_ID,
        nc_user=CIMD_NC_USER,
        nc_account_id=CIMD_NC_USER,
        app_password=CIMD_APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )
    refresh = "the-refresh-token-of-a-cimd-connection"
    await store.create_refresh_token(
        refresh, auth_id=CIMD_AUTH_ID, family_id="the-family-of-this-connection", now=moment
    )
    loaded = await subject.load_refresh_token(registration(CIMD_ID), refresh)
    assert loaded is not None

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        answer = await subject.exchange_refresh_token(registration(CIMD_ID), loaded, [])

    assert route.called is False
    assert answer.access_token
    assert answer.refresh_token is not None
    assert answer.refresh_token != refresh, "the rotation itself is untouched"


@pytest.mark.anyio
async def test_the_token_endpoint_answers_a_document_client_from_its_stored_row(
    tmp_path: Path,
) -> None:
    """WR-01 and WR-03 end to end: client authentication and code exchange, no packet.

    The row is stale and the document host answers nobody, and the whole ``/token`` walk
    completes anyway: the authenticator and the exchange both read the stored row.
    """
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(store, fetched_at=moment - 4_000, expires_at=moment - 1)
    await store.create_authorization(
        CIMD_AUTH_ID,
        client_id=CIMD_ID,
        nc_user=CIMD_NC_USER,
        nc_account_id=CIMD_NC_USER,
        app_password=CIMD_APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )
    await store.create_auth_code(
        CODE,
        auth_id=CIMD_AUTH_ID,
        redirect_uri="http://127.0.0.1/callback",
        code_challenge=CHALLENGE,
        resource=RESOURCE,
    )

    with serving(subject) as http, respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        response = http.post(
            "/token",
            data=token_request(client_id=CIMD_ID, redirect_uri="http://127.0.0.1/callback"),
        )

    assert response.status_code == 200, response.text
    assert route.called is False
    assert response.json()["access_token"]


@pytest.mark.anyio
async def test_an_unknown_document_client_at_the_token_endpoint_is_a_401_without_a_packet(
    tmp_path: Path,
) -> None:
    """The fail closed half of the same fix: no row means 401, and still no packet.

    Before the fix ``/token`` was a second unauthenticated trigger for the outbound fetch;
    now the fetch belongs to ``/authorize`` alone.
    """
    subject, _store = build(tmp_path)

    with serving(subject) as http, respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        response = http.post(
            "/token",
            data=token_request(client_id=CIMD_ID, redirect_uri="http://127.0.0.1/callback"),
        )

    assert response.status_code == 401
    assert route.called is False


@pytest.mark.anyio
async def test_a_document_identity_keeps_its_row_and_its_connections_past_the_ttl(
    tmp_path: Path,
) -> None:
    """Pitfall 4, T-06-31: the registration TTL must not end a connection nobody ended.

    The row is older than the window that removes a registration nobody ever used, and it
    carries a connection with an encrypted Nextcloud app password. Under the registration TTL
    the lookup would hand that password back and delete the row, and through the cascade the
    connection with it: a user disconnected by a deadline that describes something else.
    """
    subject, store = build(tmp_path)
    moment = int(time.time())
    await with_a_document_row(
        store,
        fetched_at=moment - 10,
        expires_at=moment + 200,
        registered_at=moment - UNUSED_CLIENT_TTL - 1,
    )
    await store.create_authorization(
        CIMD_AUTH_ID,
        client_id=CIMD_ID,
        nc_user=CIMD_NC_USER,
        nc_account_id=CIMD_NC_USER,
        app_password=CIMD_APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=f"{PUBLIC_URL}/mcp",
    )

    with respx.mock(assert_all_called=False) as mock:
        mock.get(CIMD_FETCH_URL)
        client = await subject.get_client(CIMD_ID)

    assert client is not None
    assert await store.load_client(CIMD_ID) is not None
    assert await store.load_authorization(CIMD_AUTH_ID) is not None


@pytest.mark.anyio
async def test_the_sweep_of_expired_clients_leaves_a_document_identity_alone(
    tmp_path: Path,
) -> None:
    """The second place a client row is deleted, and it has to make the same exception."""
    subject, store = build(tmp_path)
    long_ago = int(time.time()) - UNUSED_CLIENT_TTL - 1
    await with_a_document_row(store, fetched_at=long_ago, expires_at=long_ago + 300)
    await store.save_client("a-registration-that-ran-out", metadata_json="{}", now=long_ago)

    swept = await subject.sweep_expired_clients()

    assert swept == 1
    assert await store.load_client("a-registration-that-ran-out") is None
    assert await store.load_client(CIMD_ID) is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "body"),
    [
        (500, CIMD_DOCUMENT),
        (404, CIMD_DOCUMENT),
        (302, CIMD_DOCUMENT),
        (200, {"client_id": CIMD_ID}),
        (200, cimd_document(client_id="https://claude.ai/oauth/another-document")),
        (200, cimd_document(token_endpoint_auth_method="client_secret_post")),
        (200, cimd_document(redirect_uris=[])),
        (200, cimd_document(redirect_uris=["cursor://anysphere.cursor-mcp/oauth/callback"])),
    ],
)
async def test_every_refusal_of_this_path_is_one_answer_and_never_an_exception(
    tmp_path: Path, status: int, body: dict[str, object]
) -> None:
    """T-06-33: unknown, unreachable, malformed and inadmissible look the same from outside."""
    subject, store = build(tmp_path)

    with respx.mock:
        cimd_route(body, status=status)
        assert await subject.get_client(CIMD_ID) is None

    assert await store.load_client(CIMD_ID) is None, "and none of them leaves a row behind"


@pytest.mark.anyio
async def test_an_identifier_that_is_not_a_document_url_never_reaches_the_transport(
    tmp_path: Path,
) -> None:
    """The form check is the first one that costs nothing, and an unknown client id is the
    ordinary case of this branch: almost every call of it is one."""
    subject, _ = build(tmp_path)

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        assert await subject.get_client("9d0f8f1a-not-a-url") is None
        assert await subject.get_client("http://claude.ai/oauth/document") is None
        assert await subject.get_client(f" {CIMD_ID}") is None

    assert route.called is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("header", "window"),
    [
        (None, cimd.CACHE_MIN_SECONDS),
        ("max-age=60", cimd.CACHE_MIN_SECONDS),
        ("max-age=900", 900),
        ("max-age=86400", cimd.CACHE_MAX_SECONDS),
        ("no-store", cimd.CACHE_MIN_SECONDS),
    ],
)
async def test_the_deadline_of_a_row_is_the_window_of_its_own_answer(
    tmp_path: Path, header: str | None, window: int
) -> None:
    """The draft asks a server to respect the cache headers and lets it bound them itself."""
    subject, store = build(tmp_path)

    with respx.mock:
        cimd_route(headers={"cache-control": header} if header else None)
        assert await subject.get_client(CIMD_ID) is not None

    row = await store.load_client(CIMD_ID)
    assert row is not None
    assert row.cimd_fetched_at is not None
    assert row.cimd_expires_at is not None
    assert row.cimd_expires_at - row.cimd_fetched_at == window


def test_the_client_lookup_raises_no_registration_error_on_either_of_its_paths() -> None:
    """D-37: an exception out of ``get_client`` would be a new failure shape in four endpoints.

    ``register_client`` names its refusals with a ``RegistrationError``, because a developer
    reads that answer at ``/register``. The lookup answers ``None`` instead, and the branch of
    this plan does not get to be the exception.

    The docstrings come off first, the way the throttle gate of this file does it: they name
    what the code deliberately does not do, and a gate that cannot tell a mention from a use
    would forbid the explanation instead of the thing.
    """
    tree = ast.parse(inspect.getsource(provider_module))
    checked = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        if node.name not in ("get_client", "_resolve_cimd", "_cimd_client_information"):
            continue
        checked.add(node.name)
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        assert "RegistrationError" not in ast.unparse(node), (
            f"{node.name} refuses with a value, never with a registration error"
        )

    assert checked == {"get_client", "_resolve_cimd", "_cimd_client_information"}


# --- the code exchange -------------------------------------------------------------------

AUTH_ID = "the-flow-this-authorization-was-born-in"
NC_USER = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
CODE = "the-authorization-code-of-this-consent"
RESOURCE = f"{PUBLIC_URL}/mcp"
VERIFIER = "a-code-verifier-of-the-client-that-is-long-enough"
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


async def approved(
    tmp_path: Path,
    *,
    resource: str = RESOURCE,
    secret: str | None = None,
    **env: str,
) -> tuple[provider_module.NextcloudOAuthProvider, OAuthStore]:
    """A registered client, a consent that happened and the code it produced."""
    subject, store = build(tmp_path, **env)
    await subject.register_client(registration(secret=secret))
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=resource,
    )
    await store.create_auth_code(
        CODE,
        auth_id=AUTH_ID,
        redirect_uri=REDIRECT,
        code_challenge=CHALLENGE,
        resource=resource,
    )
    return subject, store


@pytest.mark.anyio
async def test_a_code_is_loaded_with_everything_the_token_endpoint_compares(
    tmp_path: Path,
) -> None:
    subject, _store = await approved(tmp_path)

    loaded = await subject.load_authorization_code(registration(), CODE)

    assert loaded is not None
    assert loaded.code == CODE
    assert loaded.client_id == CLIENT_ID
    assert loaded.subject == NC_USER, "the resource owner travels into the access token"
    assert loaded.code_challenge == CHALLENGE
    assert str(loaded.redirect_uri) == REDIRECT
    assert loaded.redirect_uri_provided_explicitly is True
    assert loaded.resource == RESOURCE
    assert loaded.scopes == [metadata.TOOL_SCOPE]
    assert 0 < loaded.expires_at - time.time() <= 60


@pytest.mark.anyio
async def test_a_code_that_is_unknown_used_or_expired_is_not_loaded(tmp_path: Path) -> None:
    subject, store = await approved(tmp_path)

    assert await subject.load_authorization_code(registration(), "never-issued") is None
    await store.redeem_auth_code(CODE)
    assert await subject.load_authorization_code(registration(), CODE) is None


@pytest.mark.anyio
async def test_the_exchange_issues_an_opaque_pair_and_stores_only_their_digests(
    tmp_path: Path,
) -> None:
    subject, store = await approved(tmp_path)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None

    issued = await subject.exchange_authorization_code(registration(), code)

    assert issued.token_type == "Bearer"
    assert issued.expires_in == ACCESS_TOKEN_TTL
    assert issued.refresh_token is not None
    assert issued.access_token != issued.refresh_token
    access = await store.load_access_token(issued.access_token)
    refresh = await store.load_refresh_token(issued.refresh_token)
    assert access is not None
    assert refresh is not None
    assert access.auth_id == AUTH_ID
    assert access.nc_user == NC_USER
    assert access.resource == RESOURCE
    assert access.family_id == refresh.family_id, "one connection, one family"
    file_bytes = (tmp_path / "oauth.sqlite3").read_bytes()
    assert issued.access_token.encode() not in file_bytes
    assert issued.refresh_token.encode() not in file_bytes


@pytest.mark.anyio
async def test_the_code_is_spent_and_a_second_exchange_fails(tmp_path: Path) -> None:
    """RFC 6749 §10.5: one code, one exchange, and the second one is invalid_grant."""
    subject, _store = await approved(tmp_path)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None

    await subject.exchange_authorization_code(registration(), code)
    with pytest.raises(TokenError) as raised:
        await subject.exchange_authorization_code(registration(), code)

    assert raised.value.error == "invalid_grant"


@pytest.mark.anyio
@pytest.mark.parametrize("resource", ["", "https://other.example.com/mcp"])
async def test_a_code_without_this_audience_never_becomes_a_token(
    tmp_path: Path, resource: str
) -> None:
    """T-03-51: a token without an audience is valid at every other MCP server."""
    subject, store = await approved(tmp_path, resource=resource)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None

    with pytest.raises(TokenError) as raised:
        await subject.exchange_authorization_code(registration(), code)

    assert raised.value.error == "invalid_target"
    assert await store.load_auth_code(CODE) is not None, "a refusal does not spend the code"


@pytest.mark.anyio
async def test_a_client_blocked_between_authorize_and_token_gets_nothing(
    tmp_path: Path,
) -> None:
    """T-03-55, pitfall 9: a block in the middle of a flow must not slip through."""
    subject, store = await approved(tmp_path)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None
    await store.save_client(CLIENT_ID, metadata_json='{"client_id": "x"}', allowed=False)

    with pytest.raises(TokenError) as raised:
        await subject.exchange_authorization_code(registration(), code)

    assert raised.value.error == "invalid_client"


@pytest.mark.anyio
async def test_the_exchange_asks_nextcloud_nothing_at_all(tmp_path: Path) -> None:
    """T-03-58, pitfall 13: the token endpoint of a connector has ten seconds."""
    subject, _store = await approved(tmp_path)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None

    with respx.mock:
        await subject.exchange_authorization_code(registration(), code)
        assert len(respx.calls) == 0


@pytest.mark.anyio
async def test_the_exchange_marks_the_registration_as_used(tmp_path: Path) -> None:
    """A registration that produced a token lives on the long window, not the short one."""
    subject, store = await approved(tmp_path)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None

    await subject.exchange_authorization_code(registration(), code)

    row = await store.load_client(CLIENT_ID)
    assert row is not None
    assert row.last_used_at is not None


# --- the client authenticator of this server ----------------------------------------------


def token_request(**fields: str) -> dict[str, str]:
    payload = {
        "grant_type": "authorization_code",
        "code": CODE,
        "code_verifier": VERIFIER,
        "redirect_uri": REDIRECT,
        "client_id": CLIENT_ID,
    }
    payload.update(fields)
    return payload


def serving(
    subject: provider_module.NextcloudOAuthProvider,
    *,
    throttle: throttle_module.Throttle | None = None,
    **env: str,
) -> TestClient:
    return TestClient(
        Starlette(
            routes=provider_module.auth_routes(ENV | env, provider=subject, throttle=throttle)
        )
    )


@pytest.mark.anyio
async def test_a_public_client_walks_the_whole_token_endpoint(tmp_path: Path) -> None:
    """The end to end shape: a real code, a real PKCE verifier, a real pair of tokens."""
    subject, _store = await approved(tmp_path)

    with serving(subject) as http:
        response = http.post("/token", data=token_request())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == ACCESS_TOKEN_TTL
    assert body["refresh_token"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_a_confidential_client_authenticates_against_the_stored_digest(
    tmp_path: Path,
) -> None:
    """The SDK compares a plaintext secret, and this store keeps none (plan 03-05)."""
    subject, _store = await approved(tmp_path, secret=SECRET)

    with serving(subject) as http:
        good = http.post("/token", data=token_request(client_secret=SECRET))

    assert good.status_code == 200, good.text


@pytest.mark.anyio
async def test_a_wrong_client_secret_is_a_401_and_no_token(tmp_path: Path) -> None:
    subject, store = await approved(tmp_path, secret=SECRET)

    with serving(subject) as http:
        response = http.post("/token", data=token_request(client_secret="not-the-secret"))

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"
    assert await store.load_auth_code(CODE) is not None, "the code was not spent"


@pytest.mark.anyio
async def test_a_confidential_client_without_its_secret_is_refused(tmp_path: Path) -> None:
    subject, _store = await approved(tmp_path, secret=SECRET)

    with serving(subject) as http:
        response = http.post("/token", data=token_request())

    assert response.status_code == 401


@pytest.mark.anyio
async def test_a_row_that_asks_for_a_secret_and_has_none_is_refused(tmp_path: Path) -> None:
    """WR-01: the SDK authenticator refuses "registered for a secret and has none stored",
    and this override read the same state as "a public client, let it in". Any row written
    another way than through the shipped registration path would then have authenticated
    with no credential at all."""
    subject, store = await approved(tmp_path, secret=SECRET)
    row = await store.load_client(CLIENT_ID)
    assert row is not None
    await store.save_client(
        CLIENT_ID,
        metadata_json=row.metadata_json,
        allowed=True,
        secret_hash=None,
    )

    with serving(subject) as http:
        without = http.post("/token", data=token_request())
        with_one = http.post("/token", data=token_request(client_secret=SECRET))

    assert without.status_code == 401
    assert with_one.status_code == 401
    assert without.json()["error"] == "invalid_client"
    assert await store.load_auth_code(CODE) is not None, "the code was not spent"


@pytest.mark.anyio
async def test_a_client_secret_that_ran_out_stops_working(tmp_path: Path) -> None:
    """WR-01: nothing compared client_secret_expires_at against a clock, so an expired
    secret kept working. Not reachable with the shipped default (never), which is why it is
    a warning, and live the moment an administrator sets an expiry."""
    subject, store = await approved(tmp_path, secret=SECRET)
    registered = registration(secret=SECRET)
    registered.client_secret_expires_at = int(time.time()) - 1
    row = await store.load_client(CLIENT_ID)
    assert row is not None
    await store.save_client(
        CLIENT_ID,
        metadata_json=registered.model_dump_json(),
        allowed=True,
        secret_hash=row.client_secret_hash,
    )

    with serving(subject) as http:
        response = http.post("/token", data=token_request(client_secret=SECRET))

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


# --- the token end of the loopback port rule (RFC 8252 7.3, T-06-20) ---------------------
#
# The relaxation lives in ``oauth/consent.py``: a native client publishes a portless loopback
# address and arrives with whatever port the operating system gave it, so the exact
# comparison of the SDK is asked a second question there and the REQUESTED address, with its
# port, is what travels into the authorization code. The claim behind that decision is that
# the token endpoint then needs no second relaxation, because the SDK compares the token
# request against the stored value of the code and not against the registration. The consent
# tests hold the first half; these two hold the second, so a change to that comparison in a
# future SDK release lands on a red check instead of on a client that signs in and then
# cannot exchange its code.


#: What Claude Code publishes and what it arrives with: the document names no port and the
#: client listens on whatever port the operating system gave it (06-RESEARCH.md, pattern 4).
LOOPBACK_REGISTERED = CIMD_URIS[0]
LOOPBACK_APPROVED = "http://localhost:3118/callback"
LOOPBACK_ANOTHER_PORT = "http://localhost:4242/callback"


async def approved_on_a_relaxed_port(
    tmp_path: Path,
) -> tuple[provider_module.NextcloudOAuthProvider, OAuthStore]:
    """A portless registration and a code that carries the port the consent approved.

    The one case where the two addresses differ, and the reason it exists in the store at
    all: ``oauth/consent.py`` writes the REQUESTED address into the flow and therefore into
    the code, so the port lives in the code and never in the registration (T-06-19).
    """
    subject, store = build(tmp_path)
    await subject.register_client(registration(redirect_uris=[LOOPBACK_REGISTERED]))
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )
    await store.create_auth_code(
        CODE,
        auth_id=AUTH_ID,
        redirect_uri=LOOPBACK_APPROVED,
        code_challenge=CHALLENGE,
        resource=RESOURCE,
    )
    return subject, store


@pytest.mark.anyio
async def test_a_relaxed_loopback_port_walks_the_token_endpoint_unchanged(
    tmp_path: Path,
) -> None:
    """The registration is portless, the code carries the port, and the exchange goes through."""
    subject, _store = await approved_on_a_relaxed_port(tmp_path)

    with serving(subject) as http:
        response = http.post("/token", data=token_request(redirect_uri=LOOPBACK_APPROVED))

    assert response.status_code == 200, response.text
    assert response.json()["refresh_token"]


@pytest.mark.anyio
async def test_another_port_at_the_token_endpoint_is_not_the_approved_one(tmp_path: Path) -> None:
    """T-06-20: the relaxation is one place and the token endpoint is not a second one.

    A client that comes back on the port it was given is admitted; a request that names any
    other port is a request about another address than the one a person approved, and the
    code stays unspent.
    """
    subject, store = await approved_on_a_relaxed_port(tmp_path)

    with serving(subject) as http:
        response = http.post("/token", data=token_request(redirect_uri=LOOPBACK_ANOTHER_PORT))

    assert response.status_code == 400
    # The SDK answers a redirect URI that is not the one of the code with ``invalid_request``
    # (``mcp/server/auth/handlers/token.py``), not with ``invalid_grant``. The spelling is
    # measured here rather than assumed, because it is the SDK's answer and not ours.
    assert response.json()["error"] == "invalid_request"
    assert await store.load_auth_code(CODE) is not None, "the code was not spent"


@pytest.mark.anyio
async def test_the_portless_registration_is_not_the_address_the_code_carries(
    tmp_path: Path,
) -> None:
    """And the registration itself is no longer an admissible answer at this endpoint.

    Not a detail: it is what proves the comparison runs against the code. If the SDK ever
    compared against the registration instead, this request would pass and the one above
    would fail, which is exactly the drift these three checks exist to catch.
    """
    subject, _store = await approved_on_a_relaxed_port(tmp_path)

    with serving(subject) as http:
        response = http.post("/token", data=token_request(redirect_uri=LOOPBACK_REGISTERED))

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


@pytest.mark.anyio
async def test_a_wrong_pkce_verifier_is_refused_by_the_sdk(tmp_path: Path) -> None:
    """The checks the SDK owns stay the SDK's, and this proves they are still in the path."""
    subject, _store = await approved(tmp_path)

    with serving(subject) as http:
        response = http.post("/token", data=token_request(code_verifier="another-verifier"))

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


# --- what an empty store answers, and the one grant that refuses for good -----------------


@pytest.mark.anyio
async def test_every_token_path_refuses_what_this_server_never_issued(tmp_path: Path) -> None:
    """Fail closed: a value nothing in the store knows is never a grant and never a 500."""
    subject, _ = build(tmp_path)
    client = registration()

    assert await subject.load_authorization_code(client, "any-code") is None
    assert await subject.load_refresh_token(client, "any-token") is None
    assert await subject.load_access_token("any-token") is None
    assert await subject.revoke_token(_access_token()) is None

    with pytest.raises(TokenError):
        await subject.exchange_authorization_code(client, _authorization_code())
    with pytest.raises(TokenError):
        await subject.exchange_refresh_token(client, _refresh_token(), [])
    with pytest.raises(TokenError) as raised:
        await subject.exchange_identity_assertion(client, _identity_assertion())

    assert raised.value.error == "unsupported_grant_type", "and this one refuses for good"


# --- the routes --------------------------------------------------------------------------


def routes(**env: str) -> list[str]:
    policy = registry.client_policy(ENV | env)

    async def never_opened() -> OAuthStore:
        raise AssertionError("building the routes opens no store")

    subject = provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(ENV | env),
        env=ENV | env,
        policy=policy,
        store_provider=never_opened,
    )
    return [route.path for route in provider_module.auth_routes(ENV | env, provider=subject)]


def test_the_authorization_server_routes_are_the_three_the_sdk_serves() -> None:
    """``/authorize`` is the fourth endpoint and is served by ``oauth/consent.py``: a
    refused authorization request has to end on a page a person can read, not in the JSON
    the SDK answers a machine with (plan 03-05, task 3)."""
    assert sorted(routes()) == ["/register", "/revoke", "/token"]


def test_the_application_serves_the_four_endpoints_exactly_once_each() -> None:
    """Set equality over the deployed application, which is where the two factories meet."""
    paths = [getattr(route, "path", "") for route in _exapp_routes()]

    for path in AS_PATHS:
        assert paths.count(path) == 1, path


def test_without_dynamic_registration_the_register_route_does_not_exist() -> None:
    """D-40: the switch removes the endpoint, it does not leave one that always refuses."""
    assert "/register" not in routes(**{registry.ENV_DCR: "off"})


def test_the_authorization_server_document_follows_the_switch() -> None:
    """A registration endpoint in the document that no route answers is a broken client."""
    on = metadata_document(dcr_enabled=True)
    off = metadata_document(dcr_enabled=False)

    assert on["registration_endpoint"] == f"{PUBLIC_URL}/register"
    assert "registration_endpoint" not in off


def metadata_document(*, dcr_enabled: bool) -> dict[str, object]:
    app = Starlette(routes=metadata.metadata_routes(ENV, dcr_enabled=dcr_enabled))
    with TestClient(app) as http:
        return http.get(metadata.OPENID_CONFIGURATION_SUFFIX).json()


def test_the_document_route_is_served_once_and_by_us() -> None:
    """The SDK registers a document of its own at the same path, with a cache header."""
    paths = [
        path
        for path in (getattr(route, "path", "") for route in _exapp_routes())
        if path.endswith(metadata.AS_METADATA_SUFFIX)
    ]

    assert paths == [metadata.AS_METADATA_SUFFIX]


def test_the_registration_answer_carries_no_store(tmp_path: Path) -> None:
    """T-03-45: the PHP proxy caches a 201 without a cache header for an hour."""
    with client(tmp_path) as http:
        response = http.post(
            "/register",
            json={
                "redirect_uris": [REDIRECT],
                "client_name": "Claude",
                "token_endpoint_auth_method": "none",
            },
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"


def test_with_the_switch_off_a_registration_reaches_no_route_at_all(tmp_path: Path) -> None:
    with client(tmp_path, **{registry.ENV_DCR: "off"}) as http:
        response = http.post(
            "/register",
            json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none"},
        )

    assert response.status_code == 404, "the route does not exist while the switch is off"


def test_a_registration_of_forbidden_addresses_alone_is_refused_over_http(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        response = http.post(
            "/register",
            json={
                "redirect_uris": ["http://claude.ai/cb"],
                "token_endpoint_auth_method": "none",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"
    assert response.headers["cache-control"] == "no-store"


def test_the_registration_answer_names_the_addresses_that_were_registered(tmp_path: Path) -> None:
    """BL-04 over the wire: 201 for Cursor, with the private-use scheme gone from the echo."""
    with client(tmp_path) as http:
        response = http.post(
            "/register",
            json={
                "redirect_uris": CURSOR_URIS,
                "client_name": "Cursor",
                "token_endpoint_auth_method": "none",
            },
        )

    assert response.status_code == 201
    assert response.json()["redirect_uris"] == CURSOR_REGISTRABLE


def client(tmp_path: Path, **env: str) -> TestClient:
    subject = OAuthStore(tmp_path / "oauth.sqlite3", KEY)
    policy = registry.client_policy(ENV | env)
    instance = provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(ENV | env),
        env=ENV | env,
        policy=policy,
        store_provider=opener(subject),
    )
    return TestClient(Starlette(routes=provider_module.auth_routes(ENV | env, provider=instance)))


def test_the_exapp_application_serves_the_four_routes_and_the_standalone_one_none() -> None:
    """D-23: the modes of phase 1 must not grow an authorization server by accident."""
    exapp = {getattr(route, "path", "") for route in _exapp_routes()}
    standalone = {getattr(route, "path", "") for route in entry_http.build_app({}).router.routes}

    assert set(AS_PATHS) <= exapp
    assert not set(AS_PATHS) & standalone


def _exapp_routes() -> list[object]:
    return list(build_exapp_app(ENV).router.routes)


# --- the SDK models these checks hand in -------------------------------------------------


def _authorization_code() -> AuthorizationCode:
    return AuthorizationCode.model_validate(
        {
            "code": "any-code",
            "scopes": [metadata.TOOL_SCOPE],
            "expires_at": time.time() + 60,
            "client_id": CLIENT_ID,
            "code_challenge": "challenge",
            "redirect_uri": REDIRECT,
            "redirect_uri_provided_explicitly": True,
            "resource": f"{PUBLIC_URL}/mcp",
        }
    )


def _refresh_token() -> RefreshToken:
    return RefreshToken(token="any-token", client_id=CLIENT_ID, scopes=[metadata.TOOL_SCOPE])


def _access_token() -> AccessToken:
    return AccessToken(token="any-token", client_id=CLIENT_ID, scopes=[metadata.TOOL_SCOPE])


def _identity_assertion() -> IdentityAssertionParams:
    return IdentityAssertionParams(assertion="not.a.jwt")


# --- the revocation of a whole connection (SC 4) -------------------------------------------


async def issued(
    tmp_path: Path, **env: str
) -> tuple[provider_module.NextcloudOAuthProvider, OAuthStore, OAuthToken]:
    """A connection that exists: one access token, one refresh token, one app password."""
    subject, store = await approved(tmp_path, **env)
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None
    return subject, store, await subject.exchange_authorization_code(registration(), code)


def deletion_route(status: int = 200) -> respx.Route:
    """The one Nextcloud call a revocation makes: the app password of this connection."""
    return respx.delete(f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}").mock(
        return_value=httpx.Response(status)
    )


def guarded(checker: StoreTokenVerifier) -> TestClient:
    """The transport boundary alone, so a 401 can be read header by header."""

    async def endpoint(request: Request) -> Response:
        del request
        return Response("reached", status_code=200)

    route = Route(MCP_PATH, endpoint, methods=["GET"])
    route.app = RequireAppApi(route.app, ENV, token_verifier=checker)
    return TestClient(Starlette(routes=[route]))


def appapi_headers(user: str = "") -> dict[str, str]:
    """What HaRP puts on every request; an empty user id is the OAuth branch (03-01)."""
    return {
        "EX-APP-ID": "mcp_connector",
        "EX-APP-VERSION": "0.1.0",
        "AUTHORIZATION-APP-API": base64.b64encode(f"{user}:app-secret-test".encode()).decode(),
    }


@pytest.mark.anyio
async def test_revoking_a_refresh_token_ends_the_whole_family(tmp_path: Path) -> None:
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion_route()
        await subject.revoke_token(_presented_refresh(tokens))

    assert await store.load_access_token(tokens.access_token) is None
    row = await store.load_authorization(AUTH_ID)
    assert row is not None
    assert row.revoked_at is not None


@pytest.mark.anyio
async def test_revoking_an_access_token_ends_the_whole_family(tmp_path: Path) -> None:
    """RFC 7009 lets a client hand in either kind, and several of them hand in this one."""
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion_route()
        await subject.revoke_token(_presented_access(tokens))

    assert await store.load_access_token(tokens.access_token) is None
    assert await subject.load_refresh_token(registration(), tokens.refresh_token or "") is None


@pytest.mark.anyio
async def test_a_revocation_takes_effect_inside_the_cache_window(tmp_path: Path) -> None:
    """T-03-62: five seconds of a connection the user just ended is five too many."""
    subject, store, tokens = await issued(tmp_path)
    checker = StoreTokenVerifier(
        store_provider=opener(store), get_client=subject.get_client, env=ENV, clock=lambda: 1000.0
    )
    subject.on_revocation(checker.invalidate)
    assert await checker.verify_token(tokens.access_token) is not None, "the cache is warm"

    with respx.mock:
        deletion_route()
        await subject.revoke_token(_presented_refresh(tokens))

    assert await checker.verify_token(tokens.access_token) is None


@pytest.mark.anyio
async def test_the_401_after_a_revocation_points_where_an_anonymous_one_points(
    tmp_path: Path,
) -> None:
    """A client that lost its connection has to be able to start discovery again (SC 4)."""
    subject, store, tokens = await issued(tmp_path)
    checker = StoreTokenVerifier(
        store_provider=opener(store), get_client=subject.get_client, env=ENV
    )
    subject.on_revocation(checker.invalidate)

    with guarded(checker) as http:
        allowed = http.get(MCP_PATH, headers=appapi_headers() | _bearer(tokens))
        anonymous = http.get(MCP_PATH, headers=appapi_headers())
        assert allowed.status_code == 200

        with respx.mock:
            deletion_route()
            await subject.revoke_token(_presented_refresh(tokens))

        refused = http.get(MCP_PATH, headers=appapi_headers() | _bearer(tokens))

    assert refused.status_code == 401
    assert refused.headers["www-authenticate"] == anonymous.headers["www-authenticate"]
    assert "resource_metadata=" in refused.headers["www-authenticate"]
    assert (tokens.access_token or "") not in refused.text


@pytest.mark.anyio
async def test_the_revocation_hands_the_app_password_back_to_nextcloud(tmp_path: Path) -> None:
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        await subject.revoke_token(_presented_refresh(tokens))
        assert deletion.call_count == 1, "one attempt, never a retry (D-37)"

    row = await store.load_authorization(AUTH_ID)
    assert row is not None
    assert row.cleanup_at is None, "the credential is gone, so nothing is left to clean up"


@pytest.mark.anyio
async def test_a_failed_deletion_does_not_hold_up_the_revocation(tmp_path: Path) -> None:
    """Pitfall 13: a revocation that hangs on a cleanup step keeps a user connected."""
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route(status=500)
        await subject.revoke_token(_presented_refresh(tokens))
        assert deletion.call_count == 1

    assert await store.load_access_token(tokens.access_token) is None
    row = await store.load_authorization(AUTH_ID)
    assert row is not None
    assert row.revoked_at is not None
    assert row.cleanup_at is not None, "the orphaned credential is noted, not forgotten"


@pytest.mark.anyio
async def test_ending_a_connection_by_its_handle_hands_the_app_password_back(
    tmp_path: Path,
) -> None:
    """BL-01: the handle path of the user's own page ends where the token path ends.

    ``end_connection`` wrote the three revocations and stopped, so the credential stayed
    valid at Nextcloud: the sweep named in its docstring reads
    ``abandoned_authorizations``, which filters ``revoked_at IS NULL`` and can therefore
    never see a row this method just revoked.
    """
    subject, store, _tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        assert await subject.end_connection(NC_USER, AUTH_ID) is True
        assert deletion.call_count == 1, "one attempt, never a retry (D-37)"

    row = await store.load_authorization(AUTH_ID)
    assert row is not None
    assert row.revoked_at is not None
    assert row.cleanup_at is None, "the credential is gone, so nothing is left to clean up"


@pytest.mark.anyio
async def test_ending_a_connection_survives_a_nextcloud_that_refuses_the_deletion(
    tmp_path: Path,
) -> None:
    """Pitfall 13: "disconnected" has to mean disconnected when the request returns."""
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion_route(status=500)
        assert await subject.end_connection(NC_USER, AUTH_ID) is True

    assert await store.load_access_token(tokens.access_token) is None
    row = await store.load_authorization(AUTH_ID)
    assert row is not None
    assert row.revoked_at is not None
    assert row.cleanup_at is not None, "the orphaned credential is noted, not forgotten"


@pytest.mark.anyio
async def test_ending_a_connection_of_another_account_changes_nothing(tmp_path: Path) -> None:
    """LO-01: the method took a handle alone, and the whole ownership check sat in its one
    caller. Correct today and a trap for the next one: an administrative view or a command
    of a later phase would call it with a handle it read somewhere. The comparison is cheap,
    it is the same ``is_user`` the page uses, and having it twice is the right direction for
    a method that ends somebody's access."""
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        assert await subject.end_connection("mallory", AUTH_ID) is False
        assert await subject.end_connection("", AUTH_ID) is False, "the app context owns nothing"
        assert not deletion.called

    assert await store.load_access_token(tokens.access_token) is not None
    row = await store.load_authorization(AUTH_ID)
    assert row is not None
    assert row.revoked_at is None


@pytest.mark.anyio
async def test_ending_an_unknown_connection_calls_nothing_at_all(tmp_path: Path) -> None:
    """The page answers the same sentence for unknown and revoked, and writes nothing."""
    subject, store, _tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        assert await subject.end_connection(NC_USER, "a-handle-of-nobody") is False
        assert await subject.end_connection(NC_USER, AUTH_ID) is True
        assert await subject.end_connection(NC_USER, AUTH_ID) is False, "already revoked"
        assert deletion.call_count == 1, "the second attempt is not a second deletion"

    assert await store.load_authorization(AUTH_ID) is not None


@pytest.mark.anyio
async def test_a_token_this_server_never_issued_changes_nothing(tmp_path: Path) -> None:
    """RFC 7009 section 2.2: 200 for an unknown token, and no hint that it was unknown."""
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        await subject.revoke_presented_token(CLIENT_ID, "a-token-of-somebody-else")
        assert not deletion.called

    assert await store.load_access_token(tokens.access_token) is not None


@pytest.mark.anyio
async def test_a_client_cannot_revoke_the_connection_of_another_client(tmp_path: Path) -> None:
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        await subject.revoke_presented_token("some-other-client", tokens.refresh_token or "")
        assert not deletion.called

    assert await store.load_access_token(tokens.access_token) is not None


@pytest.mark.anyio
async def test_the_revocation_endpoint_answers_200_and_no_store(tmp_path: Path) -> None:
    subject, store, tokens = await issued(tmp_path)

    with respx.mock:
        deletion_route()
        with serving(subject) as http:
            response = http.post(
                "/revoke", data={"client_id": CLIENT_ID, "token": tokens.refresh_token or ""}
            )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert await store.load_access_token(tokens.access_token) is None


@pytest.mark.anyio
async def test_the_revocation_endpoint_refuses_a_client_it_cannot_authenticate(
    tmp_path: Path,
) -> None:
    subject, store, tokens = await issued(tmp_path, secret=SECRET)

    with serving(subject) as http:
        response = http.post(
            "/revoke",
            data={
                "client_id": CLIENT_ID,
                "client_secret": "not-the-secret",
                "token": tokens.refresh_token or "",
            },
        )

    assert response.status_code == 401
    assert await store.load_access_token(tokens.access_token) is not None


@pytest.mark.anyio
async def test_the_revocation_endpoint_refuses_a_body_without_a_token(tmp_path: Path) -> None:
    subject, _store, _tokens = await issued(tmp_path)

    with serving(subject) as http:
        response = http.post("/revoke", data={"client_id": CLIENT_ID})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


@pytest.mark.anyio
async def test_a_body_no_parser_can_read_is_refused_by_both_client_endpoints(
    tmp_path: Path,
) -> None:
    """HI-02 on the two machine endpoints: ``Request.form()`` is not a total function.

    ``python-multipart`` raises an exception Starlette does not translate, so a broken
    multipart body left ``/token`` and ``/revoke`` as an unhandled 500 with a traceback in
    the log instead of the error shapes both of them promise. The body of such a request may
    carry a client secret, which is the second reason it may not reach a traceback.
    """
    subject, _store = build(tmp_path)
    await subject.register_client(registration())
    broken = {"Content-Type": "multipart/form-data; boundary=the-boundary"}

    with serving(subject) as http:
        revocation = http.post("/revoke", headers=broken, content=b"not a multipart body")
        token = http.post("/token", headers=broken, content=b"not a multipart body")

    # Both land in the client authentication, which reads the body first and now refuses a
    # request it cannot read instead of raising through it. 401 is the honest answer:
    # nothing in that body authenticated anybody. The error name is each endpoint's own,
    # ours on /revoke and the SDK's on /token, and neither is a traceback.
    for refusal in (revocation, token):
        assert refusal.status_code == 401
        assert refusal.headers["cache-control"] == "no-store"
    assert revocation.json()["error"] == "unauthorized_client"
    assert token.json()["error"] == "invalid_client"


# --- the sweep of the sign ins nobody finished ---------------------------------------------


@pytest.mark.anyio
async def test_a_sign_in_nobody_finished_hands_its_credential_back(tmp_path: Path) -> None:
    """Plan 03-05 writes the app password before anybody consents, because the poll of the
    Login Flow v2 answers 200 exactly once. A browser that is closed at that moment would
    otherwise leave a working Nextcloud credential behind for good (pitfall 13, D-34)."""
    subject, store = build(tmp_path)
    await subject.register_client(registration())
    await store.create_authorization(
        "the-flow-nobody-came-back-to",
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
        now=int(time.time()) - FLOW_TTL - 1,
    )

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_abandoned()

    assert swept == 1
    assert deletion.call_count == 1
    assert await store.load_authorization("the-flow-nobody-came-back-to") is None


@pytest.mark.anyio
async def test_the_sweep_leaves_a_running_sign_in_and_a_live_connection_alone(
    tmp_path: Path,
) -> None:
    subject, store, tokens = await issued(tmp_path)
    await store.create_authorization(
        "a-sign-in-that-is-still-running",
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_abandoned()
        assert not deletion.called

    assert swept == 0
    assert await store.load_authorization(AUTH_ID) is not None
    assert await store.load_access_token(tokens.access_token) is not None


@pytest.mark.anyio
async def test_the_sweep_takes_at_most_a_handful_per_call(tmp_path: Path) -> None:
    """A browser request pays for this, so the cost of one call is bounded by construction."""
    subject, store = build(tmp_path)
    await subject.register_client(registration())
    for index in range(provider_module.SWEEP_LIMIT + 3):
        await store.create_authorization(
            f"abandoned-{index}",
            client_id=CLIENT_ID,
            nc_user=NC_USER,
            nc_account_id=NC_USER,
            app_password=APP_PASSWORD,
            scopes=metadata.TOOL_SCOPE,
            resource=RESOURCE,
            now=int(time.time()) - FLOW_TTL - 1,
        )

    with respx.mock:
        deletion_route()
        swept = await subject.sweep_abandoned()

    assert swept == provider_module.SWEEP_LIMIT


@pytest.mark.anyio
async def test_the_sweep_leaves_a_finished_binding_standing(tmp_path: Path) -> None:
    """A binding of the exchange path never owns a token (it acts under a foreign one), so
    it matches the abandoned shape exactly. The sweep excepts its reserved client, and only
    the user's own revocation (plan 23-06) and the purge ever hand its password back."""
    subject, store = build(tmp_path)
    await store.save_client(
        exchange_accounts.EXCHANGE_CLIENT_ID,
        metadata_json='{"client_id": "reserved"}',
        allowed=False,
    )
    await store.create_authorization(
        "the-finished-binding",
        client_id=exchange_accounts.EXCHANGE_CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
        now=int(time.time()) - FLOW_TTL - 1,
    )

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_abandoned()

    assert swept == 0
    assert not deletion.called
    assert await store.load_authorization("the-finished-binding") is not None
    # The binding keeps its credential: an immediate second sweep changes nothing either.
    assert await store.app_password("the-finished-binding") == APP_PASSWORD
    with respx.mock:
        deletion_route()
        assert await subject.sweep_abandoned() == 0
    assert await store.app_password("the-finished-binding") == APP_PASSWORD


@pytest.mark.anyio
async def test_a_holding_row_under_another_reserved_client_is_still_swept(
    tmp_path: Path,
) -> None:
    """Exactly one client is excepted. A holding row of a sign in nobody confirmed rides
    under a different reserved client, so the existing sweep takes it and hands its
    Nextcloud app password back (T-23-23)."""
    subject, store = build(tmp_path)
    await store.save_client(
        "urn:mcp-connector:another-reserved-path",
        metadata_json='{"client_id": "reserved"}',
        allowed=False,
    )
    await store.create_authorization(
        "the-holding-row-nobody-confirmed",
        client_id="urn:mcp-connector:another-reserved-path",
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
        now=int(time.time()) - FLOW_TTL - 1,
    )

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_abandoned()

    assert swept == 1
    assert deletion.call_count == 1
    assert await store.load_authorization("the-holding-row-nobody-confirmed") is None


# --- WR-04: a client that runs out gives its app passwords back before its row goes --------


@pytest.mark.anyio
async def test_an_expired_client_hands_its_app_passwords_back_before_it_is_deleted(
    tmp_path: Path,
) -> None:
    """WR-04, the reachable case: a registration whose user signed in and approved while
    the client never exchanged the code has last_used_at IS NULL, so after a day the row
    went, and the cascade took the encrypted app password with it. The credential kept
    working at Nextcloud and no later sweep could find it, because the ciphertext was gone.
    """
    subject, store = build(tmp_path)
    await store.save_client(
        CLIENT_ID,
        metadata_json=registration().model_dump_json(),
        now=int(time.time()) - UNUSED_CLIENT_TTL - 1,
    )
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_expired_clients()

    assert swept == 1
    assert deletion.call_count == 1, "the app password went back to Nextcloud"
    assert await store.load_client(CLIENT_ID) is None
    assert await store.load_authorization(AUTH_ID) is None


@pytest.mark.anyio
async def test_the_client_lookup_hands_the_credentials_back_when_it_expires_a_row(
    tmp_path: Path,
) -> None:
    """The second place a client row is deleted, and it is the one on the request path."""
    subject, store = build(tmp_path)
    await store.save_client(
        CLIENT_ID,
        metadata_json=registration().model_dump_json(),
        now=int(time.time()) - UNUSED_CLIENT_TTL - 1,
    )
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )

    with respx.mock:
        deletion = deletion_route()
        assert await subject.get_client(CLIENT_ID) is None

    assert deletion.call_count == 1
    assert await store.load_authorization(AUTH_ID) is None


@pytest.mark.anyio
async def test_an_expired_client_hands_back_more_connections_than_the_sweep_limit(
    tmp_path: Path,
) -> None:
    """BL-01, point 4: ``delete_client`` cascades, so a capped read loses the rest silently.

    ``authorizations_of_client`` was read once with ``SWEEP_LIMIT`` and the delete of the
    client row took every further connection with it, ciphertext included. From the fourth
    connection of one registration on, the app password was neither handed back nor
    findable by any later sweep, which is exactly the failure mode WR-04 was built against.
    """
    subject, store = build(tmp_path)
    await store.save_client(
        CLIENT_ID,
        metadata_json=registration().model_dump_json(),
        now=int(time.time()) - UNUSED_CLIENT_TTL - 1,
    )
    handles = [f"connection-{index}" for index in range(provider_module.SWEEP_LIMIT + 2)]
    for handle in handles:
        await store.create_authorization(
            handle,
            client_id=CLIENT_ID,
            nc_user=NC_USER,
            nc_account_id=NC_USER,
            app_password=APP_PASSWORD,
            scopes=metadata.TOOL_SCOPE,
            resource=RESOURCE,
        )

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_expired_clients()

    assert swept == 1
    assert deletion.call_count == len(handles), "every credential of that client went back"
    for handle in handles:
        assert await store.load_authorization(handle) is None


@pytest.mark.anyio
async def test_a_client_that_did_not_run_out_keeps_its_connections(tmp_path: Path) -> None:
    """The counter probe: the sweep must not touch a registration that is in use."""
    subject, store = await approved(tmp_path)

    with respx.mock:
        deletion = deletion_route()
        swept = await subject.sweep_expired_clients()

    assert swept == 0
    assert not deletion.called
    assert await store.load_authorization(AUTH_ID) is not None
    assert await store.load_client(CLIENT_ID) is not None


@pytest.mark.anyio
async def test_a_revocation_that_fails_still_removes_the_expired_client(
    tmp_path: Path,
) -> None:
    """The rule of every cleanup path of this phase: the row goes even when the credential
    could not be handed back, and the failure is loud in the log rather than silent."""
    subject, store = build(tmp_path)
    await store.save_client(
        CLIENT_ID,
        metadata_json=registration().model_dump_json(),
        now=int(time.time()) - UNUSED_CLIENT_TTL - 1,
    )
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=metadata.TOOL_SCOPE,
        resource=RESOURCE,
    )

    with respx.mock:
        deletion_route(500)
        swept = await subject.sweep_expired_clients()

    assert swept == 1
    assert await store.load_client(CLIENT_ID) is None
    assert await store.load_authorization(AUTH_ID) is None


# --- the throttle of our own authorization paths (SC 5, D-37) ------------------------------


def probe(
    *, machine: bool, limit: int = 3, ceiling: int = 100
) -> tuple[TestClient, throttle_module.Throttle]:
    """One route that answers whatever a caller asks for, behind the throttle wrapper."""
    box = throttle_module.Throttle(limit=limit, ceiling=ceiling, window=60)

    async def endpoint(request: Request) -> Response:
        return Response("body", status_code=int(request.query_params.get("status") or 400))

    route = Route("/probe", endpoint, methods=["GET"])
    route.app = throttle_module.Throttled(route.app, box, "probe", machine=machine, env=ENV)
    return TestClient(Starlette(routes=[route])), box


def test_a_flood_of_failures_ends_in_429_with_a_retry_after() -> None:
    http, _box = probe(machine=True)

    for _attempt in range(3):
        assert http.get("/probe").status_code == 400

    throttled = http.get("/probe")
    assert throttled.status_code == 429
    assert int(throttled.headers["retry-after"]) >= 1
    assert throttled.headers["cache-control"] == "no-store"


def test_the_json_answer_names_the_same_seconds_as_its_header() -> None:
    http, _box = probe(machine=True)
    for _attempt in range(3):
        http.get("/probe")

    throttled = http.get("/probe")

    body = throttled.json()
    assert body["error"] == "temporarily_unavailable"
    assert throttled.headers["retry-after"] in body["error_description"]


def test_the_html_answer_names_the_same_seconds_as_its_header() -> None:
    http, _box = probe(machine=False)
    for _attempt in range(3):
        http.get("/probe")

    throttled = http.get("/probe")
    seconds = throttled.headers["retry-after"]

    assert throttled.status_code == 429
    assert "text/html" in throttled.headers["content-type"]
    assert f"Wait {seconds} seconds" in throttled.text
    assert throttled.headers["cache-control"] == "no-store"


def test_a_successful_request_pays_back_one_failure_and_never_the_window() -> None:
    """WR-03: clearing the counter was an off switch. The path classes are shared surfaces,
    so a caller guessing flow ids only had to interleave one harmless successful request
    every ninth attempt to stay at zero forever. One success pays back exactly one failure:
    two failures, a success, two failures is three, and three is the limit here."""
    http, _box = probe(machine=True)

    for _attempt in range(2):
        assert http.get("/probe").status_code == 400
    assert http.get("/probe?status=200").status_code == 200
    for _attempt in range(2):
        assert http.get("/probe").status_code == 400

    assert http.get("/probe?status=200").status_code == 429


def test_a_success_never_pays_back_more_than_it_spent() -> None:
    """The forgiving half of the same rule: a person who mistypes something twice and then
    succeeds does not carry the two around for the rest of the window."""
    http, _box = probe(machine=True)

    assert http.get("/probe").status_code == 400
    for _attempt in range(3):
        assert http.get("/probe?status=200").status_code == 200

    for _attempt in range(2):
        assert http.get("/probe").status_code == 400
    assert http.get("/probe?status=200").status_code == 200


def test_a_forged_forwarded_header_still_meets_the_global_ceiling() -> None:
    """The per source counter can be split by anybody who can write a header; the ceiling
    of the path class cannot, and that is what keeps the Nextcloud round trips bounded."""
    http, _box = probe(machine=True, limit=3, ceiling=5)

    for index in range(5):
        answer = http.get("/probe", headers={"X-Forwarded-For": f"10.0.0.{index}"})
        assert answer.status_code == 400

    assert http.get("/probe", headers={"X-Forwarded-For": "10.0.0.99"}).status_code == 429


def test_the_throttle_remembers_a_bounded_number_of_sources() -> None:
    box = throttle_module.Throttle(limit=3, ceiling=1000, window=60)

    for index in range(throttle_module.SOURCE_LIMIT + 50):
        box.record_attempt("probe", f"10.0.0.{index}")

    assert len(box._counters) <= throttle_module.SOURCE_LIMIT


def test_the_throttle_stores_neither_a_credential_nor_an_identity() -> None:
    """T-03-65: a counter that keeps what it counted is itself a source of data."""
    box = throttle_module.Throttle(limit=3, ceiling=100, window=60)

    box.record_attempt(throttle_module.CLASS_TOKEN, "10.0.0.7")

    kept = repr(sorted(box._counters))
    assert "10.0.0.7" not in kept, "the source is a digest, never the address"
    assert throttle_module.CLASS_TOKEN not in kept
    assert all(len(key) == 64 for key in box._counters), "SHA-256 hex and nothing else"

    tree = ast.parse(inspect.getsource(throttle_module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                node.body = node.body[1:] or [ast.Pass()]
    code = ast.unparse(ast.fix_missing_locations(tree)).lower()

    assert "sha256" in code, "the source of a request is remembered as a digest"
    assert "authorization" not in code, "the credential header is never read here"
    assert "nc_user" not in code
    assert "refresh" not in code


def test_the_authorization_paths_are_throttled_and_the_mcp_route_is_not() -> None:
    """SC 5: the throttle sits on our own authorization paths, never on the tool call."""
    throttled = {
        getattr(route, "path", "")
        for route in _exapp_routes()
        if _is_throttled(getattr(route, "app", None))
    }

    assert {"/token", "/register", "/revoke", "/authorize"} <= throttled
    assert MCP_PATH not in throttled


@pytest.mark.anyio
async def test_a_flood_against_the_token_endpoint_reaches_no_nextcloud(tmp_path: Path) -> None:
    """Pitfall 5: every request with an Authorization header costs a Nextcloud round trip,
    and the throttle is the only thing that bounds how many of them a flood can buy."""
    subject, _store = await approved(tmp_path, secret=SECRET)
    box = throttle_module.Throttle(limit=3, ceiling=100, window=60)

    with respx.mock, serving(subject, throttle=box) as http:
        answers = [
            http.post("/token", data=token_request(client_secret="wrong")).status_code
            for _attempt in range(5)
        ]
        assert len(respx.calls) == 0

    assert answers[:3] == [401, 401, 401]
    assert answers[-1] == 429


def _is_throttled(app: object) -> bool:
    """Whether this route carries the throttle, under the ``no-store`` wrapper or not."""
    while app is not None:
        if isinstance(app, throttle_module.Throttled):
            return True
        app = getattr(app, "_app", None)
    return False


def _bearer(tokens: OAuthToken) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens.access_token}"}


def _presented_refresh(tokens: OAuthToken) -> RefreshToken:
    return RefreshToken(
        token=tokens.refresh_token or "", client_id=CLIENT_ID, scopes=[metadata.TOOL_SCOPE]
    )


def _presented_access(tokens: OAuthToken) -> AccessToken:
    return AccessToken(token=tokens.access_token, client_id=CLIENT_ID, scopes=[metadata.TOOL_SCOPE])

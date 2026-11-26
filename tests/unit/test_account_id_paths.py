"""Issue 60: the account id, not the login name, names every DAV home and every id check.

On LDAP/AD and with a login by email address, the name a user signs in with and the
Nextcloud user id differ (``imedina`` or ``ivan@example.com`` against a GUID). Login Flow
v2 hands back the typed name, which is right for Basic authentication and wrong for every
path below ``/remote.php/dav/<kind>/<uid>/``: those take the user id and answer 404 for
anything else. The connection row already stores the canonical id (``nc_account_id``,
``oauth/principal.py``); these tests hold that it reaches every path and every comparison,
while Basic keeps the login name and a legacy row without an id keeps today's behaviour.
"""

import base64
from typing import Any

import httpx
import pytest
import respx
from starlette.requests import Request

from mcp_connector import config, deps
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.clients import caldav, carddav, dav, systemtags
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials
from mcp_connector.nextcloud.exclusion import ExclusionGuard
from mcp_connector.oauth.exchange_accounts import EXCHANGE_CLIENT_ID
from mcp_connector.oauth.verifier import (
    CREDENTIAL_IMPERSONATE,
    OAUTH_STATE_ATTR,
    OAuthIdentity,
)

BASE = "http://nc.test"
SECRET = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
ACCOUNT = "B9642E94-77DA-4189-9CF3-155646E581ED"
LOGINS = ["imedina", "ivan@example.com"]

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
AA_VERSION = "34.0.3"


@pytest.fixture(autouse=True)
def no_files_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.ENV_FILES_ROOT, raising=False)


@pytest.fixture(params=LOGINS)
def login(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def creds(login: str) -> Credentials:
    return Credentials(BASE, login, SECRET, account_id=ACCOUNT)


# --- the credential object ------------------------------------------------------------------


def test_basic_auth_keeps_the_login_name(creds: Credentials, login: str) -> None:
    request = httpx.Request("GET", f"{BASE}/x")
    flow = creds.auth().sync_auth_flow(request)
    sent = next(flow)
    expected = httpx.BasicAuth(login, SECRET)
    reference = next(expected.sync_auth_flow(httpx.Request("GET", f"{BASE}/x")))
    assert sent.headers["Authorization"] == reference.headers["Authorization"]


def test_the_account_defaults_to_the_login_name() -> None:
    """Legacy rows, passthrough and stdio: no stored id, so nothing changes."""
    legacy = Credentials(BASE, "alice", SECRET)
    assert legacy.account == "alice"
    assert dav.files_url(legacy, "/a.txt") == f"{BASE}/remote.php/dav/files/alice/a.txt"


def test_the_repr_names_the_account_and_hides_the_secret(creds: Credentials) -> None:
    text = repr(creds)
    assert ACCOUNT in text
    assert SECRET not in text


# --- files, search, versions, uploads -------------------------------------------------------


def test_files_url_uses_the_account_id(creds: Credentials) -> None:
    assert dav.files_url(creds, "/Docs/a.txt") == (
        f"{BASE}/remote.php/dav/files/{ACCOUNT}/Docs/a.txt"
    )


def test_search_scope_uses_the_account_id(creds: Credentials) -> None:
    assert dav.search_scope(creds) == f"/files/{ACCOUNT}"
    assert dav.search_scope(creds, "/Docs") == f"/files/{ACCOUNT}/Docs"


def test_versions_url_uses_the_account_id(creds: Credentials) -> None:
    assert dav.versions_url(creds, 42) == f"{BASE}/remote.php/dav/versions/{ACCOUNT}/versions/42"


def test_uploads_url_uses_the_account_id(creds: Credentials) -> None:
    url = dav.uploads_url(creds, "u1", path="/a.bin")
    assert url.startswith(f"{BASE}/remote.php/dav/uploads/{ACCOUNT}/nc-mcp-")


def test_an_account_id_is_quoted_in_every_path() -> None:
    odd = Credentials(BASE, "login", SECRET, account_id="ivan medina")
    assert dav.files_url(odd, "/a").startswith(f"{BASE}/remote.php/dav/files/ivan%20medina/")
    assert dav.search_scope(odd) == "/files/ivan%20medina"
    assert systemtags.home_url(odd) == f"{BASE}/remote.php/dav/files/ivan%20medina/"


def multistatus(*hrefs: str) -> bytes:
    responses = "".join(
        f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>"
        f"<oc:fileid>{index}</oc:fileid><d:resourcetype/>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for index, href in enumerate(hrefs, start=10)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">{responses}</d:multistatus>'
    ).encode()


def test_home_entries_map_hrefs_that_carry_the_account_id(creds: Credentials) -> None:
    """Nextcloud answers PROPFIND and REPORT with hrefs below the user id."""
    body = multistatus(
        f"/remote.php/dav/files/{ACCOUNT}/Docs/a.txt",
        f"/remote.php/dav/files/{ACCOUNT}/",
    )
    paths = [path for path, _ in dav.home_entries(body, creds)]
    assert paths == ["/Docs/a.txt", "/"]


def test_parse_entries_keep_hrefs_that_carry_the_account_id(creds: Credentials) -> None:
    body = multistatus(f"/remote.php/dav/files/{ACCOUNT}/Docs/a.txt")
    assert [entry["path"] for entry in dav.parse_entries(body, creds)] == ["/Docs/a.txt"]


def test_a_href_below_the_login_name_is_not_this_home(creds: Credentials, login: str) -> None:
    """The login name is no home: a href below it is somewhere else and maps to None."""
    body = multistatus(f"/remote.php/dav/files/{login}/a.txt")
    assert [path for path, _ in dav.home_entries(body, creds)] == [None]


def test_a_quoted_account_id_in_a_href_is_decoded_before_the_comparison() -> None:
    odd = Credentials(BASE, "login", SECRET, account_id="ivan medina")
    body = multistatus("/remote.php/dav/files/ivan%20medina/a.txt")
    assert [path for path, _ in dav.home_entries(body, odd)] == ["/a.txt"]


# --- system tags ----------------------------------------------------------------------------


def test_the_systemtags_home_uses_the_account_id(creds: Credentials) -> None:
    assert systemtags.home_url(creds) == f"{BASE}/remote.php/dav/files/{ACCOUNT}/"


ADMIN_USERS = f"{BASE}/ocs/v2.php/cloud/groups/admin/users"
JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


def admin_members(*uids: str) -> bytes:
    listed = ",".join(f'"{uid}"' for uid in uids)
    return (
        b'{"ocs":{"meta":{"status":"ok","statuscode":200,"message":"OK"},"data":{"users":['
        + listed.encode()
        + b"]}}}"
    )


@pytest.mark.anyio
async def test_the_admin_check_compares_the_account_id(creds: Credentials) -> None:
    """The member list carries user ids, never login names."""
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_mocked=True) as mock:
            mock.route(method="GET", url=ADMIN_USERS).mock(
                return_value=httpx.Response(
                    200, content=admin_members(ACCOUNT), headers=JSON_HEADERS
                )
            )
            assert await systemtags.confirm_admin(client, creds) is True


@pytest.mark.anyio
async def test_the_login_name_in_the_admin_list_is_not_this_account(
    creds: Credentials, login: str
) -> None:
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_mocked=True) as mock:
            mock.route(method="GET", url=ADMIN_USERS).mock(
                return_value=httpx.Response(200, content=admin_members(login), headers=JSON_HEADERS)
            )
            assert await systemtags.confirm_admin(client, creds) is False


# --- calendars, tasks, contacts -------------------------------------------------------------


def test_the_calendar_home_uses_the_account_id(creds: Credentials) -> None:
    assert caldav.calendars_home_url(creds) == f"{BASE}/remote.php/dav/calendars/{ACCOUNT}/"
    assert caldav.calendar_url(creds, "personal").startswith(
        f"{BASE}/remote.php/dav/calendars/{ACCOUNT}/"
    )


def test_the_addressbook_home_uses_the_account_id(creds: Credentials) -> None:
    assert carddav.addressbooks_home_url(creds) == (
        f"{BASE}/remote.php/dav/addressbooks/users/{ACCOUNT}/"
    )


# --- caches keyed by identity ---------------------------------------------------------------


@pytest.mark.anyio
async def test_two_accounts_behind_one_login_name_never_share_a_capability_cache() -> None:
    """The key is never coarser than before: one more value can only split an entry."""
    capabilities.clear_cache()
    first = Credentials(BASE, "imedina", SECRET, account_id=ACCOUNT)
    second = Credentials(BASE, "imedina", SECRET, account_id="another-account")
    body = b'{"ocs":{"meta":{"status":"ok","statuscode":200,"message":"OK"},"data":{}}}'
    try:
        async with httpx.AsyncClient() as client:
            with respx.mock(assert_all_mocked=True) as mock:
                route = mock.route(
                    method="GET", url=f"{BASE}/ocs/v2.php{capabilities.CAPABILITIES_PATH}"
                ).mock(return_value=httpx.Response(200, content=body, headers=JSON_HEADERS))
                await capabilities.load(NcClients(client, first))
                await capabilities.load(NcClients(client, second))
        assert route.call_count == 2
    finally:
        capabilities.clear_cache()


@pytest.mark.anyio
async def test_an_exclusion_guard_refuses_a_second_account_behind_the_same_login() -> None:
    guard = ExclusionGuard()
    first = Credentials(BASE, "imedina", SECRET, account_id=ACCOUNT)
    second = Credentials(BASE, "imedina", SECRET, account_id="another-account")
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_mocked=False) as mock:
            mock.route().mock(return_value=httpx.Response(500))
            await guard.scope(NcClients(client, first))
            with pytest.raises(ValueError, match="serves exactly one"):
                await guard.scope(NcClients(client, second))


# --- the credential layer -------------------------------------------------------------------


@pytest.fixture
def exapp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.ENV_APP_ID, APP_ID)
    monkeypatch.setenv(config.ENV_APP_SECRET, APP_SECRET)
    monkeypatch.setenv(config.ENV_APP_VERSION, APP_VERSION)
    monkeypatch.setenv(config.ENV_AA_VERSION, AA_VERSION)
    monkeypatch.setenv(config.ENV_NEXTCLOUD_URL, BASE)
    monkeypatch.setenv(config.ENV_PUBLIC_URL, "https://cloud.example.com/exapps/mcp_connector")
    monkeypatch.delenv(config.ENV_STATIC_BEARER, raising=False)
    monkeypatch.delenv(config.ENV_APP_PASSWORD, raising=False)


class _RequestContext:
    def __init__(self, request: Any) -> None:
        self.request = request


class _Context:
    """A tool context whose request carries a signed AppAPI header without a user."""

    def __init__(self, identity: OAuthIdentity) -> None:

        token = base64.b64encode(f":{APP_SECRET}".encode()).decode()
        headers = {
            "ex-app-id": APP_ID,
            "ex-app-version": APP_VERSION,
            "authorization-app-api": token,
        }
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
            }
        )
        setattr(request.state, OAUTH_STATE_ATTR, identity)
        self.request_context = _RequestContext(request)


def oauth_identity(**fields: Any) -> OAuthIdentity:
    values: dict[str, Any] = {
        "nc_user": "imedina",
        "principal": ACCOUNT,
        "app_password": SECRET,
        "auth_id": "auth",
        "client_id": "client",
    }
    values.update(fields)
    return OAuthIdentity(**values)


@pytest.mark.parametrize("login", LOGINS)
def test_an_oauth_connection_signs_in_with_the_login_and_reads_below_the_id(
    exapp_env: None, login: str
) -> None:
    creds = deps.resolve_credentials(_Context(oauth_identity(nc_user=login)))
    assert creds.mode == MODE_BASIC
    assert creds.user == login
    assert creds.account == ACCOUNT
    assert dav.files_url(creds, "/a") == f"{BASE}/remote.php/dav/files/{ACCOUNT}/a"


def test_a_legacy_connection_without_an_id_reads_below_the_login_name(exapp_env: None) -> None:
    """A row from before ``nc_account_id``: the principal is the login name (principal_of)."""
    creds = deps.resolve_credentials(_Context(oauth_identity(principal="imedina")))
    assert creds.user == "imedina"
    assert creds.account == "imedina"
    assert dav.files_url(creds, "/a") == f"{BASE}/remote.php/dav/files/imedina/a"


def test_an_impersonation_identity_impersonates_the_account_id(exapp_env: None) -> None:
    """AppAPI takes the user id in its header; a login name there is a different account."""
    who = oauth_identity(
        nc_user="imedina",
        app_password="",
        auth_id="",
        client_id=EXCHANGE_CLIENT_ID,
        credential=CREDENTIAL_IMPERSONATE,
    )
    creds = deps.resolve_credentials(_Context(who))
    assert creds.mode == MODE_APPAPI
    assert creds.user == ACCOUNT
    assert creds.account == ACCOUNT

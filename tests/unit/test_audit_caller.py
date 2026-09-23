"""Who made this call: the one answer the recording path is allowed to ask for.

The recording path may not use ``deps.resolve_credentials``. Its result carries the
Nextcloud app password, and it raises ``MCPError`` when a request has no user context, while
a recorder must never raise (D-13). So there is a second, smaller question next to it, and
this module holds it to four properties: it names the caller, it carries no secret, it makes
no call of any kind, and it answers ``None`` instead of raising.

No Nextcloud, no store and no socket: the contexts here are the ones the SDK hands a tool,
built by hand, exactly as ``test_oauth_credentials.py`` builds them.
"""

import base64
import dataclasses
from collections.abc import Mapping
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config, deps
from mcp_connector.audit import AUDIT_STATE_ATTR
from mcp_connector.deps import Caller, resolve_caller
from mcp_connector.exapp.middleware import RequireAppApi
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
AA_VERSION = "34.0.3"
BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"

NC_USER = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
AUTH_ID = "the-flow-this-authorization-was-born-in"
CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
CLIENT_NAME = "Claude"

#: The acting party of a foreign realm, the ``azp`` of an exchanged token. It is not a
#: registered client name, and that difference is what the fifth field of ``Caller`` exists
#: to keep readable.
ACTOR = "kc-client-of-another-realm"


@pytest.fixture
def exapp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deploy environment AppAPI injects into the ExApp container."""
    monkeypatch.setenv(config.ENV_APP_ID, APP_ID)
    monkeypatch.setenv(config.ENV_APP_SECRET, APP_SECRET)
    monkeypatch.setenv(config.ENV_APP_VERSION, APP_VERSION)
    monkeypatch.setenv(config.ENV_AA_VERSION, AA_VERSION)
    monkeypatch.setenv(config.ENV_NEXTCLOUD_URL, BASE_URL)
    monkeypatch.setenv(config.ENV_PUBLIC_URL, PUBLIC_URL)
    monkeypatch.delenv(config.ENV_STATIC_BEARER, raising=False)
    monkeypatch.delenv(config.ENV_APP_PASSWORD, raising=False)


def appapi_headers(user: str = NC_USER, secret: str = APP_SECRET) -> dict[str, str]:
    """The three headers HaRP puts in front of every request it forwards."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


class FakeRequestContext:
    """What the SDK hands a tool: the request of the message, and the parameters of the call.

    ``params`` is here although nothing in this module reads it: the recording path of the
    later plans of this phase takes the tool name and the parameter names from it, and a
    context that lacks the field would let those tests pass for the wrong reason.
    """

    def __init__(self, request: Request | None, params: Any = None) -> None:
        self.request = request
        self.params = params


class FakeContext:
    """The context object of a tool call, in the shapes ``deps`` reads it in."""

    def __init__(
        self,
        headers: Mapping[str, str] | None = None,
        identity: OAuthIdentity | None = None,
        *,
        with_request: bool = True,
        params: Any = None,
    ) -> None:
        self.headers = headers
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [
                    (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
                ],
            }
        )
        if identity is not None:
            setattr(request.state, OAUTH_STATE_ATTR, identity)
        self.request_context = FakeRequestContext(request if with_request else None, params)


MIDDLEWARE_ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_NEXTCLOUD_URL: BASE_URL,
    config.ENV_PUBLIC_URL: PUBLIC_URL,
}


def guarded_app(recorder: object | None) -> tuple[Starlette, list[object | None]]:
    """One route behind the real boundary, reporting what the boundary left for it."""
    seen: list[object | None] = []

    async def served(request: Request) -> Response:
        seen.append(getattr(request.state, AUDIT_STATE_ATTR, None))
        return PlainTextResponse("served")

    app = Starlette(routes=[Route("/mcp", served, methods=["GET"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = RequireAppApi(route.app, MIDDLEWARE_ENV, audit_recorder=recorder)
    return app, seen


def identity(**fields: Any) -> OAuthIdentity:
    values: dict[str, Any] = {
        "nc_user": NC_USER,
        "principal": NC_USER,
        "app_password": APP_PASSWORD,
        "auth_id": AUTH_ID,
        "client_id": CLIENT_ID,
        "client_name": CLIENT_NAME,
    }
    values.update(fields)
    return OAuthIdentity(**values)


# --- the two ways a call gets a name --------------------------------------------------------


def test_an_oauth_call_names_the_user_the_client_and_the_connection(exapp_env: None) -> None:
    """D-08: client id, connection id and the registered name, and no address of anybody."""
    caller = resolve_caller(FakeContext(headers=appapi_headers(user=""), identity=identity()))

    assert caller is not None
    assert caller.nc_user == NC_USER
    assert caller.client_id == CLIENT_ID
    assert caller.auth_id == AUTH_ID
    assert caller.client_name == CLIENT_NAME
    assert caller.actor is None, "a registered client acts for itself; nobody delegated here"


def test_an_exchanged_token_names_the_acting_party_and_not_a_client_name(
    exapp_env: None,
) -> None:
    """AUDIT-07: the ``azp`` of a foreign realm travels in its own field.

    A reader must be able to tell the name a client gave itself from the party a token was
    exchanged for, without reading ``client_id`` alongside to work out which of the two the
    one name column is carrying this time.
    """
    caller = resolve_caller(
        FakeContext(
            headers=appapi_headers(user=""),
            identity=identity(client_name="", actor=ACTOR),
        )
    )

    assert caller is not None
    assert caller.actor == ACTOR
    assert caller.client_name == ""


def test_an_identity_that_names_no_acting_party_answers_none(exapp_env: None) -> None:
    """The empty string of the identity and "nobody named" are the same fact in a row."""
    caller = resolve_caller(FakeContext(headers=appapi_headers(user=""), identity=identity()))

    assert caller is not None
    assert caller.actor is None


def test_an_appapi_call_names_the_user_and_nothing_about_a_client(exapp_env: None) -> None:
    """The impersonation path has a Nextcloud user and no client of its own (AUTH-01)."""
    caller = resolve_caller(FakeContext(headers=appapi_headers()))

    assert caller is not None
    assert caller.nc_user == NC_USER
    assert caller.client_id is None
    assert caller.auth_id is None
    assert caller.client_name is None
    assert caller.actor is None


# --- what happens when there is nothing to read ---------------------------------------------


@pytest.mark.parametrize(
    "ctx",
    [
        None,
        object(),
        FakeContext(with_request=False),
        FakeContext(),
    ],
    ids=["none", "a-foreign-object", "no-request", "no-identity-and-no-handshake"],
)
def test_a_context_without_an_answer_is_none_and_never_an_exception(
    exapp_env: None, ctx: Any
) -> None:
    """Every missing step is one answer, and that answer is a gap the check makes visible."""
    assert resolve_caller(ctx) is None


def test_the_recorder_stays_silent_where_the_credential_layer_raises(exapp_env: None) -> None:
    """The reason this function exists next to ``resolve_credentials`` (D-13)."""
    ctx = FakeContext(headers=appapi_headers(user=""))

    with pytest.raises(deps.MCPError):
        deps.resolve_credentials(ctx)

    assert resolve_caller(ctx) is None


# --- what the answer may not carry ----------------------------------------------------------


def test_the_caller_carries_five_fields_and_no_secret(exapp_env: None) -> None:
    """T-18-12: a recorder that could see the app password would eventually write it."""
    names = sorted(field.name for field in dataclasses.fields(Caller))

    assert names == ["actor", "auth_id", "client_id", "client_name", "nc_user"]

    caller = resolve_caller(FakeContext(headers=appapi_headers(user=""), identity=identity()))

    assert caller is not None
    assert APP_PASSWORD not in repr(caller)
    assert "***" not in repr(caller), "there is nothing here that would have to be masked"


# --- the recorder travels with the request --------------------------------------------------


def test_the_boundary_leaves_the_recorder_where_the_recording_path_reads_it() -> None:
    """One constant for both sides, so the two cannot drift apart (AUDIT_STATE_ATTR)."""
    recorder = object()
    app, seen = guarded_app(recorder)

    with TestClient(app) as client:
        response = client.get("/mcp", headers=appapi_headers())

    assert response.status_code == 200
    assert seen == [recorder], "the very object that was handed in, not a copy of it"


def test_without_a_recorder_nothing_is_deposited_at_all() -> None:
    """The state this ships in (D-14): no attribute, no line, no difference to before."""
    app, seen = guarded_app(None)

    with TestClient(app) as client:
        response = client.get("/mcp", headers=appapi_headers())

    assert response.status_code == 200
    assert seen == [None]


def test_an_oauth_call_is_recorded_under_the_principal(exapp_env: None) -> None:
    """The audit chain of an account is keyed by the value AppAPI callers use as well."""
    caller = resolve_caller(
        FakeContext(
            headers=appapi_headers(user=""),
            identity=identity(nc_user="alice@example.com", principal="a1b2c3"),
        )
    )

    assert caller is not None
    assert caller.nc_user == "a1b2c3"

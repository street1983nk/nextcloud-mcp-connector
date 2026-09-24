"""Unit tests for ``entry_oauth``: settings, secret file, the standalone application."""

import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config, deps, entry_oauth
from mcp_connector.errors import ToolError
from mcp_connector.exapp.middleware import RequireOAuthBearer
from mcp_connector.exapp.ui import consent as ui_consent
from mcp_connector.oauth import chain, exchange_binding, oidc
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.metadata import (
    AS_METADATA_SUFFIX,
    OPENID_CONFIGURATION_SUFFIX,
    PRM_SUFFIX,
)
from mcp_connector.oauth.oidc_routes import OIDC_CALLBACK_PATH, OIDC_START_PATH
from mcp_connector.oauth.provider import NextcloudOAuthProvider
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity, StoreTokenVerifier

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions and links")

PUBLIC_URL = "https://mcp.example.com"
NC_URL = "http://nc.test"
ISSUER = "https://idp.example.com"
CLIENT_ID = "the-client-id"
PROVIDER_ID = "7"
MAPPING = oidc.STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1
SECRET_KEY_HEX = "ab" * 32

CONSENT_PATH = "/authorize/consent"

EXAPP_ONLY_PATHS: tuple[tuple[str, str], ...] = (
    ("GET", "/connect"),
    ("GET", "/connections"),
    ("POST", "/init"),
    ("PUT", "/enabled"),
    ("GET", "/heartbeat"),
)


# --- fixtures / helpers ------------------------------------------------------------------


def make_storage_dir(tmp_path: Path, *, name: str = "storage", mode: int = 0o700) -> Path:
    directory = tmp_path / name
    directory.mkdir()
    directory.chmod(mode)
    return directory


def make_key_file(
    tmp_path: Path, *, name: str = "key", content: str = SECRET_KEY_HEX, mode: int = 0o600
) -> Path:
    path = tmp_path / name
    path.write_text(content)
    path.chmod(mode)
    return path


def base_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    storage = make_storage_dir(tmp_path)
    key_file = make_key_file(tmp_path)
    env = {
        config.ENV_URL: NC_URL,
        config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH,
        config.ENV_PUBLIC_URL: PUBLIC_URL,
        config.ENV_OAUTH_STORAGE_DIR: str(storage),
        config.ENV_OAUTH_DATA_KEY_FILE: str(key_file),
        config.ENV_OIDC_ISSUER: ISSUER,
        config.ENV_OIDC_CLIENT_ID: CLIENT_ID,
        config.ENV_OIDC_PROVIDER_ID: PROVIDER_ID,
        config.ENV_OIDC_MAPPING: MAPPING,
    }
    env.update(overrides)
    return env


def without(env: Mapping[str, str], *names: str) -> dict[str, str]:
    return {key: value for key, value in env.items() if key not in names}


# --- load_settings: happy path ------------------------------------------------------------


def test_load_settings_happy_path(tmp_path: Path) -> None:
    env = base_env(tmp_path)

    settings = entry_oauth.load_settings(env)

    assert settings.public_url == PUBLIC_URL
    assert settings.oidc.redirect_uri == f"{PUBLIC_URL}{OIDC_CALLBACK_PATH}"
    assert isinstance(settings.oidc.provider_id, int)
    assert settings.oidc.provider_id == int(PROVIDER_ID)
    assert settings.oidc.algorithms == oidc.DEFAULT_ALGORITHMS
    assert settings.oidc.algorithms == ("RS256",)


def test_load_settings_strips_a_trailing_slash_from_the_public_url(tmp_path: Path) -> None:
    env = base_env(tmp_path, **{config.ENV_PUBLIC_URL: f"{PUBLIC_URL}/"})

    settings = entry_oauth.load_settings(env)

    assert settings.public_url == PUBLIC_URL
    assert settings.oidc.redirect_uri == f"{PUBLIC_URL}{OIDC_CALLBACK_PATH}"


# --- load_settings: refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "overrides"),
    [
        ("mode variable missing", {}),
        ("mode variable is another value", {config.ENV_AUTH_MODE: "exapp"}),
        ("mode variable is blank", {config.ENV_AUTH_MODE: "  "}),
    ],
)
def test_load_settings_refuses_when_oauth_mode_is_not_selected(
    tmp_path: Path, name: str, overrides: dict[str, str]
) -> None:
    if name == "mode variable missing":
        env = without(base_env(tmp_path), config.ENV_AUTH_MODE)
    else:
        env = base_env(tmp_path, **overrides)

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert config.ENV_AUTH_MODE in str(raised.value), name


@pytest.mark.parametrize("name", list(entry_oauth.CONFLICTING_VARIABLES))
def test_load_settings_refuses_every_conflicting_variable(tmp_path: Path, name: str) -> None:
    env = base_env(tmp_path, **{name: "something"})

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert name in str(raised.value)


def test_load_settings_refuses_a_plain_http_public_url(tmp_path: Path) -> None:
    env = base_env(tmp_path, **{config.ENV_PUBLIC_URL: "http://mcp.example.com"})

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert "https" in str(raised.value).lower()


@pytest.mark.parametrize(
    "name",
    [
        config.ENV_URL,
        config.ENV_PUBLIC_URL,
        config.ENV_OAUTH_STORAGE_DIR,
        config.ENV_OAUTH_DATA_KEY_FILE,
        config.ENV_OIDC_ISSUER,
        config.ENV_OIDC_CLIENT_ID,
        config.ENV_OIDC_PROVIDER_ID,
        config.ENV_OIDC_MAPPING,
    ],
)
def test_load_settings_refuses_every_missing_required_variable(tmp_path: Path, name: str) -> None:
    env = without(base_env(tmp_path), name)

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert name in str(raised.value)


def test_load_settings_refuses_a_non_numeric_provider_id(tmp_path: Path) -> None:
    env = base_env(tmp_path, **{config.ENV_OIDC_PROVIDER_ID: "not-a-number"})

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert config.ENV_OIDC_PROVIDER_ID in str(raised.value)


def test_load_settings_refuses_an_unknown_mapping(tmp_path: Path) -> None:
    env = base_env(tmp_path, **{config.ENV_OIDC_MAPPING: "some-other-strategy"})

    with pytest.raises(ToolError):
        entry_oauth.load_settings(env)


def test_load_settings_refuses_an_issuer_with_a_trailing_slash(tmp_path: Path) -> None:
    env = base_env(tmp_path, **{config.ENV_OIDC_ISSUER: f"{ISSUER}/"})

    with pytest.raises(ToolError):
        entry_oauth.load_settings(env)


def test_load_settings_refuses_hs256(tmp_path: Path) -> None:
    env = base_env(tmp_path, **{config.ENV_OIDC_ALGORITHMS: "HS256"})

    with pytest.raises(ToolError):
        entry_oauth.load_settings(env)


@posix_only
def test_load_settings_refuses_a_group_writable_storage_dir(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    Path(env[config.ENV_OAUTH_STORAGE_DIR]).chmod(0o770)

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert config.ENV_OAUTH_STORAGE_DIR in str(raised.value)


def test_load_settings_error_messages_never_carry_the_secret(tmp_path: Path) -> None:
    secret_file = make_key_file(tmp_path, name="secret", content="a-very-private-value")
    env = base_env(
        tmp_path,
        **{
            config.ENV_OIDC_CLIENT_SECRET_FILE: str(secret_file),
            config.ENV_OIDC_PROVIDER_ID: "not-a-number",
        },
    )

    with pytest.raises(ToolError) as raised:
        entry_oauth.load_settings(env)

    assert "a-very-private-value" not in str(raised.value)


# --- read_secret_file ------------------------------------------------------------------


SECRET_VALUE = "s3cr3t-client-value"


def write_secret(
    tmp_path: Path,
    *,
    content: str | bytes = SECRET_VALUE,
    mode: int = 0o600,
    name: str = "secret",
) -> Path:
    path = tmp_path / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)
    path.chmod(mode)
    return path


def test_read_secret_file_reads_and_strips(tmp_path: Path) -> None:
    path = write_secret(tmp_path, content=f"  {SECRET_VALUE}\n")

    assert entry_oauth.read_secret_file(path) == SECRET_VALUE


def test_read_secret_file_refuses_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as raised:
        entry_oauth.read_secret_file(tmp_path / "does-not-exist")

    assert SECRET_VALUE not in str(raised.value)


def test_read_secret_file_refuses_a_directory(tmp_path: Path) -> None:
    directory = tmp_path / "a-directory"
    directory.mkdir()

    with pytest.raises(ToolError):
        entry_oauth.read_secret_file(directory)


@posix_only
def test_read_secret_file_refuses_a_world_readable_file(tmp_path: Path) -> None:
    path = write_secret(tmp_path, mode=0o644)

    with pytest.raises(ToolError) as raised:
        entry_oauth.read_secret_file(path)

    assert SECRET_VALUE not in str(raised.value)


@posix_only
def test_read_secret_file_refuses_a_group_writable_file(tmp_path: Path) -> None:
    path = write_secret(tmp_path, mode=0o620)

    with pytest.raises(ToolError) as raised:
        entry_oauth.read_secret_file(path)

    assert SECRET_VALUE not in str(raised.value)


def test_read_secret_file_refuses_an_empty_file(tmp_path: Path) -> None:
    path = write_secret(tmp_path, content="")

    with pytest.raises(ToolError):
        entry_oauth.read_secret_file(path)


def test_read_secret_file_refuses_an_empty_after_strip_file(tmp_path: Path) -> None:
    path = write_secret(tmp_path, content="   \n\t  ")

    with pytest.raises(ToolError):
        entry_oauth.read_secret_file(path)


def test_read_secret_file_refuses_an_oversized_file(tmp_path: Path) -> None:
    path = write_secret(tmp_path, content="a" * 4097)

    with pytest.raises(ToolError) as raised:
        entry_oauth.read_secret_file(path)

    assert "a" * 100 not in str(raised.value)


def test_read_secret_file_accepts_a_file_at_the_byte_limit(tmp_path: Path) -> None:
    path = write_secret(tmp_path, content="a" * 4096)

    assert entry_oauth.read_secret_file(path) == "a" * 4096


def test_read_secret_file_refuses_non_utf8_content(tmp_path: Path) -> None:
    path = write_secret(tmp_path, content=b"\xff\xfe\x00\x01")

    with pytest.raises(ToolError):
        entry_oauth.read_secret_file(path)


@posix_only
def test_read_secret_file_accepts_0640(tmp_path: Path) -> None:
    path = write_secret(tmp_path, mode=0o640)

    assert entry_oauth.read_secret_file(path) == SECRET_VALUE


@posix_only
def test_read_secret_file_accepts_0600(tmp_path: Path) -> None:
    path = write_secret(tmp_path, mode=0o600)

    assert entry_oauth.read_secret_file(path) == SECRET_VALUE


def test_a_configured_secret_ends_up_in_settings_and_never_in_its_repr(tmp_path: Path) -> None:
    secret_file = write_secret(tmp_path)
    env = base_env(tmp_path, **{config.ENV_OIDC_CLIENT_SECRET_FILE: str(secret_file)})

    settings = entry_oauth.load_settings(env)

    assert settings.oidc.client_secret == SECRET_VALUE
    assert SECRET_VALUE not in repr(settings)
    assert SECRET_VALUE not in repr(settings.oidc)


# --- build_oauth_app ------------------------------------------------------------------


def make_app(tmp_path: Path, **overrides: str):
    env = base_env(tmp_path, **overrides)
    return entry_oauth.build_oauth_app(env), env


def test_mcp_without_auth_is_401_with_a_resource_metadata_pointer(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post(
            "/mcp", json={}, headers={"Accept": "application/json, text/event-stream"}
        )

    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert f'resource_metadata="{PUBLIC_URL}{PRM_SUFFIX}"' in challenge


def test_mcp_with_a_basic_header_is_401(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post(
            "/mcp",
            json={},
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": "Basic d2hhdGV2ZXI6c2VjcmV0",
            },
        )

    assert response.status_code == 401


def test_mcp_with_an_unknown_bearer_is_401(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post(
            "/mcp",
            json={},
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer not-a-real-token",
            },
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [PRM_SUFFIX, AS_METADATA_SUFFIX],
)
def test_discovery_documents_are_served(tmp_path: Path, path: str) -> None:
    app, _ = make_app(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.get(path)

    assert response.status_code == 200, path


def test_oidc_and_consent_routes_exist(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        start = client.post(OIDC_START_PATH, data={}, follow_redirects=False)
        callback = client.get(OIDC_CALLBACK_PATH, follow_redirects=False)
        consent = client.get(CONSENT_PATH, follow_redirects=False)

    assert start.status_code != 404
    assert callback.status_code != 404
    assert consent.status_code != 404


@pytest.mark.parametrize(("method", "path"), EXAPP_ONLY_PATHS)
def test_exapp_only_routes_are_absent(tmp_path: Path, method: str, path: str) -> None:
    app, _ = make_app(tmp_path)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.request(method, path)

    assert response.status_code == 404, path


def test_an_oversized_body_to_token_is_413_with_a_content_length(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    body = b"a" * (entry_oauth.MAX_BROWSER_BODY_BYTES + 1)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post(
            "/token",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 413


def test_an_oversized_chunked_body_to_token_is_cut_off(tmp_path: Path) -> None:
    """A chunked body past the limit ends as 413, even on a route that parses a form."""
    app, _ = make_app(tmp_path)
    chunk = b"a" * 4096
    chunks_needed = entry_oauth.MAX_BROWSER_BODY_BYTES // len(chunk) + 2

    def body_generator():
        for _ in range(chunks_needed):
            yield chunk

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post(
            "/token",
            content=body_generator(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


# --- BodyLimit directly ------------------------------------------------------------------


async def _echo_app(scope, receive, send) -> None:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


def test_body_limit_passes_a_small_body_through_unchanged(tmp_path: Path) -> None:
    from starlette.applications import Starlette
    from starlette.routing import Route

    async def handler(request):
        from starlette.responses import Response

        data = await request.body()
        return Response(content=data)

    app = Starlette(routes=[Route("/echo", handler, methods=["POST"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = entry_oauth.BodyLimit(route.app, entry_oauth.MAX_BROWSER_BODY_BYTES)

    with TestClient(app) as client:
        response = client.post("/echo", content=b"small body")

    assert response.status_code == 200
    assert response.content == b"small body"


def test_body_limit_refuses_an_oversized_chunked_body(tmp_path: Path) -> None:
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route

    async def handler(request):
        data = await request.body()
        return Response(content=data)

    app = Starlette(routes=[Route("/echo", handler, methods=["POST"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = entry_oauth.BodyLimit(route.app, entry_oauth.MAX_BROWSER_BODY_BYTES)

    chunk = b"a" * 4096
    chunks_needed = entry_oauth.MAX_BROWSER_BODY_BYTES // len(chunk) + 2

    def body_generator():
        for _ in range(chunks_needed):
            yield chunk

    with TestClient(app) as client:
        response = client.post("/echo", content=body_generator())

    assert response.status_code == 413


# --- select_mode --------------------------------------------------------------------------


def test_select_mode_returns_oauth() -> None:
    env = {config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH}

    assert config.select_mode(env, headers={}) == "oauth"


def test_select_mode_exapp_still_wins_over_oauth() -> None:
    env = {
        config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH,
        config.ENV_APP_ID: "mcp_connector",
        config.ENV_APP_SECRET: "app-secret",
    }

    assert config.select_mode(env, headers={}) == "exapp"


# --- main() -------------------------------------------------------------------------------


ALL_RELEVANT_VARS = (
    config.ENV_URL,
    config.ENV_AUTH_MODE,
    config.ENV_PUBLIC_URL,
    config.ENV_OAUTH_STORAGE_DIR,
    config.ENV_OAUTH_DATA_KEY_FILE,
    config.ENV_OIDC_ISSUER,
    config.ENV_OIDC_CLIENT_ID,
    config.ENV_OIDC_CLIENT_SECRET_FILE,
    config.ENV_OIDC_PROVIDER_ID,
    config.ENV_OIDC_MAPPING,
    config.ENV_OIDC_ALGORITHMS,
    config.ENV_STATIC_BEARER,
    config.ENV_APP_PASSWORD,
    config.ENV_USER,
    config.ENV_APP_ID,
    config.ENV_APP_SECRET,
    config.ENV_BIND_HOST,
    config.ENV_BIND_PORT,
)


def clear_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ALL_RELEVANT_VARS:
        monkeypatch.delenv(name, raising=False)


def apply_environment(monkeypatch: pytest.MonkeyPatch, env: Mapping[str, str]) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def never_run(*args: object, **kwargs: object) -> None:
    raise AssertionError("uvicorn.run must not be called")


def test_main_with_a_bad_environment_exits_2_and_never_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_environment(monkeypatch)
    monkeypatch.setattr(entry_oauth.uvicorn, "run", never_run)

    with pytest.raises(SystemExit) as raised:
        entry_oauth.main()

    assert raised.value.code == 2


def test_main_with_a_bad_bind_port_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_environment(monkeypatch)
    apply_environment(monkeypatch, base_env(tmp_path))
    monkeypatch.setenv(config.ENV_BIND_PORT, "not-a-port")
    monkeypatch.setattr(entry_oauth.uvicorn, "run", never_run)

    with pytest.raises(SystemExit) as raised:
        entry_oauth.main()

    assert raised.value.code == 2


def test_main_with_a_missing_key_file_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_environment(monkeypatch)
    env = base_env(tmp_path)
    env[config.ENV_OAUTH_DATA_KEY_FILE] = str(tmp_path / "does-not-exist")
    apply_environment(monkeypatch, env)
    monkeypatch.setattr(entry_oauth.uvicorn, "run", never_run)

    with pytest.raises(SystemExit) as raised:
        entry_oauth.main()

    assert raised.value.code == 2


def test_main_with_a_valid_environment_calls_uvicorn_run_with_the_default_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_environment(monkeypatch)
    apply_environment(monkeypatch, base_env(tmp_path))
    calls: list[dict[str, object]] = []

    def fake_run(app: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(entry_oauth.uvicorn, "run", fake_run)

    entry_oauth.main()

    assert len(calls) == 1
    assert calls[0]["host"] == entry_oauth.DEFAULT_BIND_HOST
    assert calls[0]["port"] == entry_oauth.DEFAULT_BIND_PORT
    assert calls[0]["proxy_headers"] is True


def test_main_with_a_valid_environment_calls_uvicorn_run_with_a_configured_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_environment(monkeypatch)
    env = base_env(tmp_path)
    apply_environment(monkeypatch, env)
    monkeypatch.setenv(config.ENV_BIND_HOST, "0.0.0.0")  # noqa: S104 - asserting the pass-through, not binding
    monkeypatch.setenv(config.ENV_BIND_PORT, "9999")
    calls: list[dict[str, object]] = []

    def fake_run(app: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(entry_oauth.uvicorn, "run", fake_run)

    entry_oauth.main()

    assert len(calls) == 1
    assert calls[0]["host"] == "0.0.0.0"  # noqa: S104 - asserting the pass-through, not binding
    assert calls[0]["port"] == 9999
    assert calls[0]["proxy_headers"] is True


# --- credential layer in the standalone mode ---------------------------------------------


class _Context:
    """A tool context with request headers and, optionally, a verified OAuth identity."""

    def __init__(self, identity: OAuthIdentity | None) -> None:
        self.headers = {"authorization": "Bearer something"}
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [(b"authorization", b"Bearer something")],
            }
        )
        if identity is not None:
            setattr(request.state, OAUTH_STATE_ATTR, identity)
        self.request_context = SimpleNamespace(request=request)


def _standalone_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith(("NC_MCP_", "APP_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(config.ENV_AUTH_MODE, config.AUTH_MODE_OAUTH)
    monkeypatch.setenv(config.ENV_URL, "https://cloud.example.com/nextcloud")


def test_a_tool_call_uses_the_connection_and_the_configured_nextcloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _standalone_env(monkeypatch)
    identity = OAuthIdentity(
        nc_user="alice",
        app_password="app-password-of-alice",
        auth_id="auth-1",
        client_id="client-1",
        principal="a1b2",
    )

    credentials = deps.resolve_credentials(_Context(identity))

    assert credentials.base_url == "https://cloud.example.com/nextcloud"
    assert credentials.user == "alice"
    assert credentials.secret == "app-password-of-alice"


@pytest.mark.parametrize("revoked", [None, True], ids=["no identity", "revoked"])
def test_a_tool_call_without_a_live_connection_is_refused(
    monkeypatch: pytest.MonkeyPatch, revoked: bool | None
) -> None:
    _standalone_env(monkeypatch)
    identity = (
        None
        if revoked is None
        else OAuthIdentity(
            nc_user="alice",
            app_password="x",
            auth_id="auth-1",
            client_id="client-1",
            principal="a1b2",
            revoked=True,
        )
    )

    with pytest.raises(deps.MCPError):
        deps.resolve_credentials(_Context(identity))


def test_the_health_probe_answers_without_authentication(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert set(response.json()) == {"status", "version"}


# --- the host the browser pages name --------------------------------------------------------


def test_standalone_pages_name_the_nextcloud_as_the_sign_in_host() -> None:
    env = {
        config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH,
        config.ENV_URL: "https://cloud.example.com/nextcloud",
        config.ENV_PUBLIC_URL: PUBLIC_URL,
    }
    assert config.sign_in_host(env) == "cloud.example.com"


def test_the_exapp_keeps_naming_its_public_host() -> None:
    env = {
        config.ENV_URL: "https://elsewhere.example.com",
        config.ENV_PUBLIC_URL: "https://cloud.example.com/exapps/mcp_connector",
    }
    assert config.sign_in_host(env) == "cloud.example.com"


def test_the_sign_in_and_consent_texts_name_the_nextcloud() -> None:
    env = {
        config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH,
        config.ENV_URL: "https://cloud.example.com",
        config.ENV_PUBLIC_URL: PUBLIC_URL,
    }
    handoff = ui_consent.handoff_page(
        "ChatGPT", "https://cloud.example.com/login/v2/flow/abc", "flow-1", env=env
    )
    consent = ui_consent.consent_page(
        "ChatGPT",
        "client-1",
        "https://client.example/cb",
        "alice",
        "flow-1",
        "confirm",
        unverified=True,
        env=env,
    )
    for page in (handoff, consent):
        text = bytes(page.body).decode()
        assert "cloud.example.com" in text
        # The header bar still names this app's own address, and nothing else does.
        assert text.count("mcp.example.com") == 1


def test_an_outbound_link_button_keeps_its_horizontal_padding() -> None:
    """``.action a`` resets the padding; the button look must win over it (seen live)."""
    from mcp_connector.exapp.ui import layout

    assert ".action .btn-link," in layout.STYLESHEET


def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", path, "1.1", 400),
        None,
    )


def test_the_access_log_never_carries_the_callback_code() -> None:
    record = _access_record("/oidc/callback?state=abc&code=SECRET")
    assert entry_oauth.RedactCallbackQuery().filter(record)
    line = record.getMessage()
    assert "SECRET" not in line
    assert "state=" not in line
    assert "/oidc/callback?[redacted]" in line


@pytest.mark.parametrize(
    "path", ["/oidc/callback", "/.well-known/oauth-authorization-server?x=1", "/oidc/callbackx?a=1"]
)
def test_other_access_log_lines_stay_as_they_are(path: str) -> None:
    record = _access_record(path)
    entry_oauth.RedactCallbackQuery().filter(record)
    assert path in record.getMessage()


def test_the_redaction_is_installed_once() -> None:
    access = logging.getLogger("uvicorn.access")
    entry_oauth.redact_access_log()
    entry_oauth.redact_access_log()
    assert sum(isinstance(f, entry_oauth.RedactCallbackQuery) for f in access.filters) == 1


def test_no_openid_configuration_on_a_host_of_its_own(tmp_path: Path) -> None:
    """Not an OpenID provider: without a path prefix the RFC 8414 path is enough."""
    app, _ = make_app(tmp_path)
    with TestClient(app, base_url=PUBLIC_URL) as client:
        assert client.get(OPENID_CONFIGURATION_SUFFIX).status_code == 404
        assert client.get("/.well-known/oauth-authorization-server").status_code == 200


def test_the_openid_variant_stays_under_a_path_prefix(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, **{config.ENV_PUBLIC_URL: f"{PUBLIC_URL}/connector"})
    paths = {getattr(route, "path", "") for route in app.router.routes}
    assert OPENID_CONFIGURATION_SUFFIX in paths


# --- the client address the throttle counts ------------------------------------------------


def _request_with(forwarded: str | None) -> Request:
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/authorize",
            "query_string": b"",
            "headers": headers,
            "client": ("203.0.113.9", 1234),
        }
    )


def test_the_standalone_mode_ignores_a_forwarded_address_by_default() -> None:
    env = {config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH}
    assert config.trust_forwarded_for(env) is False
    assert throttle_module.source_of(_request_with("198.51.100.7"), trust_forwarded=False) == (
        "203.0.113.9"
    )


def test_the_exapp_keeps_reading_the_forwarded_address() -> None:
    assert config.trust_forwarded_for({}) is True
    assert throttle_module.source_of(_request_with("198.51.100.7")) == "198.51.100.7"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("0", False), ("off", False), ("?", False)],
)
def test_the_switch_decides_in_the_standalone_mode(value: str, expected: bool) -> None:
    env = {config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH, config.ENV_TRUST_FORWARDED_FOR: value}
    assert config.trust_forwarded_for(env) is expected


def test_an_exapp_can_be_told_not_to_read_the_header() -> None:
    assert config.trust_forwarded_for({config.ENV_TRUST_FORWARDED_FOR: "0"}) is False


def test_a_forged_address_does_not_split_the_counter_in_standalone_mode(tmp_path: Path) -> None:
    """Every refusal counts against the same source, whatever the caller writes."""
    app, _ = make_app(tmp_path)
    with TestClient(app, base_url=PUBLIC_URL) as client:
        statuses = [
            client.get(
                f"{OIDC_CALLBACK_PATH}?state={'x' * 43}&code=abc",
                headers={"x-forwarded-for": f"198.51.100.{index}"},
            ).status_code
            for index in range(throttle_module.FAILURE_LIMIT + 1)
        ]
    assert statuses[-1] == 429


# --- the token exchange path refuses a half configuration at startup (CONF-01) ------------

#: Values distinctive enough that a test can prove no log line of the run repeats them.
EXCHANGE_ISSUER = "https://idp.secret-tenant.example.org/realms/f13"
EXCHANGE_AZP = "an-orchestrator-of-secret-tenant"
EXCHANGE_CLAIM = "a_claim_of_secret_tenant"
EXCHANGE_ENV = {
    config.ENV_EXCHANGE_ENABLED: "1",
    config.ENV_EXCHANGE_ISSUER: EXCHANGE_ISSUER,
    config.ENV_EXCHANGE_AZP: EXCHANGE_AZP,
    config.ENV_EXCHANGE_ACCOUNT_CLAIM: EXCHANGE_CLAIM,
}


def test_an_armed_exchange_path_without_the_issuer_stops_the_settings(tmp_path: Path) -> None:
    """T-22-01 in the deployment without AppAPI: the same refusal as in the ExApp."""
    with pytest.raises(ToolError) as excinfo:
        entry_oauth.load_settings(base_env(tmp_path, **{config.ENV_EXCHANGE_ENABLED: "1"}))

    assert config.ENV_EXCHANGE_ISSUER in excinfo.value.message


def test_a_configured_exchange_path_without_the_switch_stops_the_settings(tmp_path: Path) -> None:
    """T-22-02: a namespace that was filled in and never armed is not served here either."""
    with pytest.raises(ToolError) as excinfo:
        entry_oauth.load_settings(
            base_env(tmp_path, **{config.ENV_EXCHANGE_ISSUER: EXCHANGE_ISSUER})
        )

    assert config.ENV_EXCHANGE_ENABLED in excinfo.value.message


def test_without_the_namespace_the_settings_say_nothing_about_the_exchange_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="mcp_connector.entry_oauth"):
        settings = entry_oauth.load_settings(base_env(tmp_path))

    assert settings.public_url == PUBLIC_URL
    assert not [record for record in caplog.records if "exchange" in record.getMessage().lower()]


def announcements_in(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Every line of a run that speaks about the exchange path, whoever wrote it."""
    return [record for record in caplog.records if "exchange" in record.getMessage().lower()]


def test_a_complete_exchange_configuration_is_announced_once_and_without_a_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """WR-01: one line per start, counted over the whole way ``main`` takes.

    ``main`` calls ``load_settings`` and then ``build_oauth_app(settings=...)``, and both
    used to announce, so the one production path of this mode wrote the line twice while
    two tests measured one call each and both stayed green. The count here spans both calls
    over one armed environment, which is the combination ``main`` actually runs.
    """
    env = base_env(tmp_path, **EXCHANGE_ENV)

    with caplog.at_level(logging.INFO, logger="mcp_connector.entry_oauth"):
        settings = entry_oauth.load_settings(env)
        entry_oauth.build_oauth_app(env, settings=settings)

    assert len(announcements_in(caplog)) == 1
    everything = " ".join(record.getMessage() for record in caplog.records)
    assert "secret-tenant" not in everything


def test_reading_the_settings_alone_announces_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The other half of WR-01: the line belongs to the built application, and to one place.

    Reading a configuration is not arming a path; hanging the chain in is. Announcing here
    as well is what made the count of the line above two.
    """
    with caplog.at_level(logging.INFO, logger="mcp_connector.entry_oauth"):
        settings = entry_oauth.load_settings(base_env(tmp_path, **EXCHANGE_ENV))

    assert settings.exchange is not None, "the configuration was read, only not announced"
    assert announcements_in(caplog) == []


def test_the_application_built_from_the_environment_alone_announces_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The third way in: no settings in hand, so ``build_oauth_app`` reads them itself."""
    with caplog.at_level(logging.INFO, logger="mcp_connector.entry_oauth"):
        entry_oauth.build_oauth_app(base_env(tmp_path, **EXCHANGE_ENV))

    assert len(announcements_in(caplog)) == 1


def test_the_application_refuses_a_half_configuration_with_settings_in_hand(
    tmp_path: Path,
) -> None:
    """``build_oauth_app`` is callable without ``load_settings``, so it reads the namespace
    itself: a caller that hands validated settings in must not thereby skip the check."""
    env = base_env(tmp_path)
    settings = entry_oauth.load_settings(env)

    with pytest.raises(ToolError) as excinfo:
        entry_oauth.build_oauth_app({**env, config.ENV_EXCHANGE_ENABLED: "1"}, settings=settings)

    assert config.ENV_EXCHANGE_ISSUER in excinfo.value.message


def test_armed_settings_build_an_armed_application_over_a_clean_environment(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """WR-02: the field the settings carry decides, and a second read never disarms it.

    ``build_oauth_app`` read the namespace again and overwrote the field with the answer,
    so a caller who validated an armed configuration from one mapping and built the
    application against another got a boundary without a chain: armed in hand, unarmed in
    service, no refusal and no line. The environment handed in here is the factory state,
    and the settings are the armed ones.
    """
    env = base_env(tmp_path)
    settings = entry_oauth.load_settings({**env, **EXCHANGE_ENV})
    assert settings.exchange is not None

    with caplog.at_level(logging.INFO, logger="mcp_connector.entry_oauth"):
        guard = boundary_of(entry_oauth.build_oauth_app(env, settings=settings))

    assert isinstance(guard._token_verifier, chain.ChainedVerifier)
    assert len(announcements_in(caplog)) == 1
    assert "secret-tenant" not in " ".join(record.getMessage() for record in caplog.records)


def test_the_second_read_still_refuses_a_half_configuration_next_to_armed_settings(
    tmp_path: Path,
) -> None:
    """The reason the second read stays: it is the refusal, not the source of the answer."""
    env = base_env(tmp_path)
    settings = entry_oauth.load_settings({**env, **EXCHANGE_ENV})

    with pytest.raises(ToolError) as excinfo:
        entry_oauth.build_oauth_app(
            {**env, config.ENV_EXCHANGE_ISSUER: EXCHANGE_ISSUER}, settings=settings
        )

    assert config.ENV_EXCHANGE_ENABLED in excinfo.value.message


def test_the_application_is_announced_once_when_the_settings_are_handed_in(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    env = base_env(tmp_path)
    settings = entry_oauth.load_settings(env)

    with caplog.at_level(logging.INFO, logger="mcp_connector.entry_oauth"):
        entry_oauth.build_oauth_app({**env, **EXCHANGE_ENV}, settings=settings)

    assert len(announcements_in(caplog)) == 1
    assert "secret-tenant" not in " ".join(record.getMessage() for record in caplog.records)


# --- the chain at the transport boundary of the standalone deployment (EXCH-04) -----------


def revocations_taken(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every callable ``on_revocation`` is handed while an application is built.

    Recorded at the hand over, because the finished application never shows it again. What
    is recorded is a bound method, so ``__self__`` names the object a revocation reaches.
    """
    taken: list[Any] = []
    original = NextcloudOAuthProvider.on_revocation

    def record(self: NextcloudOAuthProvider, invalidate: Callable[[], None]) -> None:
        taken.append(invalidate)
        original(self, invalidate)

    monkeypatch.setattr(NextcloudOAuthProvider, "on_revocation", record)
    return taken


def boundary_of(app: Starlette) -> RequireOAuthBearer:
    """The transport boundary of ``/mcp``, from under the throttle when there is one.

    Since EXCH-05 an armed exchange path puts a throttle around the boundary, and it has
    to sit outside it to see the 401 the boundary writes.
    """
    guards = [
        route.app
        for route in app.router.routes
        if isinstance(route, Route) and route.path == entry_oauth.MCP_PATH
    ]
    assert len(guards) == 1
    guard = guards[0]
    while isinstance(guard, throttle_module.Throttled):
        guard = guard._app
    assert isinstance(guard, RequireOAuthBearer)
    return guard


def test_without_the_namespace_the_boundary_holds_the_store_verifier_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The off state of the standalone deployment, measured with ``is`` as in the ExApp."""
    taken = revocations_taken(monkeypatch)

    guard = boundary_of(entry_oauth.build_oauth_app(base_env(tmp_path)))

    assert isinstance(guard._token_verifier, StoreTokenVerifier)
    assert len(taken) == 1
    assert taken[0].__self__ is guard._token_verifier


def test_the_armed_path_hangs_the_chain_and_gives_it_the_revocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taken = revocations_taken(monkeypatch)

    guard = boundary_of(entry_oauth.build_oauth_app(base_env(tmp_path, **EXCHANGE_ENV)))

    assert isinstance(guard._token_verifier, chain.ChainedVerifier)
    assert len(taken) == 1
    assert taken[0].__self__ is guard._token_verifier


def test_the_chain_is_hung_in_when_the_settings_are_handed_in_as_well(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second call path into the application reads the same namespace and wires the same."""
    env = base_env(tmp_path, **EXCHANGE_ENV)
    settings = entry_oauth.load_settings(env)
    taken = revocations_taken(monkeypatch)

    guard = boundary_of(entry_oauth.build_oauth_app(env, settings=settings))

    assert isinstance(guard._token_verifier, chain.ChainedVerifier)
    assert taken[0].__self__ is guard._token_verifier


# --- the account source of the standalone deployment (CRED-02) -----------------------------


def test_the_armed_path_hands_the_bound_account_source_into_the_chain(tmp_path: Path) -> None:
    """The armed application builds the one account source of this mode, and it builds it
    from the very store opener the verifier and the provider use: a second opener would be
    a second view on the same revocation."""
    guard = boundary_of(entry_oauth.build_oauth_app(base_env(tmp_path, **EXCHANGE_ENV)))
    verifier = guard._token_verifier

    assert isinstance(verifier, chain.ChainedVerifier)
    accounts = verifier._accounts
    assert isinstance(accounts, exchange_binding.BoundAccounts)
    store_branch = verifier._store
    assert isinstance(store_branch, StoreTokenVerifier)
    assert accounts._store is store_branch._store


def test_without_the_namespace_no_account_source_exists_at_the_boundary(tmp_path: Path) -> None:
    """The off state is the same structure as before this plan: the store verifier itself,
    and therefore no chain and no account source anywhere behind ``/mcp``."""
    guard = boundary_of(entry_oauth.build_oauth_app(base_env(tmp_path)))

    assert isinstance(guard._token_verifier, StoreTokenVerifier)
    assert not isinstance(guard._token_verifier, chain.ChainedVerifier)


# --- the refusal writer, deliberately absent in this mode (AUDIT-07, T-24-21) --------------


@pytest.mark.parametrize("switch", [{}, {config.ENV_AUDIT_LOG: "on"}])
def test_the_standalone_chain_notes_no_refusal_whatever_the_audit_switch_says(
    tmp_path: Path, switch: dict[str, str]
) -> None:
    """The decision of plan 24-04 for this mode, held here so it cannot happen by accident.

    The ExApp mode writes a row per refused exchange attempt. This mode does not, and that
    is decided rather than forgotten. It has no recorder, so no tool call is recorded here
    either and the switch of D-14 means nothing in this process today; it has no sweep, so
    the rows would sit out neither the retention window nor the size limit
    (``audit/record.Recorder`` carries the sweep, and ``entry_exapp._audit_startup`` is the
    other one); and it has no occ and no audit routes, so nothing could read them back.
    Wiring the writer alone would turn one switch into two different promises in two modes
    and leave behind a file that grows on a path a stranger drives and that nobody sweeps.

    ``config.ENV_AUDIT_LOG: "on"`` is parametrised in on purpose: the absence has to hold
    for the environment an operator would expect it to change something in.
    """
    guard = boundary_of(entry_oauth.build_oauth_app(base_env(tmp_path, **EXCHANGE_ENV, **switch)))
    verifier = guard._token_verifier

    assert isinstance(verifier, chain.ChainedVerifier)
    assert verifier._refusals is None


# --- the enrollment page of the exchange binding hangs only while the path is armed --------


def test_the_armed_application_attaches_the_enrollment_page(tmp_path: Path) -> None:
    """Plan 23-06: the page on which a binding is set up, seen and withdrawn, wrapped in
    the same body limit as every other browser route."""
    app = entry_oauth.build_oauth_app(base_env(tmp_path, **EXCHANGE_ENV))

    enrollment = [
        route
        for route in app.router.routes
        if isinstance(route, Route) and route.path == "/exchange"
    ]

    assert len(enrollment) == 2, "one address, a GET route and a POST route"
    assert {method for route in enrollment for method in route.methods or ()} >= {"GET", "POST"}
    assert all(isinstance(route.app, entry_oauth.BodyLimit) for route in enrollment)


def test_the_disarmed_application_has_no_exchange_address(tmp_path: Path) -> None:
    """In the off state the address does not exist at all rather than answering emptily:
    an address that is not there is the smallest attack surface, and the factory state is
    the same structure as before this milestone."""
    app = entry_oauth.build_oauth_app(base_env(tmp_path))

    paths = [route.path for route in app.router.routes if isinstance(route, Route)]

    assert "/exchange" not in paths

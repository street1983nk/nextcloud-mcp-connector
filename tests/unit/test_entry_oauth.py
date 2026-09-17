"""Unit tests for ``entry_oauth``: settings, secret file, the standalone application."""

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_connector import config, deps, entry_oauth
from mcp_connector.errors import ToolError
from mcp_connector.exapp.ui import consent as ui_consent
from mcp_connector.oauth import oidc
from mcp_connector.oauth.metadata import (
    AS_METADATA_SUFFIX,
    OPENID_CONFIGURATION_SUFFIX,
    PRM_SUFFIX,
)
from mcp_connector.oauth.oidc_routes import OIDC_CALLBACK_PATH, OIDC_START_PATH
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity

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
    [PRM_SUFFIX, OPENID_CONFIGURATION_SUFFIX, AS_METADATA_SUFFIX],
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

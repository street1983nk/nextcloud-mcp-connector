"""Store directory and data key as explicit deployment inputs (standalone OAuth, slice 3).

The ExApp keeps its composition: AppAPI volume plus the key stored in Nextcloud. Every other
deployment hands both inputs to :func:`store.explicit_store_opener`, validates its directory
with :func:`config.storage_directory` and reads its key with :func:`crypto.file_key`. None of
these paths may reach the development fallback or create a key.
"""

import inspect
import os
import stat
from pathlib import Path

import pytest

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.oauth import connect, crypto, store
from mcp_connector.oauth import provider as provider_module

KEY = bytes(range(32))
KEY_HEX = KEY.hex()
VARIABLE = "EXAMPLE_STORE_DIR"
HINT = "Mount a writable volume."


# --- explicit_store_opener -----------------------------------------------------------------


@pytest.mark.anyio
async def test_the_opener_uses_exactly_the_given_directory_and_key(tmp_path: Path) -> None:
    calls: list[str] = []

    async def key() -> bytes:
        calls.append("key")
        return KEY

    def directory() -> Path:
        calls.append("directory")
        return tmp_path

    opener = store.explicit_store_opener(directory=directory, key=key)
    first = await opener()
    second = await opener()

    assert first is second, "one store per application"
    assert first.path == tmp_path / store.STORE_FILENAME
    assert calls == ["key", "directory"], "each input is asked once, the key first"
    assert (tmp_path / store.STORE_FILENAME).is_file()


@pytest.mark.anyio
async def test_a_failing_key_creates_nothing(tmp_path: Path) -> None:
    """The key is the step that fails with a named error, so it runs before any directory
    is touched and a failed start leaves no empty store behind."""
    touched: list[Path] = []

    async def key() -> bytes:
        raise ToolError(message="no key", hint="mount it")

    def directory() -> Path:
        touched.append(tmp_path)
        return tmp_path

    opener = store.explicit_store_opener(directory=directory, key=key)
    with pytest.raises(ToolError):
        await opener()

    assert touched == []
    assert os.listdir(tmp_path) == []


@pytest.mark.anyio
async def test_a_failed_open_is_retried_on_the_next_request(tmp_path: Path) -> None:
    """Nothing is cached until a store exists, so a volume mounted late is picked up."""
    attempts: list[int] = []

    async def key() -> bytes:
        attempts.append(1)
        if len(attempts) == 1:
            raise ToolError(message="not yet", hint="wait")
        return KEY

    opener = store.explicit_store_opener(directory=lambda: tmp_path, key=key)
    with pytest.raises(ToolError):
        await opener()
    opened = await opener()

    assert opened.path.parent == tmp_path
    assert len(attempts) == 2


@pytest.mark.anyio
async def test_the_exapp_opener_is_the_appapi_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []
    env = {config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}

    async def data_key(passed: object = None) -> bytes:
        seen.append(("key", passed))
        return KEY

    def persistent_storage(passed: object = None) -> Path:
        seen.append(("directory", passed))
        return tmp_path

    monkeypatch.setattr(store.crypto, "data_key", data_key)
    monkeypatch.setattr(store.config, "persistent_storage", persistent_storage)

    opened = await store.store_opener(env)()

    assert opened.path == tmp_path / store.STORE_FILENAME
    assert seen == [("key", env), ("directory", env)]


@pytest.mark.parametrize(
    ("factory", "name"),
    [
        (provider_module.NextcloudOAuthProvider.__init__, "store_provider"),
        (connect.connect_routes, "store_provider"),
    ],
    ids=["provider", "onboarding"],
)
def test_no_consumer_opens_a_store_of_its_own(factory: object, name: str) -> None:
    """A default opener would pick the ExApp directory and key for any deployment."""
    parameter = inspect.signature(factory).parameters[name]  # type: ignore[arg-type]
    assert parameter.default is inspect.Parameter.empty


def test_the_consumers_do_not_import_the_exapp_opener() -> None:
    for module in (provider_module, connect):
        source = inspect.getsource(module)
        assert "store_opener(" not in source.replace("explicit_store_opener(", ""), module


# --- config.storage_directory ------------------------------------------------------------


def test_a_writable_directory_is_accepted(tmp_path: Path) -> None:
    assert config.storage_directory(f"  {tmp_path}  ", variable=VARIABLE, hint=HINT) == tmp_path


@pytest.mark.parametrize("raw", ["", "   "])
def test_an_empty_value_names_the_variable(raw: str) -> None:
    before = set(Path.cwd().iterdir())
    with pytest.raises(ToolError) as raised:
        config.storage_directory(raw, variable=VARIABLE, hint=HINT)
    assert VARIABLE in raised.value.message
    assert raised.value.hint == HINT
    assert set(Path.cwd().iterdir()) == before, "no development directory is created"


def test_a_missing_directory_is_never_created(tmp_path: Path) -> None:
    missing = tmp_path / "not-mounted"
    with pytest.raises(ToolError) as raised:
        config.storage_directory(str(missing), variable=VARIABLE, hint=HINT)
    assert VARIABLE in raised.value.message
    assert not missing.exists()


def test_a_file_is_not_a_store_directory(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ToolError):
        config.storage_directory(str(target), variable=VARIABLE, hint=HINT)


def test_an_unwritable_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "_probe_writable", lambda path: False)
    with pytest.raises(ToolError) as raised:
        config.storage_directory(str(tmp_path), variable=VARIABLE, hint=HINT)
    assert "not writable" in raised.value.message


def test_the_exapp_branch_still_uses_its_own_variable(tmp_path: Path) -> None:
    env = {
        config.ENV_APP_ID: "mcp_connector",
        config.ENV_APP_SECRET: "secret",
        config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path / "missing"),
    }
    with pytest.raises(ToolError) as raised:
        config.persistent_storage(env)
    assert config.ENV_APP_PERSISTENT_STORAGE in raised.value.message


# --- crypto.file_key ---------------------------------------------------------------------


def key_file(tmp_path: Path, content: str, mode: int = 0o600) -> Path:
    path = tmp_path / "data.key"
    path.write_text(content, encoding="ascii")
    path.chmod(mode)
    return path


@pytest.mark.parametrize("content", [KEY_HEX, f"{KEY_HEX}\n", f"  {KEY_HEX.upper()}\r\n"])
def test_a_hex_key_file_is_read(tmp_path: Path, content: str) -> None:
    assert crypto.file_key(key_file(tmp_path, content)) == KEY


@pytest.mark.parametrize("mode", [0o400, 0o440, 0o444, 0o644])
def test_read_only_modes_of_secret_mounts_are_accepted(tmp_path: Path, mode: int) -> None:
    assert crypto.file_key(key_file(tmp_path, KEY_HEX, mode)) == KEY


def test_a_symlinked_secret_is_accepted(tmp_path: Path) -> None:
    """Kubernetes mounts a secret as a symlink into a timestamped directory."""
    real = key_file(tmp_path, KEY_HEX)
    link = tmp_path / "link.key"
    link.symlink_to(real)
    assert crypto.file_key(link) == KEY


@pytest.mark.parametrize("mode", [0o620, 0o602, 0o666])
def test_a_key_file_others_can_replace_is_refused(tmp_path: Path, mode: int) -> None:
    path = key_file(tmp_path, KEY_HEX)
    os.chmod(path, mode)
    assert stat.S_IMODE(path.stat().st_mode) == mode
    with pytest.raises(ToolError) as raised:
        crypto.file_key(path)
    assert "writable" in raised.value.message


@pytest.mark.parametrize(
    "content",
    [KEY_HEX[:-2], KEY_HEX + "00", "zz" + KEY_HEX[2:], "", KEY_HEX[:32] + " " + KEY_HEX[33:]],
    ids=["short", "long", "not hex", "empty", "inner whitespace"],
)
def test_a_malformed_key_is_refused_without_echoing_it(tmp_path: Path, content: str) -> None:
    with pytest.raises(ToolError) as raised:
        crypto.file_key(key_file(tmp_path, content))
    text = f"{raised.value.message} {raised.value.hint}"
    for fragment in (KEY_HEX[:8], KEY_HEX[-8:], "zz"):
        assert fragment not in text


def test_a_missing_key_file_is_never_created(tmp_path: Path) -> None:
    missing = tmp_path / "data.key"
    with pytest.raises(ToolError) as raised:
        crypto.file_key(missing)
    assert "does not exist" in raised.value.message
    assert not missing.exists()
    assert list(tmp_path.iterdir()) == []


def test_a_directory_is_not_a_key_file(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as raised:
        crypto.file_key(tmp_path)
    assert "regular file" in raised.value.message


def test_a_binary_key_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "data.key"
    path.write_bytes(bytes(range(200, 232)))
    path.chmod(0o600)
    with pytest.raises(ToolError):
        crypto.file_key(path)

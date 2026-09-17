"""Store directory and data key as explicit deployment inputs (standalone OAuth, slice 3).

The ExApp keeps its composition: AppAPI volume plus the key stored in Nextcloud. Every other
deployment hands both inputs to :func:`store.explicit_store_opener`, validates its directory
with :func:`config.storage_directory` and reads its key with :func:`crypto.file_key`. None of
these paths may reach the development fallback or create a key.
"""

import inspect
import os
import stat
import sys
from pathlib import Path

import pytest

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.oauth import connect, crypto, store
from mcp_connector.oauth import provider as provider_module

KEY = bytes(range(32))
KEY_HEX = KEY.hex()
VARIABLE = "EXAMPLE_STORE_DIR"

#: Mode bits, links and FIFOs as these checks use them exist on POSIX only (Windows models a
#: read-only flag in the mode). The production code skips the mode checks there as well.
posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions, links and FIFOs")
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


@posix_only
@pytest.mark.parametrize("mode", [0o770, 0o757, 0o777, 0o1777])
def test_a_directory_others_can_write_into_is_refused(tmp_path: Path, mode: int) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(mode)
    with pytest.raises(ToolError) as raised:
        config.storage_directory(str(shared), variable=VARIABLE, hint=HINT)
    assert "group or by others" in raised.value.message


@posix_only
@pytest.mark.parametrize("mode", [0o700, 0o750, 0o755])
def test_a_directory_only_its_owner_can_write_into_is_accepted(tmp_path: Path, mode: int) -> None:
    private = tmp_path / "private"
    private.mkdir()
    private.chmod(mode)
    assert config.storage_directory(str(private), variable=VARIABLE, hint=HINT) == private


def test_the_exapp_volume_keeps_its_directory_rules(tmp_path: Path) -> None:
    """Unchanged ExApp behaviour: a group writable AppAPI volume is still accepted."""
    volume = tmp_path / "volume"
    volume.mkdir()
    volume.chmod(0o775)
    env = {
        config.ENV_APP_ID: "mcp_connector",
        config.ENV_APP_SECRET: "secret",
        config.ENV_APP_PERSISTENT_STORAGE: str(volume),
    }
    assert config.persistent_storage(env) == volume


@posix_only
def test_the_write_probe_never_follows_a_planted_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1 of the review: the old predictable probe truncated the file a link pointed at."""
    victim = tmp_path / "victim"
    victim.write_text("SECRET", encoding="utf-8")
    directory = tmp_path / "store"
    directory.mkdir()
    monkeypatch.setattr(config.secrets, "token_hex", lambda size: "fixed")
    (directory / f".write-probe-{os.getpid()}-fixed").symlink_to(victim)

    assert config._probe_writable(directory) is False
    assert victim.read_text(encoding="utf-8") == "SECRET"


def test_the_write_probe_name_is_not_predictable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    original = os.open

    def recording(path: object, *args: object, **kwargs: object) -> int:
        seen.append(str(path))
        return original(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(config.os, "open", recording)
    assert config._probe_writable(tmp_path)
    assert config._probe_writable(tmp_path)
    monkeypatch.undo()
    assert len(set(seen)) == 2
    assert os.listdir(tmp_path) == []


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


@posix_only
@pytest.mark.parametrize("mode", [0o400, 0o440, 0o600, 0o640])
def test_owner_and_group_read_modes_are_accepted(tmp_path: Path, mode: int) -> None:
    """Group read stays allowed: Kubernetes hands a secret to a pod through fsGroup."""
    assert crypto.file_key(key_file(tmp_path, KEY_HEX, mode)) == KEY


@posix_only
def test_a_symlinked_secret_is_accepted(tmp_path: Path) -> None:
    """Kubernetes mounts a secret as a symlink into a timestamped directory."""
    real = key_file(tmp_path, KEY_HEX)
    link = tmp_path / "link.key"
    link.symlink_to(real)
    assert crypto.file_key(link) == KEY


@posix_only
@pytest.mark.parametrize("mode", [0o620, 0o602, 0o666, 0o644, 0o444, 0o604, 0o401, 0o660])
def test_a_key_file_others_can_read_or_replace_is_refused(tmp_path: Path, mode: int) -> None:
    path = key_file(tmp_path, KEY_HEX)
    os.chmod(path, mode)
    assert stat.S_IMODE(path.stat().st_mode) == mode
    with pytest.raises(ToolError) as raised:
        crypto.file_key(path)
    assert "too open" in raised.value.message


@posix_only
def test_the_checked_file_is_the_file_that_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link swapped between the check and the read changes nothing: one descriptor."""
    private = key_file(tmp_path, KEY_HEX)
    public = tmp_path / "public.key"
    public.write_text("ab" * 32, encoding="ascii")
    public.chmod(0o644)
    link = tmp_path / "mounted.key"
    link.symlink_to(private)
    original_fstat = crypto.os.fstat

    def swap_then_stat(descriptor: int) -> os.stat_result:
        link.unlink()
        link.symlink_to(public)
        return original_fstat(descriptor)

    monkeypatch.setattr(crypto.os, "fstat", swap_then_stat)

    assert crypto.file_key(link) == KEY


def test_an_oversized_key_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as raised:
        crypto.file_key(key_file(tmp_path, KEY_HEX + " " * 5000))
    assert "wrong length" in raised.value.message


@posix_only
def test_a_fifo_does_not_block_the_start(tmp_path: Path) -> None:
    if sys.platform == "win32":
        # Also for the type checker: ``os.mkfifo`` does not exist on Windows.
        pytest.skip("no FIFOs on Windows")
    fifo = tmp_path / "data.key"
    os.mkfifo(fifo, 0o600)
    with pytest.raises(ToolError) as raised:
        crypto.file_key(fifo)
    assert "regular file" in raised.value.message


@pytest.mark.parametrize(
    "content",
    [
        KEY_HEX[:-2],
        KEY_HEX + "00",
        "zz" + KEY_HEX[2:],
        "",
        KEY_HEX[:32] + " " + KEY_HEX[33:],
        KEY_HEX[:30] + "  " + KEY_HEX[32:],
        KEY_HEX[:62] + "\t\n",
    ],
    ids=["short", "long", "not hex", "empty", "inner blank", "blank pair", "short plus blanks"],
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


@posix_only
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

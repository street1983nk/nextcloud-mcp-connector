"""Unit tests for environment parsing (D-11).

A missing variable must name itself in the error text: the developer reads that message
in a client log where nothing else explains what went wrong.
"""

import logging
import typing
from pathlib import Path

import pytest

from mcp_connector import config
from mcp_connector.audit import store as audit_store
from mcp_connector.errors import ToolError
from mcp_connector.exapp import config_values
from mcp_connector.oauth import registry

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(nc_env: dict[str, str]) -> dict[str, str]:
    return {
        config.ENV_URL: nc_env["base_url"],
        config.ENV_USER: nc_env["user"],
        config.ENV_APP_PASSWORD: nc_env["secret"],
    }


def test_loads_credentials_from_env(nc_env: dict[str, str]) -> None:
    creds = config.load_stdio_credentials(_env(nc_env))
    assert creds.base_url == "http://nc.test"
    assert creds.user == "alice"
    assert creds.secret == "app-password-test"


@pytest.mark.parametrize(
    "missing",
    ["NC_MCP_URL", "NC_MCP_USER", "NC_MCP_APP_PASSWORD"],
)
def test_missing_variable_names_itself(nc_env: dict[str, str], missing: str) -> None:
    env = _env(nc_env)
    del env[missing]
    with pytest.raises(ToolError) as excinfo:
        config.load_stdio_credentials(env)
    assert missing in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.parametrize(
    "blank",
    ["", "   "],
)
def test_blank_variable_is_treated_as_missing(nc_env: dict[str, str], blank: str) -> None:
    env = _env(nc_env)
    env[config.ENV_APP_PASSWORD] = blank
    with pytest.raises(ToolError) as excinfo:
        config.load_stdio_credentials(env)
    assert config.ENV_APP_PASSWORD in excinfo.value.message


def test_trailing_slash_is_removed_and_subpath_is_kept() -> None:
    assert config.normalize_base_url("https://cloud.test/") == "https://cloud.test"
    assert config.normalize_base_url("https://cloud.test///") == "https://cloud.test"
    assert (
        config.normalize_base_url("https://host.test/nextcloud/") == "https://host.test/nextcloud"
    )
    assert config.normalize_base_url("  https://host.test/nc  ") == "https://host.test/nc"


def test_files_root_defaults_to_the_whole_files_area() -> None:
    assert config.files_root({}) == "/"


def test_files_root_normalizes_the_bound_directory() -> None:
    assert config.files_root({config.ENV_FILES_ROOT: " /RTC/mth/knsk/// "}) == "/RTC/mth/knsk"


@pytest.mark.parametrize(
    "raw",
    ["rtc/mth/knsk", "/rtc/../secret", r"/rtc\\mth", "/rtc\x00mth"],
)
def test_invalid_files_root_is_rejected(raw: str) -> None:
    with pytest.raises(ToolError) as excinfo:
        config.normalize_files_root(raw)
    assert config.ENV_FILES_ROOT in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.parametrize(
    "raw",
    ["cloud.test", "ftp://cloud.test", "file:///etc/passwd", "", "   ", "https://"],
)
def test_invalid_base_url_is_rejected(raw: str) -> None:
    with pytest.raises(ToolError) as excinfo:
        config.normalize_base_url(raw)
    assert excinfo.value.hint


@pytest.mark.parametrize(
    "raw",
    [
        "https://admin:hunter2@cloud.test",
        "https://admin@cloud.test",
        "http://:hunter2@cloud.test/nextcloud",
    ],
    ids=["user and password", "user only", "password only"],
)
def test_credentials_in_the_base_url_are_rejected_without_repeating_them(raw: str) -> None:
    """IN-04: the value passed the scheme and netloc checks and landed in
    settings.base_url, which exapp/status.py writes into two logger.error lines in full."""
    with pytest.raises(ToolError) as excinfo:
        config.normalize_base_url(raw)

    assert "credentials" in excinfo.value.message
    assert "hunter2" not in excinfo.value.message
    assert "hunter2" not in excinfo.value.hint


def test_redirect_hint_is_available_for_client_errors() -> None:
    """The 3xx path in the client layer reuses one wording, defined here."""
    assert "redirect" in config.REDIRECT_HINT.lower()


def test_http_mode_variable_names_are_declared_but_unused() -> None:
    """Plan 04 evaluates these; plan 02 only reserves the names (no silent defaults)."""
    assert config.ENV_ALLOWED_HOSTS == "NC_MCP_ALLOWED_HOSTS"
    assert config.ENV_STATIC_BEARER == "NC_MCP_STATIC_BEARER"


# --- the ExApp mode (EXAPP-01) ----------------------------------------------------

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"


def _exapp_env() -> dict[str, str]:
    return {
        config.ENV_APP_ID: APP_ID,
        config.ENV_APP_SECRET: APP_SECRET,
        config.ENV_APP_VERSION: APP_VERSION,
        config.ENV_AA_VERSION: "34.0.3",
        config.ENV_NEXTCLOUD_URL: "http://nc.test/",
    }


def test_appapi_variable_names_keep_the_names_appapi_dictates() -> None:
    """These four carry no NC_MCP_ prefix on purpose: the deploy daemon sets them."""
    assert config.ENV_APP_ID == "APP_ID"
    assert config.ENV_APP_SECRET == "APP_SECRET"
    assert config.ENV_APP_VERSION == "APP_VERSION"
    assert config.ENV_NEXTCLOUD_URL == "NEXTCLOUD_URL"


def test_exapp_configured_needs_both_id_and_secret() -> None:
    assert config.exapp_configured(_exapp_env()) is True
    assert config.exapp_configured({config.ENV_APP_ID: APP_ID}) is False
    assert config.exapp_configured({config.ENV_APP_SECRET: APP_SECRET}) is False
    assert config.exapp_configured({}) is False


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_appapi_variable_is_treated_as_unset(blank: str) -> None:
    env = _exapp_env()
    env[config.ENV_APP_SECRET] = blank
    assert config.exapp_configured(env) is False


def test_exapp_settings_reads_the_deploy_environment() -> None:
    settings = config.exapp_settings(_exapp_env())
    assert settings.app_id == APP_ID
    assert settings.app_secret == APP_SECRET
    assert settings.app_version == APP_VERSION
    assert settings.aa_version == "34.0.3"
    assert settings.base_url == "http://nc.test", "the trailing slash is normalised away"


def test_exapp_settings_falls_back_to_the_phase_one_url_variable() -> None:
    env = _exapp_env()
    del env[config.ENV_NEXTCLOUD_URL]
    env[config.ENV_URL] = "https://cloud.test/nextcloud/"
    assert config.exapp_settings(env).base_url == "https://cloud.test/nextcloud"


def test_exapp_settings_treats_a_missing_aa_version_as_empty() -> None:
    """HaRP writes a placeholder into AA-VERSION anyway, so it is never required."""
    env = _exapp_env()
    del env[config.ENV_AA_VERSION]
    assert config.exapp_settings(env).aa_version == ""


@pytest.mark.parametrize("missing", ["APP_ID", "APP_SECRET", "APP_VERSION", "NEXTCLOUD_URL"])
def test_a_missing_appapi_variable_names_itself(missing: str) -> None:
    env = _exapp_env()
    del env[missing]
    with pytest.raises(ToolError) as excinfo:
        config.exapp_settings(env)
    assert missing in excinfo.value.message
    assert excinfo.value.hint


def test_the_settings_repr_masks_the_app_secret() -> None:
    """T-02-03: the secret must not show up in a traceback or a container repr."""
    settings = config.exapp_settings(_exapp_env())
    assert APP_SECRET not in repr(settings)
    assert "***" in repr(settings)


# --- the persistent volume of the token store (AUTH-03, pitfall 12) ---------------


def test_the_store_directory_is_the_volume_appapi_mounted(tmp_path: Path) -> None:
    env = {**_exapp_env(), config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}
    assert config.persistent_storage(env) == tmp_path


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_volume_names_the_variable_in_the_exapp_mode(value: str | None) -> None:
    """T-03-15: without it every authorization dies at the next container restart."""
    env = _exapp_env()
    if value is not None:
        env[config.ENV_APP_PERSISTENT_STORAGE] = value

    with pytest.raises(ToolError) as excinfo:
        config.persistent_storage(env)
    assert config.ENV_APP_PERSISTENT_STORAGE in excinfo.value.message
    assert excinfo.value.hint


def test_a_volume_that_does_not_exist_is_never_created_silently(tmp_path: Path) -> None:
    """A missing mount point is a deployment error, not a directory we may invent."""
    missing = tmp_path / "not-mounted"
    env = {**_exapp_env(), config.ENV_APP_PERSISTENT_STORAGE: str(missing)}

    with pytest.raises(ToolError) as excinfo:
        config.persistent_storage(env)
    assert config.ENV_APP_PERSISTENT_STORAGE in excinfo.value.message
    assert not missing.exists()


def test_a_volume_that_is_a_file_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "oauth"
    target.write_text("not a directory", encoding="utf-8")
    env = {**_exapp_env(), config.ENV_APP_PERSISTENT_STORAGE: str(target)}

    with pytest.raises(ToolError) as excinfo:
        config.persistent_storage(env)
    assert config.ENV_APP_PERSISTENT_STORAGE in excinfo.value.message


def test_a_volume_that_cannot_be_written_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read only mount answers every question right until the first write."""
    monkeypatch.setattr(config, "_probe_writable", lambda path: False)
    env = {**_exapp_env(), config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}

    with pytest.raises(ToolError) as excinfo:
        config.persistent_storage(env)
    assert config.ENV_APP_PERSISTENT_STORAGE in excinfo.value.message
    assert excinfo.value.hint


def test_the_probe_really_writes_and_leaves_nothing_behind(tmp_path: Path) -> None:
    """os.access lies on Windows and inside containers, so the check writes a file."""
    assert config._probe_writable(tmp_path) is True
    assert list(tmp_path.iterdir()) == []
    assert config._probe_writable(tmp_path / "missing") is False


def test_outside_the_exapp_mode_the_store_falls_back_into_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The --manual development mode has no volume; the fallback is named, not silent."""
    monkeypatch.chdir(tmp_path)
    with caplog.at_level(logging.WARNING, logger="mcp_connector.config"):
        path = config.persistent_storage({})

    assert path == tmp_path / config.DEV_STORAGE_DIR
    assert path.is_dir()
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.DEV_STORAGE_DIR in messages
    assert config.ENV_APP_PERSISTENT_STORAGE in messages


def test_the_development_fallback_directory_is_git_ignored() -> None:
    """A store full of encrypted app passwords must never become a commit."""
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"{config.DEV_STORAGE_DIR}/" in [line.strip() for line in ignored]


# --- the switch that closes the outgoing Talk channel (TALK-04) -------------------


def test_the_talk_switch_carries_the_name_the_manifest_declares() -> None:
    """The variable name is the contract with AppAPI: an undeclared one is dropped."""
    assert config.ENV_TALK_SEND == "NC_MCP_TALK_SEND"


@pytest.mark.parametrize("raw", sorted(config._TRUE_VALUES))
def test_every_understood_on_spelling_leaves_sending_enabled(raw: str) -> None:
    assert config.talk_send_enabled({config.ENV_TALK_SEND: raw}) is True


@pytest.mark.parametrize("raw", sorted(config._FALSE_VALUES))
def test_every_understood_off_spelling_switches_sending_off(raw: str) -> None:
    assert config.talk_send_enabled({config.ENV_TALK_SEND: raw}) is False


@pytest.mark.parametrize("raw", ["OFF", "False", "NO", "  off  ", "\tOFF\n"])
def test_an_off_spelling_is_read_without_regard_to_case_or_padding(raw: str) -> None:
    """An administrator who types OFF has switched it off, not entered a typo."""
    assert config.talk_send_enabled({config.ENV_TALK_SEND: raw}) is False


def test_without_the_variable_sending_is_enabled() -> None:
    """The shipped state of TALK-04: the switch is the countermeasure for the outgoing
    channel, not its precondition, so an installation that sets nothing can send."""
    assert config.talk_send_enabled({}) is True


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_value_counts_as_unset(blank: str) -> None:
    """The same rule ``exapp_configured`` applies: an empty value in a compose file is a
    typo, not a request to remove a capability."""
    assert config.talk_send_enabled({config.ENV_TALK_SEND: blank}) is True


@pytest.mark.parametrize("raw", ["vielleicht", "maybe", "enabled", "2", "-1", "onoff"])
def test_a_value_nobody_understands_never_switches_sending_off(raw: str) -> None:
    """Why the reader says ``not in _FALSE_VALUES`` instead of ``in _TRUE_VALUES``.

    With the positive membership test a typo would answer False, and an instance would
    silently lose a capability this server promises without one line saying so. The default
    of this switch is on, so only a spelling that means off may turn it off.
    """
    assert config.talk_send_enabled({config.ENV_TALK_SEND: raw}) is True


def test_the_switch_reads_the_process_environment_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The property plan 09-03 builds on: a tool has no resolved mapping in its hand, so it
    reads the process environment per call, exactly like ``select_mode`` does today."""
    monkeypatch.setenv(config.ENV_TALK_SEND, config_values.SWITCH_OFF)
    assert config.talk_send_enabled() is False

    monkeypatch.setenv(config.ENV_TALK_SEND, config_values.SWITCH_ON)
    assert config.talk_send_enabled() is True

    monkeypatch.delenv(config.ENV_TALK_SEND)
    assert config.talk_send_enabled() is True


def test_the_switch_spellings_are_the_ones_the_form_and_the_registry_understand() -> None:
    """Three modules read a switch value and all three have to speak one language.

    The sets are spelled three times because ``exapp/config_values.py`` imports this module,
    so a shared constant would be a circular import. This is the test the comment on those
    sets refers to: without it a value would arm a switch in the deploy environment and be
    refused by the admin form, and nothing would say why.
    """
    assert config._TRUE_VALUES == config_values.TRUE_VALUES
    assert config._FALSE_VALUES == config_values.FALSE_VALUES
    assert config._TRUE_VALUES == registry._TRUE_VALUES
    assert config._FALSE_VALUES == registry._FALSE_VALUES


# --- the three variables of the audit log (D-09, D-14, AUDIT-03) ------------------


def test_the_three_audit_variables_carry_the_names_the_rest_of_the_chain_expects() -> None:
    """The spelling is pinned because two other places name it: ``KEY_TO_ENV`` maps the admin
    field onto it, and ``docs`` will quote it. Unlike ``NC_MCP_TALK_SEND`` these three carry
    no ``<environment-variables>`` entry in ``appinfo/info.xml`` yet, so the way an
    administrator reaches the switch is the admin form of ``exapp/admin_settings.py`` and not
    a deploy variable of a store installation.
    """
    assert config.ENV_AUDIT_LOG == "NC_MCP_AUDIT_LOG"
    assert config.ENV_AUDIT_RETENTION_DAYS == "NC_MCP_AUDIT_RETENTION_DAYS"
    assert config.ENV_AUDIT_MAX_BYTES == "NC_MCP_AUDIT_MAX_BYTES"


def test_the_two_repeated_numbers_are_the_ones_the_store_ships_with() -> None:
    """The test the comment above the two constants promises.

    They stand twice because a ``from .audit import store`` in ``config.py`` would close an
    import ring: ``store.py`` imports nothing but the standard library, but its package does
    import this module. A test can import both sides without any of that, so the copy is held
    equal here instead of being made unnecessary there.
    """
    assert config.AUDIT_RETENTION_DAYS == audit_store.RETENTION_DAYS
    assert config.AUDIT_SIZE_LIMIT_BYTES == audit_store.SIZE_LIMIT_BYTES


def test_without_the_variable_the_audit_log_is_off() -> None:
    """D-14, the sentence the whole phase hangs on: nothing is recorded unless asked for.

    This is also what the first start after an installation gets: AppAPI answers the admin
    value read with 401 while the app is not enabled yet, the overlay is empty, and an empty
    overlay lands exactly here.
    """
    assert config.audit_log_enabled({}) is False


@pytest.mark.parametrize("raw", sorted(config._TRUE_VALUES))
def test_every_understood_on_spelling_switches_the_audit_log_on(raw: str) -> None:
    assert config.audit_log_enabled({config.ENV_AUDIT_LOG: raw}) is True


@pytest.mark.parametrize("raw", sorted(config._FALSE_VALUES))
def test_every_understood_off_spelling_leaves_the_audit_log_off(raw: str) -> None:
    assert config.audit_log_enabled({config.ENV_AUDIT_LOG: raw}) is False


@pytest.mark.parametrize("raw", ["ON", "True", "  on  ", "\tYES\n"])
def test_an_on_spelling_is_read_without_regard_to_case_or_padding(raw: str) -> None:
    assert config.audit_log_enabled({config.ENV_AUDIT_LOG: raw}) is True


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_audit_value_counts_as_unset(blank: str) -> None:
    assert config.audit_log_enabled({config.ENV_AUDIT_LOG: blank}) is False


@pytest.mark.parametrize("raw", ["vielleicht", "maybe", "enabled", "2", "-1", "onoff"])
def test_a_typo_never_switches_the_audit_log_on(raw: str, caplog: pytest.LogCaptureFixture) -> None:
    """The opposite direction of ``talk_send_enabled``, and the reason it is the opposite.

    There a typo must not take a promised capability away, so an unreadable value stays on.
    Here a typo must not start a record about named people, so an unreadable value stays off.
    The warning names the field and never the value: it may have arrived over HTTP.
    """
    with caplog.at_level(logging.WARNING, logger="mcp_connector.config"):
        assert config.audit_log_enabled({config.ENV_AUDIT_LOG: raw}) is False

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_AUDIT_LOG in logged
    assert raw not in logged


def test_the_audit_switch_reads_the_process_environment_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same shape every other reader of this module has, so no caller is a special case."""
    monkeypatch.setenv(config.ENV_AUDIT_LOG, config_values.SWITCH_ON)
    assert config.audit_log_enabled() is True

    monkeypatch.delenv(config.ENV_AUDIT_LOG)
    assert config.audit_log_enabled() is False


def test_the_retention_window_defaults_to_the_number_the_store_ships_with() -> None:
    assert config.audit_retention_days({}) == 180


@pytest.mark.parametrize(("raw", "expected"), [("180", 180), ("365", 365), ("3650", 3650)])
def test_a_retention_window_at_or_above_the_floor_is_taken(raw: str, expected: int) -> None:
    """Longer than asked for is the administrator's decision and nothing here argues."""
    assert config.audit_retention_days({config.ENV_AUDIT_RETENTION_DAYS: raw}) == expected


@pytest.mark.parametrize("raw", ["0", "1", "10", "179"])
def test_a_retention_window_below_the_floor_is_refused(
    raw: str, caplog: pytest.LogCaptureFixture
) -> None:
    """AUDIT-03 asks that the window can reach 180 days, so a smaller one breaks it."""
    with caplog.at_level(logging.WARNING, logger="mcp_connector.config"):
        assert config.audit_retention_days({config.ENV_AUDIT_RETENTION_DAYS: raw}) == 180

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_AUDIT_RETENTION_DAYS in logged


def test_the_size_limit_defaults_to_the_number_the_store_ships_with() -> None:
    assert config.audit_size_limit({}) == 100_000_000


def test_a_size_limit_above_the_floor_is_taken() -> None:
    assert config.audit_size_limit({config.ENV_AUDIT_MAX_BYTES: "250000000"}) == 250_000_000


@pytest.mark.parametrize("raw", ["0", "1", "999999"])
def test_a_size_limit_below_the_floor_is_refused(raw: str) -> None:
    """A mistyped few bytes would sweep every row away the moment it was written."""
    assert config.audit_size_limit({config.ENV_AUDIT_MAX_BYTES: raw}) == 100_000_000


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "abc", "-5", "12.5", "1_000", "180 days", "²", "١٢٣", "9" * 5000],
)
def test_no_audit_number_ever_raises_on_a_string(raw: str) -> None:
    """Read at startup, so a refused value must never keep a container from serving.

    The last three are the ones ``str.isdigit`` alone would let through: a superscript, the
    Arabic-Indic digits and a run longer than the integer conversion limit of Python 3.11.
    """
    assert config.audit_retention_days({config.ENV_AUDIT_RETENTION_DAYS: raw}) == 180
    assert config.audit_size_limit({config.ENV_AUDIT_MAX_BYTES: raw}) == 100_000_000


def test_the_audit_numbers_read_the_process_environment_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_AUDIT_RETENTION_DAYS, "400")
    monkeypatch.setenv(config.ENV_AUDIT_MAX_BYTES, "200000000")
    assert config.audit_retention_days() == 400
    assert config.audit_size_limit() == 200_000_000


# --- the token exchange namespace (CONF-01) ----------------------------------------------


def test_without_the_variable_the_exchange_path_is_off() -> None:
    """CONF-01 in one line: the factory state of the second verification path is off.

    The same sentence D-14 writes for the audit log, for the neighbouring reason: a path
    that accepts tokens of a foreign issuer must never start itself.
    """
    assert config.exchange_enabled({}) is False


@pytest.mark.parametrize("raw", sorted(config._TRUE_VALUES))
def test_every_understood_on_spelling_arms_the_exchange_path(raw: str) -> None:
    assert config.exchange_enabled({config.ENV_EXCHANGE_ENABLED: raw}) is True


@pytest.mark.parametrize("raw", sorted(config._FALSE_VALUES))
def test_every_understood_off_spelling_leaves_the_exchange_path_off(raw: str) -> None:
    assert config.exchange_enabled({config.ENV_EXCHANGE_ENABLED: raw}) is False


@pytest.mark.parametrize("raw", ["ON", "True", "  on  ", "\tYES\n"])
def test_an_exchange_on_spelling_is_read_without_regard_to_case_or_padding(raw: str) -> None:
    assert config.exchange_enabled({config.ENV_EXCHANGE_ENABLED: raw}) is True


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_exchange_value_counts_as_unset(blank: str) -> None:
    assert config.exchange_enabled({config.ENV_EXCHANGE_ENABLED: blank}) is False


@pytest.mark.parametrize("raw", ["vielleicht", "maybe", "enabled", "2", "-1", "onoff"])
def test_a_typo_never_arms_the_exchange_path(raw: str, caplog: pytest.LogCaptureFixture) -> None:
    """A second verification path that starts because somebody mistyped is the failure
    CONF-01 was written against. The warning names the variable and never the value."""
    with caplog.at_level(logging.WARNING, logger="mcp_connector.config"):
        assert config.exchange_enabled({config.ENV_EXCHANGE_ENABLED: raw}) is False

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_EXCHANGE_ENABLED in logged
    assert raw not in logged


def test_the_exchange_switch_reads_the_process_environment_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_EXCHANGE_ENABLED, "1")
    assert config.exchange_enabled() is True

    monkeypatch.delenv(config.ENV_EXCHANGE_ENABLED)
    assert config.exchange_enabled() is False


def test_the_exchange_namespace_is_one_list_without_duplicates() -> None:
    """The collection ``chain.load_exchange_config`` checks a disarmed process against.

    A list kept by hand in two places falls apart, so it stands here and nowhere else.
    """
    assert len(config.EXCHANGE_VARIABLES) == len(set(config.EXCHANGE_VARIABLES))
    assert config.ENV_EXCHANGE_ENABLED in config.EXCHANGE_VARIABLES
    assert all(name.startswith("NC_MCP_EXCHANGE_") for name in config.EXCHANGE_VARIABLES)


def test_every_exchange_constant_of_this_module_stands_in_the_namespace() -> None:
    """Adding a variable without adding it to the collection would leave a hole in the
    refusal of a configured but disarmed process, and that hole is T-22-02."""
    named = {
        value
        for name, value in vars(config).items()
        if name.startswith("ENV_EXCHANGE_") and isinstance(value, str)
    }
    assert named == set(config.EXCHANGE_VARIABLES)


def test_the_exchange_namespace_selects_no_mode_of_its_own() -> None:
    """The off state of this phase, measured and not asserted in prose.

    A fully configured exchange environment answers every ``select_mode`` question exactly
    as an environment without one: the sixth mode does not exist, and plan 22-02 has to
    stay inside the five that do.
    """
    exchange_env = dict.fromkeys(config.EXCHANGE_VARIABLES, "x")
    headers = {"host": "nc.test"}

    assert config.select_mode(exchange_env) == "stdio"
    assert config.select_mode(exchange_env, headers=headers) == "http_passthrough"
    assert (
        config.select_mode(
            {**exchange_env, config.ENV_APP_ID: "mcp_connector", config.ENV_APP_SECRET: "s"},
            headers=headers,
        )
        == "exapp"
    )
    assert (
        config.select_mode(
            {**exchange_env, config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH}, headers=headers
        )
        == "oauth"
    )
    assert (
        config.select_mode({**exchange_env, config.ENV_STATIC_BEARER: "b"}, headers=headers)
        == "http_static_bearer"
    )


def test_the_mode_literal_still_has_exactly_five_values() -> None:
    modes = typing.get_args(config.Mode)
    assert sorted(modes) == [
        "exapp",
        "http_passthrough",
        "http_static_bearer",
        "oauth",
        "stdio",
    ]
    assert not any("exchange" in mode for mode in modes)


def test_the_account_claim_default_is_the_one_claim_every_token_carries() -> None:
    """``sub`` is the only claim Keycloak writes into every exchanged token, and phase 21
    already checks it for shape. Every other claim hangs on an open F13 answer."""
    assert config.DEFAULT_EXCHANGE_ACCOUNT_CLAIM == "sub"


def test_the_two_mapping_variables_stand_in_the_exchange_namespace() -> None:
    """MAP-01: only a variable of ``EXCHANGE_VARIABLES`` refuses a configured but disarmed
    start, so a mapping variable outside the collection would be the hole of T-22-02."""
    assert config.ENV_EXCHANGE_MAPPING in config.EXCHANGE_VARIABLES
    assert config.ENV_EXCHANGE_OIDC_PROVIDER_ID in config.EXCHANGE_VARIABLES


def test_the_mapping_default_is_the_account_id_profile_of_the_mapping_module() -> None:
    """``config`` imports nothing from ``oauth``, so the default stands here as a string;
    this test is what keeps the two spellings from drifting apart."""
    from mcp_connector.oauth import mapping

    assert config.DEFAULT_EXCHANGE_MAPPING == mapping.MAPPING_ACCOUNT_ID_V1

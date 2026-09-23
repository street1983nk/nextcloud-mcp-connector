"""The seven admin values of BL-06, TALK-04 and D-14, read out of the ExApp configuration.

Nothing here opens a socket: the one outgoing OCS call is answered by respx, exactly as in
``test_oauth_crypto.py``, whose read path this module reuses.

What is asserted below is the difference to that read path and not the path itself. Reading
the data key fails hard, because a key nobody stored makes every authorization unreadable.
Reading an admin value fails soft, because a missing value means "the administrator has not
set anything" and the deploy environment is the answer then. Every failure of this module is
therefore an empty result plus one log line, and the tests hold both halves: the empty
result and the absence of any request or response value in the log.

Threats covered: T-05-01 (the public URL becomes issuer and resource, so an unusable one is
dropped instead of adopted), T-05-02 (an unreadable answer is never read as "no value") and
T-05-03 (neither the app secret nor a read value reaches a log record).
"""

import base64
import inspect
import json
import logging
from typing import Any

import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.exapp import config_values
from mcp_connector.oauth import crypto, registry

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.test/exapps/mcp_connector"

ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_AA_VERSION: "34.0.3",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
    config.ENV_PUBLIC_URL: PUBLIC_URL,
}

#: The read is a POST on its own route (measured against AppAPI 34.0.0 in plan 03-08), and
#: the constants come from ``crypto`` instead of being spelled a second time here.
READ_URL = f"{BASE_URL}{crypto.EXAPP_CONFIG_PATH}{crypto.CONFIG_READ_SUFFIX}"

ADMIN_URL = "https://cloud.example.test/exapps/mcp_connector"


def ocs_body(data: object) -> dict[str, object]:
    """The OCS v2 envelope AppAPI answers with."""
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def stored(values: dict[str, Any], *, camel: bool = False) -> dict[str, object]:
    """The list of entries AppAPI answers with, lower case by default (AppAPI 34.0.0)."""
    key_field = "configKey" if camel else "configkey"
    value_field = "configValue" if camel else "configvalue"
    return ocs_body([{key_field: key, value_field: value} for key, value in values.items()])


def answer(values: dict[str, Any], *, camel: bool = False) -> respx.Route:
    """Mock the one read route with these stored values."""
    return respx.post(READ_URL).mock(
        return_value=httpx.Response(200, json=stored(values, camel=camel))
    )


# --- the contract of the seven keys --------------------------------------------------


def test_the_seven_keys_are_the_field_ids_of_the_admin_form() -> None:
    """Pattern 1 of the research: the config key IS the field id, without a prefix.

    Five since finding B-1 of the v1.0 milestone audit: ``NC_MCP_OAUTH_CIMD`` was a deploy
    variable and a manifest declaration and nothing in this chain, so on the one kind of
    installation this chain exists for, the one from the app store, that switch could not be
    set at all. Six since phase 9, where ``talk_send`` was the same case, and it came after
    the four OAuth values because those belong together (``registry.client_policy`` reads two
    of them as one answer). Seven since phase 18: ``audit_log`` is the switch of D-14, and it
    is last because it is about this app watching itself and not about who may reach it.
    """
    assert config_values.CONFIG_KEYS == (
        "public_url",
        "oauth_dcr",
        "oauth_cimd",
        "oauth_allowlist_only",
        "oauth_allowed_clients",
        "talk_send",
        "audit_log",
    )


def test_every_key_maps_to_the_variable_the_existing_code_already_reads() -> None:
    """The overlay speaks the spelling of the deploy environment, so no signature changes."""
    assert config_values.KEY_TO_ENV == {
        "public_url": config.ENV_PUBLIC_URL,
        "oauth_dcr": registry.ENV_DCR,
        "oauth_cimd": registry.ENV_CIMD,
        "oauth_allowlist_only": registry.ENV_ALLOWLIST_ONLY,
        "oauth_allowed_clients": registry.ENV_ALLOWED_CLIENTS,
        "talk_send": config.ENV_TALK_SEND,
        "audit_log": config.ENV_AUDIT_LOG,
    }
    assert set(config_values.KEY_TO_ENV) == set(config_values.CONFIG_KEYS)


def test_the_talk_switch_is_validated_like_every_other_checkbox() -> None:
    """No new validation code: ``_usable_value`` already branches on this set."""
    assert "talk_send" in config_values.SWITCH_KEYS


def test_the_audit_switch_is_validated_like_every_other_checkbox() -> None:
    """D-14 needs no validation of its own either: a refused value leaves the key out of the
    overlay, so the deploy variable and then ``config.audit_log_enabled`` decide, and that
    last one says off."""
    assert "audit_log" in config_values.SWITCH_KEYS


def test_the_switch_spellings_are_the_ones_the_registry_understands() -> None:
    """Both sources have to speak one language, or a value works in Env and not in the form."""
    assert config_values.TRUE_VALUES == registry._TRUE_VALUES
    assert config_values.FALSE_VALUES == registry._FALSE_VALUES


def test_only_one_place_in_this_module_reaches_the_network() -> None:
    """Shared pattern 6: one call site, one attempt, and ``env`` is always a parameter."""
    source = inspect.getsource(config_values)
    assert source.count("await client.post") == 1
    assert source.count("shared_client()") == 1


# --- the read itself ---------------------------------------------------------------


@pytest.mark.anyio
@respx.mock
async def test_one_request_asks_for_all_seven_keys() -> None:
    """Seven values, one round trip: the read takes a list and there is nothing to loop."""
    route = answer({"public_url": ADMIN_URL})

    values = await config_values.read_values(env=ENV)

    assert route.call_count == 1
    sent = route.calls.last.request
    assert sent.url.path.endswith("/ex-app/config/get-values")
    assert json.loads(sent.content) == {
        crypto.CONFIG_READ_FIELD: [
            "public_url",
            "oauth_dcr",
            "oauth_cimd",
            "oauth_allowlist_only",
            "oauth_allowed_clients",
            "talk_send",
            "audit_log",
        ]
    }
    assert values == {"public_url": ADMIN_URL}


@pytest.mark.anyio
@respx.mock
async def test_the_read_runs_in_the_app_context() -> None:
    """The empty user id is the point: the app asks about itself, not for a person."""
    route = answer({"public_url": ADMIN_URL})

    await config_values.read_values(env=ENV)

    sent = route.calls.last.request
    assert (
        sent.headers["AUTHORIZATION-APP-API"]
        == base64.b64encode(f":{APP_SECRET}".encode()).decode()
    )
    assert sent.headers["EX-APP-ID"] == APP_ID
    assert sent.headers["EX-APP-VERSION"] == APP_VERSION
    assert sent.headers["OCS-APIRequest"] == "true"


@pytest.mark.anyio
@respx.mock
async def test_the_lower_case_field_names_of_appapi_34_are_read() -> None:
    """The measured shape: the column names of ``ex_apps_config``, serialised as they are."""
    answer({"public_url": ADMIN_URL, "oauth_dcr": "0"})

    assert await config_values.read_values(env=ENV) == {
        "public_url": ADMIN_URL,
        "oauth_dcr": "0",
    }


@pytest.mark.anyio
@respx.mock
async def test_the_camel_case_field_names_are_read_as_well() -> None:
    """The spelling of the write path, and what a later AppAPI may answer with."""
    answer({"public_url": ADMIN_URL}, camel=True)

    assert await config_values.read_values(env=ENV) == {"public_url": ADMIN_URL}


@pytest.mark.anyio
@respx.mock
async def test_a_mapping_envelope_is_read_too() -> None:
    """The third accepted shape, same as in ``crypto._config_value``."""
    respx.post(READ_URL).mock(
        return_value=httpx.Response(200, json=ocs_body({"public_url": ADMIN_URL, "oauth_dcr": "1"}))
    )

    assert await config_values.read_values(env=ENV) == {
        "public_url": ADMIN_URL,
        "oauth_dcr": "1",
    }


@pytest.mark.anyio
@respx.mock
async def test_a_key_nobody_stored_is_simply_absent() -> None:
    """An empty list is a readable answer and means exactly one thing: nothing is set."""
    respx.post(READ_URL).mock(return_value=httpx.Response(200, json=ocs_body([])))

    assert await config_values.read_values(env=ENV) == {}


@pytest.mark.anyio
@respx.mock
async def test_a_json_boolean_is_read_as_a_switch_value() -> None:
    """A checkbox may arrive as a JSON boolean, and ``True`` is not a broken answer."""
    answer({"oauth_dcr": True, "oauth_allowlist_only": False})

    assert await config_values.read_values(env=ENV) == {
        "oauth_dcr": "true",
        "oauth_allowlist_only": "false",
    }


# --- every failure is an empty result plus one log line ----------------------------


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    "outcome",
    [
        "unreachable",
        "timeout",
        "status_500",
        "status_403",
        "not_json",
        "no_envelope",
        "wrong_types",
    ],
)
async def test_a_failed_read_is_an_empty_result_and_never_an_exception(
    caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    """The whole difference to ``crypto._read_key``: this path must not stop an install.

    The one answer that is not in this list is ``401``: plan 05-12 measured it as the
    expected outcome of a window every installation passes through, and it has its own test
    below. Every other failure stays an ``ERROR``, and ``403`` stands here to hold that
    line: only ``401`` is the measured expectation, not "any 4xx".
    """
    route = respx.post(READ_URL)
    if outcome == "unreachable":
        route.mock(side_effect=httpx.ConnectError("no route to nextcloud"))
    elif outcome == "timeout":
        route.mock(side_effect=httpx.ReadTimeout("nextcloud is slow"))
    elif outcome == "status_500":
        route.mock(return_value=httpx.Response(500, json={}))
    elif outcome == "status_403":
        route.mock(return_value=httpx.Response(403, json={}))
    elif outcome == "not_json":
        route.mock(return_value=httpx.Response(200, content=b"<html>login</html>"))
    elif outcome == "no_envelope":
        route.mock(return_value=httpx.Response(200, json={"unexpected": "shape"}))
    else:
        route.mock(return_value=httpx.Response(200, json=ocs_body([{"configkey": 7}])))

    with caplog.at_level(logging.DEBUG):
        assert await config_values.read_values(env=ENV) == {}

    assert [record for record in caplog.records if record.levelno >= logging.ERROR], (
        "a silent empty result would look like an administrator who set nothing"
    )


@pytest.mark.anyio
@respx.mock
async def test_a_401_is_told_as_the_expected_answer_before_this_app_is_activated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The measured window of plan 05-12, and the only failure of this read that is expected.

    ``AppAPIService::validateExAppRequestToNC`` accepts the app secret and then falls over
    ``!$exApp->getEnabled()``; only ``ex-app/state`` is exempt, the configuration path is
    not (measurements M3b and M3c plus the source of AppAPI 34.0.0). Every first start after
    a deployment sits inside that window, because ``enable`` comes after ``init``, and in
    that window there cannot be an admin value yet.

    The read keeps failing soft, so the result is empty and the deploy environment stays in
    force. What this test holds is the level: an ``ERROR`` line for the normal course of an
    installation made a working installation look broken, which is exactly what happened in
    this phase.
    """
    respx.post(READ_URL).mock(return_value=httpx.Response(401, json={}))

    with caplog.at_level(logging.DEBUG):
        assert await config_values.read_values(env=ENV) == {}

    # Only the records of this module: httpx logs every request it makes at INFO as well,
    # and that line is not the one under test here.
    ours = [record for record in caplog.records if record.name == config_values.logger.name]
    assert not [record for record in ours if record.levelno >= logging.WARNING], (
        "the expected answer of a window every installation passes through is not a fault"
    )
    told = [record for record in ours if record.levelno == logging.INFO]
    assert len(told) == 1, "one line, like every other outcome of this read"
    message = told[0].getMessage()
    assert "401" in message
    # The line has to carry the way out, or it is only a friendlier dead end: a value set in
    # the form takes effect after one disable and enable cycle (measurement M3).
    assert "disabled and enabled" in message


@pytest.mark.anyio
@respx.mock
async def test_a_broken_deploy_environment_is_an_empty_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``exapp_settings`` raises when a variable is missing (IN-02). Not here it does not."""
    broken = {key: value for key, value in ENV.items() if key != config.ENV_APP_SECRET}

    with caplog.at_level(logging.DEBUG):
        assert await config_values.read_values(env=broken) == {}
        assert await config_values.admin_overlay(env=broken) == {}


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("outcome", ["ok", "refused", "unreachable"])
async def test_no_request_or_response_value_reaches_a_log_record(
    caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    """T-05-03: the headers carry the app secret and the answer carries admin values."""
    route = respx.post(READ_URL)
    if outcome == "unreachable":
        route.mock(side_effect=httpx.ConnectError("no route to nextcloud"))
    elif outcome == "refused":
        route.mock(return_value=httpx.Response(500, json={}))
    else:
        route.mock(
            return_value=httpx.Response(
                200,
                json=stored(
                    {"public_url": ADMIN_URL, "oauth_allowed_clients": "https://secret.test/cb"}
                ),
            )
        )

    with caplog.at_level(logging.DEBUG):
        await config_values.admin_overlay(env=ENV)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert APP_SECRET not in logged
    assert base64.b64encode(f":{APP_SECRET}".encode()).decode() not in logged
    assert ADMIN_URL not in logged
    assert "https://secret.test/cb" not in logged


# --- the overlay: the public URL ---------------------------------------------------


@pytest.mark.anyio
@respx.mock
async def test_a_usable_public_url_becomes_the_env_spelling() -> None:
    """The contract for plan 05-04: the key is the variable name, the value is a string."""
    answer({"public_url": ADMIN_URL})

    assert await config_values.admin_overlay(env=ENV) == {config.ENV_PUBLIC_URL: ADMIN_URL}


@pytest.mark.anyio
@respx.mock
async def test_whitespace_and_a_trailing_slash_are_removed() -> None:
    """Same normalisation as ``config.public_url``, so both sources produce one issuer."""
    answer({"public_url": f"  {ADMIN_URL}/  "})

    assert await config_values.admin_overlay(env=ENV) == {config.ENV_PUBLIC_URL: ADMIN_URL}


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    ("value", "why"),
    [
        ("https://cloud.example.test/exapps/mcp_connector#frag", "a fragment"),
        ("https://user:pass@cloud.example.test/exapps/mcp_connector", "credentials in the URL"),
        ("cloud.example.test/exapps/mcp_connector", "no scheme"),
        ("ftp://cloud.example.test", "a scheme that is not http"),
        ("https://", "no host"),
        ("https://cloud.example.test:0/x", "a port outside the range"),
        ("https://cloud.example.test:99999/x", "a port outside the range"),
        ("javascript:alert(1)", "not a URL at all"),
        # CR-01 of 05-REVIEW.md and gap 1 of 05-VERIFICATION.md: the value that used to pass
        # this validation and then killed the process on the next start.
        ("http://cloud.example.com/exapps/mcp_connector", "http on a host that is not loopback"),
        ("HTTP://Cloud.Example.COM", "the same in upper case, which decides nothing"),
        ("http://localhost.example.com/x", "a host that merely contains a loopback word"),
        ("http://127.0.0.1.example.com/x", "the same trick with the loopback address"),
        ("http://192.168.1.10:8080/x", "a private address is still not loopback"),
    ],
)
async def test_an_unusable_public_url_is_dropped_and_named_without_its_value(
    caplog: pytest.LogCaptureFixture, value: str, why: str
) -> None:
    """T-05-01: this value becomes the issuer of the AS metadata and the resource of the PRM."""
    answer({"public_url": value})

    with caplog.at_level(logging.DEBUG):
        overlay = await config_values.admin_overlay(env=ENV)

    assert overlay == {}, f"rejected because of {why}"
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "public_url" in logged, "the field is named so an administrator can find it"
    assert value not in logged


# --- the refused fields, next to the overlay (05-14, line B) -----------------------


@pytest.mark.anyio
@respx.mock
async def test_a_refused_value_is_named_as_refused_and_not_as_absent() -> None:
    """The second half of the read: "nothing set" and "set and unusable" are not one state.

    The overlay cannot tell them apart, both are the same missing key, and the setup line of
    ``entry_exapp.main`` used to report the second one as the first (05-14, line B).
    """
    answer({"public_url": "http://cloud.example.com/exapps/mcp_connector"})

    values = await config_values.admin_values(env=ENV)

    assert values.overlay == {}
    assert values.refused == frozenset({config_values.PUBLIC_URL_KEY})


@pytest.mark.anyio
@respx.mock
async def test_a_field_nobody_filled_in_is_refused_by_nobody() -> None:
    """A blank value is not a typo: the deploy environment simply keeps this key."""
    answer({"public_url": "   ", "oauth_dcr": ""})

    values = await config_values.admin_values(env=ENV)

    assert values.overlay == {}
    assert values.refused == frozenset()


@pytest.mark.anyio
@respx.mock
async def test_the_refusals_are_per_field_like_the_validation() -> None:
    """A typo in one field is neither an outage nor a refusal of the other three."""
    answer({"public_url": ADMIN_URL, "oauth_dcr": "vielleicht"})

    values = await config_values.admin_values(env=ENV)

    assert values.overlay == {config.ENV_PUBLIC_URL: ADMIN_URL}
    assert values.refused == frozenset({"oauth_dcr"})


@pytest.mark.anyio
@respx.mock
async def test_a_read_that_failed_refuses_nothing() -> None:
    """T-05-02 again, from this side: an unreadable answer is not a refused value.

    Reporting a refusal here would tell an administrator her value was rejected when the
    truth is that this app never saw one.
    """
    respx.post(READ_URL).mock(return_value=httpx.Response(500))

    values = await config_values.admin_values(env=ENV)

    assert values.overlay == {}
    assert values.refused == frozenset()


@pytest.mark.anyio
@respx.mock
async def test_the_overlay_is_the_overlay_half_of_the_same_read() -> None:
    """One reader of the difference, one function for everyone else, one read for both."""
    answer({"public_url": ADMIN_URL, "oauth_dcr": "vielleicht"})
    overlay = await config_values.admin_overlay(env=ENV)

    answer({"public_url": ADMIN_URL, "oauth_dcr": "vielleicht"})
    values = await config_values.admin_values(env=ENV)

    assert overlay == values.overlay


# --- the issuer rule of CR-01: https, with the loopback exception ------------------


def test_the_loopback_hosts_are_the_three_spellings_of_this_machine() -> None:
    """``urlsplit(...).hostname`` lowercases and strips the brackets of an IPv6 host.

    So ``::1`` stands here without brackets, and a fourth entry ``[::1]`` would be a line no
    comparison could ever reach.
    """
    assert isinstance(config_values.LOOPBACK_HOSTS, frozenset)
    assert set(config_values.LOOPBACK_HOSTS) == {"localhost", "127.0.0.1", "::1"}


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    ("value", "expected", "why"),
    [
        (
            "https://cloud.example.com/exapps/mcp_connector",
            "https://cloud.example.com/exapps/mcp_connector",
            "the normal case of an installation",
        ),
        (
            "HTTPS://Cloud.Example.COM",
            "https://cloud.example.com",
            "case decides nothing on the accepted side either, and it is levelled (IN-03)",
        ),
        ("http://127.0.0.1:8765", "http://127.0.0.1:8765", "the default in code, still usable"),
        (
            "http://localhost:8765/exapps/mcp_connector",
            "http://localhost:8765/exapps/mcp_connector",
            "loopback by name, with port and subpath",
        ),
        ("http://localhost", "http://localhost", "loopback by name, without port and subpath"),
        (
            "http://[::1]:8765",
            "http://[::1]:8765",
            "loopback as an IPv6 literal, which arrives in brackets and keeps them",
        ),
    ],
)
async def test_https_and_every_loopback_spelling_reach_the_overlay(
    value: str, expected: str, why: str
) -> None:
    """The other half of CR-01: the rule refuses http, it does not refuse development.

    A local test topology serves over http on loopback, and RFC 8414 allows exactly that.
    """
    answer({"public_url": value})

    assert await config_values.admin_overlay(env=ENV) == {config.ENV_PUBLIC_URL: expected}, why


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    ("value", "expected", "why"),
    [
        (
            "HTTPS://Cloud.Example.COM/exapps/MCP_Connector",
            "https://cloud.example.com/exapps/MCP_Connector",
            "scheme and host are case insensitive per RFC 3986, a path is not",
        ),
        (
            "https://Cloud.Example.COM:8443/x",
            "https://cloud.example.com:8443/x",
            "the port survives the levelling",
        ),
        (
            "http://LOCALHOST:8765",
            "http://localhost:8765",
            "the loopback exception is spelled in one case afterwards as well",
        ),
        (
            "https://cloud.example.com/exapps/mcp_connector?x=A",
            "https://cloud.example.com/exapps/mcp_connector?x=A",
            "a query is left alone, like the path",
        ),
    ],
)
async def test_the_issuer_leaves_this_module_in_one_spelling(
    value: str, expected: str, why: str
) -> None:
    """IN-03: this value becomes the ``issuer`` and the prefix of ``resource``.

    Clients compare both character by character, which the trailing slash paragraph of
    ``docs/client-setup.md`` and ``docs/oauth-setup.md`` says in as many words. An
    administrator who types the address with a capital letter and then enters it lower case
    in her client fails a comparison that no log line explains. Scheme and host are case
    insensitive per RFC 3986 section 3.1 and 3.2.2, so levelling them loses nothing; the
    path is case sensitive and is therefore left exactly as it arrived.
    """
    answer({"public_url": value})

    assert await config_values.admin_overlay(env=ENV) == {config.ENV_PUBLIC_URL: expected}, why


@pytest.mark.anyio
@respx.mock
async def test_the_refused_http_value_leaves_neither_host_nor_value_in_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-05-43: the line names the field and the rule, and a container log is read by more
    than the administrator who typed the value."""
    value = "http://cloud.example.com/exapps/mcp_connector"
    answer({"public_url": value})

    with caplog.at_level(logging.DEBUG):
        assert await config_values.admin_overlay(env=ENV) == {}

    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1, "one refusal is one line"
    logged = warnings[0].getMessage()
    assert "public_url" in logged
    assert "https" in logged, "the line names the rule the value broke"
    assert value not in logged
    assert "cloud.example.com" not in logged


@pytest.mark.anyio
@respx.mock
async def test_the_default_in_code_survives_this_validation() -> None:
    """Otherwise the fallback of every unconfigured installation would be the trap itself."""
    answer({"public_url": config.DEFAULT_PUBLIC_URL})

    assert await config_values.admin_overlay(env=ENV) == {
        config.ENV_PUBLIC_URL: config.DEFAULT_PUBLIC_URL
    }


# --- the derived address of BL-17: <NEXTCLOUD_URL>/exapps/<APP_ID> ------------------
#
# ``derived_public_url`` is the third link of the precedence chain of plan 05-01: it only
# speaks when neither the admin form nor ``NC_MCP_PUBLIC_URL`` produced an address, and its
# candidate runs through the same validation core as a value an administrator typed.
# Assumption A2 of phase 05 (AppAPI may hand this container an http or internal
# ``NEXTCLOUD_URL``) is answered with validation instead of trust: such a value derives
# nothing and the fail-closed path stays. Everything here calls the function directly; the
# wiring into the start is held by ``test_exapp_entry.py``.


def derivation_env(nextcloud_url: str, app_id: str = APP_ID) -> dict[str, str]:
    """The two variables the derivation reads, and deliberately nothing else.

    No ``APP_SECRET`` and no ``NC_MCP_PUBLIC_URL``: the function has to fail soft on an
    incomplete deploy environment instead of raising like ``exapp_settings`` does, because
    it runs on every start, including the ones this chain exists for.
    """
    return {config.ENV_NEXTCLOUD_URL: nextcloud_url, config.ENV_APP_ID: app_id}


def test_the_derivation_is_published_in_all() -> None:
    """The catalogue rule of this module: what leaves it stands in ``__all__``."""
    assert "derived_public_url" in config_values.__all__


@pytest.mark.parametrize("base", ["https://cloud.example.com", "https://cloud.example.com/"])
def test_the_public_address_is_derived_from_nextcloud_url_and_the_app_id(base: str) -> None:
    """The AIO no-config case of BL-17: only ``NEXTCLOUD_URL`` is set, and it is enough.

    The form is the one ``scripts/bootstrap_exapp.sh`` already builds and
    ``docs/exapp-install.md`` documents: a HaRP ExApp is reachable under
    ``<nextcloud_url>/exapps/<appid>``, never under the instance root. A trailing slash on
    the input decides nothing, exactly as it decides nothing for an admin form value.
    """
    assert (
        config_values.derived_public_url(derivation_env(base))
        == "https://cloud.example.com/exapps/mcp_connector"
    )


def test_the_derived_address_leaves_in_one_spelling() -> None:
    """IN-03 applies to derived values too: one spelling of scheme and host, whatever came in.

    The value becomes the ``issuer`` and the prefix of ``resource``, and clients compare
    both character by character, so a derived value in a second spelling would be the same
    silent comparison failure the admin form value was cured of.
    """
    assert (
        config_values.derived_public_url(derivation_env("HTTPS://Cloud.Example.COM/"))
        == "https://cloud.example.com/exapps/mcp_connector"
    )


def test_a_non_loopback_http_nextcloud_url_derives_nothing() -> None:
    """Assumption A2, answered: an AppAPI http downgrade or an internal name derives nothing.

    This is exactly the RFC 8414 rule of CR-01, applied to the derived candidate: an issuer
    has to be https unless it points at loopback, so a value like the AIO-internal container
    name never becomes a silent broken default.
    """
    assert config_values.derived_public_url(derivation_env("http://nextcloud-aio-apache")) is None


def test_a_loopback_nextcloud_url_still_derives() -> None:
    """The rule refuses http, it does not refuse development (the measured local topology)."""
    assert (
        config_values.derived_public_url(derivation_env("http://127.0.0.1:8081"))
        == "http://127.0.0.1:8081/exapps/mcp_connector"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "not a url",
        "ftp://x",
        "https://user:pass@cloud.example.com",
        "https://cloud.example.com:99999",
        "https://cloud.example.com:0",
        "https://[::1",
    ],
    ids=[
        "empty",
        "whitespace only",
        "not a url",
        "a scheme that is not http",
        "credentials in the URL",
        "a port above the range",
        "a port below the range",
        "an unreadable IPv6 bracket",
    ],
)
def test_garbage_nextcloud_url_values_derive_nothing(value: str) -> None:
    """Fail soft on every unusable value: ``None`` and never an exception at start time."""
    assert config_values.derived_public_url(derivation_env(value)) is None


def test_a_missing_app_id_derives_nothing() -> None:
    """Without ``APP_ID`` there is no suffix: the derivation is structurally ExApp-only."""
    assert (
        config_values.derived_public_url(derivation_env("https://cloud.example.com", app_id=""))
        is None
    )


def test_the_derivation_refusal_names_the_variable_and_never_the_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-05-03 without an exception: the value comes from the deploy environment, but a rule
    with one exemption is not a rule, and a container log is read by more than its author."""
    value = "http://nextcloud-aio-apache"

    with caplog.at_level(logging.DEBUG):
        assert config_values.derived_public_url(derivation_env(value)) is None

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert config.ENV_NEXTCLOUD_URL in logged, "the variable is named so the state is findable"
    assert config.ENV_PUBLIC_URL in logged, "and the line says the existing ways stay open"
    assert value not in logged
    assert "nextcloud-aio-apache" not in logged, "not even the host of the value"


# --- the overlay: the two switches ------------------------------------------------


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    ("raw", "normalised"),
    [
        (True, "on"),
        (False, "off"),
        ("true", "on"),
        ("false", "off"),
        ("True", "on"),
        ("False", "off"),
        ("1", "on"),
        ("0", "off"),
        ("on", "on"),
        ("off", "off"),
        ("yes", "on"),
        ("no", "off"),
        ("  ON  ", "on"),
    ],
)
async def test_every_understood_switch_spelling_becomes_on_or_off(
    raw: object, normalised: str
) -> None:
    """One spelling reaches the reader, whatever Nextcloud stored for the checkbox."""
    answer({"oauth_dcr": raw, "oauth_cimd": raw, "oauth_allowlist_only": raw})

    assert await config_values.admin_overlay(env=ENV) == {
        registry.ENV_DCR: normalised,
        registry.ENV_CIMD: normalised,
        registry.ENV_ALLOWLIST_ONLY: normalised,
    }


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("raw", ["maybe", "enabled", "-1", "2", "onoff"])
async def test_an_unknown_switch_value_is_dropped_and_logged(
    caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    """No silent default: the same reason ``registry._switch`` logs instead of guessing."""
    answer({"oauth_dcr": raw})

    with caplog.at_level(logging.DEBUG):
        overlay = await config_values.admin_overlay(env=ENV)

    assert overlay == {}
    assert "oauth_dcr" in "\n".join(record.getMessage() for record in caplog.records)


# --- the overlay: blanks and the client list --------------------------------------


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
async def test_a_blank_value_is_not_set_and_lets_the_env_win(blank: str) -> None:
    """The precedence rule needs this: admin value, then ``NC_MCP_*``, then the default."""
    answer({"public_url": blank, "oauth_dcr": blank, "oauth_allowed_clients": blank})

    assert await config_values.admin_overlay(env=ENV) == {}


@pytest.mark.anyio
@respx.mock
async def test_the_client_list_passes_through_unchanged() -> None:
    """``registry._entries`` splits, strips and deduplicates. Doing it twice would differ."""
    raw = "claude-desktop, https://claude.ai/api/mcp/auth_callback ,claude-desktop"
    answer({"oauth_allowed_clients": raw})

    assert await config_values.admin_overlay(env=ENV) == {registry.ENV_ALLOWED_CLIENTS: raw.strip()}


@pytest.mark.anyio
@respx.mock
async def test_all_seven_values_travel_together() -> None:
    """The whole overlay of a fully configured instance, in the spelling of the env."""
    answer(
        {
            "public_url": ADMIN_URL,
            "oauth_dcr": "false",
            "oauth_cimd": "false",
            "oauth_allowlist_only": "true",
            "oauth_allowed_clients": "claude-desktop",
            "talk_send": "false",
            "audit_log": "true",
        }
    )

    assert await config_values.admin_overlay(env=ENV) == {
        config.ENV_PUBLIC_URL: ADMIN_URL,
        registry.ENV_DCR: "off",
        registry.ENV_CIMD: "off",
        registry.ENV_ALLOWLIST_ONLY: "on",
        registry.ENV_ALLOWED_CLIENTS: "claude-desktop",
        config.ENV_TALK_SEND: "off",
        config.ENV_AUDIT_LOG: "on",
    }


# --- the switch of TALK-04 on the read path (layer 2 of success criterion 5) --------


@pytest.mark.anyio
@respx.mock
async def test_a_stored_talk_switch_of_zero_becomes_an_overlay_of_off() -> None:
    """What an unticked checkbox in the form has to arrive as in this process.

    ``0`` is the spelling Nextcloud stores for an unticked box, and ``off`` is the one
    spelling that leaves this module, because ``config.talk_send_enabled`` reads the value
    out of the process environment and not out of a form.
    """
    answer({"talk_send": "0"})

    assert await config_values.admin_overlay(env=ENV) == {
        config.ENV_TALK_SEND: config_values.SWITCH_OFF
    }


@pytest.mark.anyio
@respx.mock
async def test_a_stored_talk_switch_of_one_becomes_an_overlay_of_on() -> None:
    """The other direction, so the value is never assumed from the absence of the other."""
    answer({"talk_send": "1"})

    assert await config_values.admin_overlay(env=ENV) == {
        config.ENV_TALK_SEND: config_values.SWITCH_ON
    }


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("raw", ["vielleicht", "maybe", "onoff", "2", "-1"])
async def test_an_unreadable_talk_switch_is_refused_without_naming_the_value(
    caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    """T-09-10: the value came in over HTTP, so the log names the field and nothing else.

    Refused rather than guessed, and the environment stays in force for this key, which is
    what makes the precedence rule work in both directions.
    """
    answer({"talk_send": raw})

    with caplog.at_level(logging.DEBUG):
        values = await config_values.admin_values(env=ENV)

    assert values.overlay == {}
    assert values.refused == frozenset({"talk_send"})
    # Only the records of this module: the httpx INFO line of the mocked round trip carries
    # the request URL, and a digit out of that path would answer the negative claim below.
    logged = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "mcp_connector.exapp.config_values"
    )
    assert "talk_send" in logged
    assert raw not in logged


@pytest.mark.anyio
@respx.mock
async def test_one_unusable_value_never_drops_the_others() -> None:
    """Per key validation: a typo in one field is not an outage of the other five."""
    answer(
        {
            "public_url": "https://cloud.example.test/x#frag",
            "oauth_dcr": "off",
            "oauth_allowed_clients": "claude-desktop",
        }
    )

    assert await config_values.admin_overlay(env=ENV) == {
        registry.ENV_DCR: "off",
        registry.ENV_ALLOWED_CLIENTS: "claude-desktop",
    }


@pytest.mark.anyio
@respx.mock
async def test_an_unreachable_nextcloud_is_an_empty_overlay() -> None:
    """The deploy environment stays in force, and the installation keeps running."""
    respx.post(READ_URL).mock(side_effect=httpx.ConnectError("no route to nextcloud"))

    assert await config_values.admin_overlay(env=ENV) == {}


# --- the client of a caller that has no shared client to use (plan 05-04) ------------


@pytest.mark.anyio
@respx.mock
async def test_a_handed_in_client_is_the_one_that_carries_the_read() -> None:
    """Plan 05-04 reads these values before the server exists, in a loop of its own.

    ``shared_client`` binds a connection pool to the event loop it is first used in, and the
    loop of that read is closed again as soon as it returns, so the pool would be unusable in
    the loop uvicorn opens afterwards. The parameter is what lets that caller bring a short
    lived client instead, and the default stays the shared one for every other caller.
    """
    route = answer({"public_url": ADMIN_URL})

    async with httpx.AsyncClient(follow_redirects=False) as client:
        values = await config_values.read_values(env=ENV, client=client)
        overlay = await config_values.admin_overlay(env=ENV, client=client)

    assert values == {"public_url": ADMIN_URL}
    assert overlay == {config.ENV_PUBLIC_URL: ADMIN_URL}
    assert route.call_count == 2
    assert all(call.request.url.path.endswith("/ex-app/config/get-values") for call in route.calls)


@pytest.mark.anyio
@respx.mock
async def test_a_handed_in_client_is_used_instead_of_the_shared_one() -> None:
    """The proof that the parameter is not decoration: the shared client is never asked."""
    answer({"public_url": ADMIN_URL})
    asked: list[str] = []

    def refuse() -> httpx.AsyncClient:  # pragma: no cover - called means the check failed
        asked.append("shared")
        raise AssertionError("the shared client was used although one was handed in")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config_values, "shared_client", refuse)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            overlay = await config_values.admin_overlay(env=ENV, client=client)

    assert overlay == {config.ENV_PUBLIC_URL: ADMIN_URL}
    assert asked == []


@pytest.mark.anyio
@respx.mock
async def test_a_handed_in_client_fails_as_softly_as_the_shared_one() -> None:
    """Every failure of this module is an empty result, whichever client carried it."""
    respx.post(READ_URL).mock(side_effect=httpx.ConnectError("no route to nextcloud"))

    async with httpx.AsyncClient(follow_redirects=False) as client:
        assert await config_values.admin_overlay(env=ENV, client=client) == {}

"""The admin Declarative Settings form of BL-06 and its hook in the enable handler.

Nothing here opens a socket: the outgoing OCS registration is answered by respx, and the
lifecycle checks build their own Starlette app from ``lifecycle_routes`` exactly as
``test_exapp_lifecycle.py`` does. That file stays untouched on purpose, so plan 05-06 can
work on it without meeting this plan in the same lines.

Both forms register on the same OCS route, which is why "both were registered" is asserted
as two calls with two form ids on the wire rather than as two respx routes: two routes for
one URL would only ever be one of them.

Threats covered: T-05-05 (a ``sensitive`` field would hand the ExApp an unreadable ICrypto
blob), T-05-06 (the security hint of BL-06 lives in the field itself), T-05-04 (a failing
registration never fills the ``error`` field, which would disable the app at once) and
T-05-03 (the app secret never reaches a log record).
"""

import base64
import json
import logging
import re

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp import (
    admin_settings,
    audit_verify,
    config_values,
    lifecycle,
    settings_form,
)
from mcp_connector.exapp.ui import strings

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
USER = "alice"
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

SETTINGS_URL = f"{BASE_URL}/ocs/v2.php/apps/app_api/api/v1/ui/settings"

#: The complete type list of Declarative Settings, verified against nextcloud/server
#: stable34 ``lib/public/Settings/DeclarativeSettingsTypes.php``. There is no button type,
#: which is why the destructive action of this phase is an occ command (plan 05-06).
FIELD_TYPES = (
    "text",
    "password",
    "email",
    "tel",
    "url",
    "number",
    "checkbox",
    "multi-checkbox",
    "radio",
    "select",
    "multi-select",
)

#: The four claims of D-v1.5-02 that no public sentence of this project makes, each with the
#: wordings it would arrive in in the two other languages this project publishes in. Written
#: as patterns and not as bare substrings on purpose: forbidden is the claim and not the word,
#: so a sentence may say that this record has no SIEM connection or that the regulation
#: concerns the operator, and "specification compliant" stays a legitimate phrase.
FORBIDDEN_CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("revisionssicher", re.compile(r"revisionssicher|tamper[\s-]*proof|audit[\s-]*proof", re.I)),
    ("AI-Act-konform", re.compile(r"ai[\s-]*act[\s-]*(konform|compliant|conforme)", re.I)),
    ("DSGVO-konform", re.compile(r"(dsgvo|gdpr|rgpd)[\s-]*(konform|compliant|conforme)", re.I)),
    ("SIEM-zertifiziert", re.compile(r"siem[\s-]*(zertifiziert|certified|certifi)", re.I)),
)

#: The word for the other extent of recording, the one that would mean parameter values and
#: result content. This app has no code for it and the form therefore must not name it, in a
#: field text, in a field type or in an option list. A word form with boundaries, because the
#: same letters sit inside ordinary English words this form is free to use.
LEVEL_WORD = re.compile(r"\bfull\b")


def appapi_headers(user: str = USER, secret: str = APP_SECRET) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


def client() -> TestClient:
    """A fresh app per call: one Starlette instance is one lifespan."""
    return TestClient(Starlette(routes=lifecycle.lifecycle_routes(ENV)))


def form_ids(route: respx.Route) -> list[str]:
    """The form id of every registration this route saw, in order."""
    return [json.loads(call.request.content)["formScheme"]["id"] for call in route.calls]


# --- the schema on the wire --------------------------------------------------------


@pytest.mark.anyio
@respx.mock
async def test_the_admin_form_sits_in_the_admin_section() -> None:
    """``section_type`` admin is what makes AppAPI store the value as ExApp configuration."""
    route = respx.post(SETTINGS_URL).mock(
        return_value=httpx.Response(200, json={"ocs": {"meta": {"status": "ok"}}})
    )

    await admin_settings.register_admin_form(env=ENV)

    assert route.call_count == 1
    scheme = json.loads(route.calls.last.request.content)["formScheme"]
    assert scheme["id"] == "mcp_connector_admin"
    assert scheme["id"] == admin_settings.ADMIN_FORM_ID
    assert scheme["id"] != settings_form.FORM_ID, "two forms, two ids, one insertOrUpdate key"
    assert scheme["priority"] == 10
    assert scheme["section_type"] == "admin"
    assert scheme["section_id"] == "security"
    assert scheme["title"] == strings.ADMIN_SETTINGS_TITLE
    assert scheme["description"] == strings.ADMIN_SETTINGS_DESCRIPTION


@pytest.mark.anyio
@respx.mock
async def test_the_eight_fields_are_the_eight_config_keys_in_order() -> None:
    """The field id IS the configuration key, so form and read path cannot drift apart.

    Five since the audit of the v1.0 milestone: ``NC_MCP_OAUTH_CIMD`` existed as a deploy
    variable, as a manifest declaration and as a documented sentence, and in no part of this
    chain. An installation from the app store never gets a deploy variable, so that switch
    was one no store installation could reach at all (finding B-1).

    Six since phase 9: ``talk_send`` is the same case for the switch of TALK-04, and it came
    after the four OAuth values because those belong together and a Talk switch between them
    would tear that grouping apart. Seven since phase 18: ``audit_log`` is the switch of D-14
    and sits last, because it is about this app watching itself and not about who reaches it.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    assert [field["id"] for field in fields] == [
        "public_url",
        "oauth_dcr",
        "oauth_cimd",
        "oauth_allowlist_only",
        "oauth_allowed_clients",
        "talk_send",
        "audit_log",
        "files_update",
    ]
    assert tuple(field["id"] for field in fields) == config_values.CONFIG_KEYS
    assert [field["type"] for field in fields] == [
        "url",
        "checkbox",
        "checkbox",
        "checkbox",
        "text",
        "checkbox",
        "checkbox",
        "checkbox",
    ]


@pytest.mark.anyio
@respx.mock
async def test_no_field_carries_a_type_outside_the_verified_list() -> None:
    """And none of them is a button, because Declarative Settings have no button type."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    body = route.calls.last.request.content.decode()
    fields = json.loads(body)["formScheme"]["fields"]
    for field in fields:
        assert field["type"] in FIELD_TYPES
    assert "button" not in body


@pytest.mark.anyio
@respx.mock
async def test_the_body_never_carries_the_word_sensitive() -> None:
    """T-05-05: AppAPI would encrypt such a value with ICrypto and hand us back a blob.

    Asserted on the body as a string and not per field, so no spelling of the flag and no
    nesting can slip through.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    assert "sensitive" not in route.calls.last.request.content.decode().lower()


@pytest.mark.anyio
@respx.mock
async def test_every_field_carries_a_title_a_description_and_a_default() -> None:
    """The documented field shape. A missing default is a registration Nextcloud refuses."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    for field in fields:
        assert field["title"]
        assert field["description"]
        assert "default" in field


@pytest.mark.anyio
@respx.mock
async def test_the_dcr_field_carries_the_security_hint_of_bl_06() -> None:
    """T-05-06: the hint belongs where the switch is, not only in docs/oauth-setup.md."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    dcr = next(field for field in fields if field["id"] == "oauth_dcr")
    assert dcr["description"] == strings.ADMIN_FIELD_DCR_DESCRIPTION
    lowered = dcr["description"].lower()
    assert "public" in lowered
    assert "allow list" in lowered or "allowlist" in lowered


@pytest.mark.anyio
@respx.mock
async def test_the_cimd_field_is_a_checkbox_that_ships_on() -> None:
    """B-1: the fifth field, and the state it shows is the one the code runs on.

    ``registry.client_policy`` reads ``NC_MCP_OAUTH_CIMD`` with ``default=True``, so a form
    that showed this box unticked would tell an administrator the opposite of what is in
    force before she has touched anything.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    cimd = next(field for field in fields if field["id"] == "oauth_cimd")
    assert cimd["type"] == "checkbox"
    assert cimd["default"] is True
    assert cimd["title"] == strings.ADMIN_FIELD_CIMD_LABEL
    assert cimd["description"] == strings.ADMIN_FIELD_CIMD_DESCRIPTION
    assert "sensitive" not in cimd


@pytest.mark.anyio
@respx.mock
async def test_the_talk_send_field_is_a_checkbox_that_ships_on() -> None:
    """TALK-04, layer 1: the sixth field, and the state it shows is the one in force.

    ``config.talk_send_enabled`` answers True for an unset variable, so a box shown unticked
    would tell an administrator the opposite of what her installation does before she has
    touched anything. And no spelling of ``sensitive``: AppAPI would encrypt the value with
    the server secret, and this app would read back a blob it cannot open (T-05-05), which
    for a switch means it could never be read as off either.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    # Looked up by id and no longer taken as the last field: since phase 18 the last one is
    # the audit switch, and a position is not what this check is about anyway.
    talk_send = next(field for field in fields if field["id"] == "talk_send")
    assert talk_send["id"] == "talk_send"
    assert talk_send["type"] == "checkbox"
    assert talk_send["default"] is True
    assert talk_send["title"] == strings.ADMIN_FIELD_TALK_SEND_LABEL
    assert talk_send["description"] == strings.ADMIN_FIELD_TALK_SEND_DESCRIPTION
    assert "sensitive" not in json.dumps(talk_send).lower()


@pytest.mark.anyio
@respx.mock
async def test_the_talk_send_description_names_the_reading_side_and_the_cycle() -> None:
    """The two sentences an administrator needs before she closes this switch.

    An administrator who reads "send" as "Talk" switches off a reading capability she never
    meant to touch, and one who expects an immediate effect measures a state this app does
    not have until it has been disabled and enabled once (the price named in
    ``entry_exapp._resolved_env``).
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    description = next(field for field in fields if field["id"] == "talk_send")["description"]
    lowered = description.lower()
    assert "reading is not affected" in lowered
    assert "disable and enable this app again" in lowered


@pytest.mark.anyio
@respx.mock
async def test_the_audit_log_field_is_a_checkbox_that_ships_off() -> None:
    """D-14, the one field of this form whose shipped state is off, and why it has to be.

    ``config.audit_log_enabled`` answers False for an unset variable, so a box shown ticked
    would tell an administrator that her installation is recording when it is not. The
    direction matters more here than at any other field of this form: what this switch starts
    is a record about named people, and the promise of D-14 is that no installation ever
    keeps one nobody asked for.

    And no spelling of ``sensitive``: AppAPI would encrypt the value with the server secret
    and this app would read back a blob it cannot open (T-05-05, T-18-19), which for this
    switch means it could never be read as off either.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    audit_log = next(field for field in fields if field["id"] == "audit_log")
    assert audit_log["id"] == "audit_log"
    assert audit_log["type"] == "checkbox"
    assert audit_log["default"] is False
    assert audit_log["title"] == strings.ADMIN_FIELD_AUDIT_LOG_LABEL
    assert audit_log["description"] == strings.ADMIN_FIELD_AUDIT_LOG_DESCRIPTION
    assert "sensitive" not in json.dumps(audit_log).lower()


@pytest.mark.anyio
@respx.mock
async def test_the_files_update_field_is_a_checkbox_that_ships_off() -> None:
    """The files update switch is opt-in and therefore ships disabled."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    files_update = next(field for field in fields if field["id"] == "files_update")
    assert files_update["type"] == "checkbox"
    assert files_update["default"] is False
    assert files_update["title"] == strings.ADMIN_FIELD_FILES_UPDATE_LABEL
    assert files_update["description"] == strings.ADMIN_FIELD_FILES_UPDATE_DESCRIPTION
    assert "sensitive" not in json.dumps(files_update).lower()


@pytest.mark.anyio
@respx.mock
async def test_the_audit_log_description_says_what_is_kept_and_what_is_not() -> None:
    """The six duties of the long version (AUDIT-05), and the claims it must not make.

    Phase 18 wrote the short version and said so: what a row contains, what it never
    contains, and the activation cycle. Phase 19 owns the rest, and it is here now, so this
    test grew instead of being replaced. The three fields the short version kept quiet about
    are the review finding IN-06 of phase 18: an administrator who reads only "the name of
    the tool" does not learn that the names of the parameters, the reason of a refusal and
    the duration of the call are written down as well.

    The limit description is the pledge of D-v1.5-02, the works council sentence is
    D-v1.5-04, and both of them are the reason this switch can be judged before it is
    flipped rather than after the first record exists.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    description = next(field for field in fields if field["id"] == "audit_log")["description"]
    lowered = description.lower()
    # Duty 1, what a row holds, with the three fields of IN-06.
    assert "the names of the parameters, never their values" in lowered
    assert "identifier of the reason" in lowered, "a refusal is a fixed identifier, not a text"
    assert "how long it took" in lowered, "the duration of the call is stored too"
    # Duty 2, what a row never holds. The first two wordings are the ones phase 18 wrote.
    assert "no parameter value" in lowered
    assert "no part of a result" in lowered
    assert "network address" in lowered
    assert "user agent" in lowered
    assert "text of an error message" in lowered
    # Duty 3, the limit, held against the console sentence in its own test below.
    assert "changed or removed unnoticed" in lowered
    assert "recompute" in lowered
    # Duty 4, D-v1.5-04. A hint, and it says so, because an app cannot judge this.
    assert "works council" in lowered
    assert "not legal advice" in lowered
    # Duty 5, retention and what a row outlives, in the numbers of ``audit/store.py``.
    assert "180 days" in lowered
    assert "100 mb" in lowered
    assert "purge" in lowered, "and that a row outlives it"
    # Duty 6, the cycle every other field of this form spells as well.
    assert "disable and enable this app again" in lowered
    # The four words AUDIT-06 keeps out of every public text of this project, checked at the
    # place a new public sentence enters it.
    for forbidden in ("revisionssicher", "ai-act", "dsgvo", "siem"):
        assert forbidden not in lowered
    # And the same four claims in the two other languages this project publishes in: the
    # German compounds alone would let "GDPR compliant" or "conforme au RGPD" through, and a
    # claim is forbidden in whatever language it is made.
    for claim, pattern in FORBIDDEN_CLAIMS:
        assert pattern.search(description) is None, f"the description claims to be {claim}"


@pytest.mark.anyio
@respx.mock
async def test_the_limit_of_the_record_reads_the_same_in_the_form_and_in_the_console() -> None:
    """One limit, two places, and neither may say more than the other.

    ``audit_verify.LIMIT_SENTENCE`` is the last line of every answer of the check command,
    and the description of this switch says the same thing to whoever decides about the
    record in the first place. If one of the two is ever softened, the other keeps the
    promise the code cannot hold, so both are asserted on their load bearing words here
    rather than each on its own.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    description = next(field for field in fields if field["id"] == "audit_log")["description"]
    for load_bearing in ("changed or removed unnoticed", "recompute"):
        assert load_bearing in description.lower(), "the form half of the limit"
        assert load_bearing in audit_verify.LIMIT_SENTENCE.lower(), "the console half of it"


@pytest.mark.anyio
@respx.mock
async def test_no_field_of_the_form_offers_a_level_of_recording() -> None:
    """There is one extent of what is recorded, so the form must not read like a choice.

    The record holds parameter names and never values (D-06, AUDIT-01). A field text, a
    field type or an option list carrying the word for the other extent would advertise a
    setting this app has no code for, and an administrator would switch it on believing a
    promise nobody made. Asserted as a word and not as a substring, because a legitimate
    sentence elsewhere on this form may well end up containing it inside another word.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    assert len(fields) == 8, "every field of the form is walked, not a subset of it"
    for field in fields:
        assert LEVEL_WORD.search(json.dumps(field).lower()) is None, (
            f"{field['id']} offers a level of recording this app cannot deliver"
        )


@pytest.mark.anyio
@respx.mock
async def test_both_switch_descriptions_name_the_coupling_between_them() -> None:
    """W-9: the policy is one derived answer, so neither field may read as independent.

    ``cimd_enabled = this switch AND the DCR switch``, and a checkbox has no third position
    for "on but closed by the other one". An administrator who reads two independent
    switches turns this one on while self registration is off and then measures a state the
    code never produces, with no line anywhere explaining it.
    """
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    cimd = next(field for field in fields if field["id"] == "oauth_cimd")
    dcr = next(field for field in fields if field["id"] == "oauth_dcr")
    assert "switch above" in cimd["description"], "the coupling, from the CIMD side"
    assert "both ways are closed" in cimd["description"].lower()
    assert "leaves self registration exactly as it is" in cimd["description"], (
        "and the direction that does not hold"
    )
    assert "document" in dcr["description"].lower(), "the coupling, from the DCR side"


@pytest.mark.anyio
@respx.mock
async def test_the_public_url_field_carries_an_example_and_the_restart_step() -> None:
    """The one value without which no client can finish a connection (pitfall 2)."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    fields = json.loads(route.calls.last.request.content)["formScheme"]["fields"]
    public = next(field for field in fields if field["id"] == "public_url")
    assert "https://cloud.example.com/exapps/mcp_connector" in public["description"]
    assert "enable" in public["description"].lower()


@pytest.mark.anyio
@respx.mock
async def test_the_form_never_carries_an_internal_host_name() -> None:
    """The description and the doc_url are read by a browser, not by us (T-04-40)."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    scheme = json.loads(route.calls.last.request.content)["formScheme"]
    assert scheme["doc_url"] == f"{PUBLIC_URL}/connections"
    assert BASE_URL not in route.calls.last.request.content.decode()


@pytest.mark.anyio
@respx.mock
async def test_a_fresh_installation_gets_a_link_that_leads_somewhere() -> None:
    """IN-03 of 05-REVIEW.md, first pass: the form that fixes the state carried a dead link.

    Before any address is set, ``config.public_url`` answers the loopback default, so the
    ``doc_url`` of this form pointed at ``http://127.0.0.1:8765/connections``, which in a
    browser on the administrator's machine is her own machine and not this container. The
    form is exactly the place where that state is corrected, so the link goes to the public
    documentation until the app knows its own address.
    """
    env = {name: value for name, value in ENV.items() if name != config.ENV_PUBLIC_URL}
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=env)

    scheme = json.loads(route.calls.last.request.content)["formScheme"]
    assert scheme["doc_url"] == admin_settings.PUBLIC_DOCS_URL
    assert config.DEFAULT_PUBLIC_URL not in route.calls.last.request.content.decode(), (
        "the default in code is no address to send an administrator to"
    )


@pytest.mark.anyio
@respx.mock
async def test_the_registration_runs_in_the_app_context() -> None:
    """The AppAPI headers with an empty user: the app speaks about itself."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    await admin_settings.register_admin_form(env=ENV)

    sent = route.calls.last.request
    assert (
        sent.headers["AUTHORIZATION-APP-API"]
        == base64.b64encode(f":{APP_SECRET}".encode()).decode()
    )
    assert sent.headers["EX-APP-ID"] == APP_ID
    assert sent.headers["EX-APP-VERSION"] == APP_VERSION
    assert sent.headers["AA-VERSION"] == "34.0.3"
    assert sent.headers["OCS-APIRequest"] == "true"


# --- the error model: one attempt, one log line, never a raise ---------------------


@pytest.mark.anyio
@respx.mock
async def test_a_registration_that_cannot_be_delivered_is_one_log_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx.post(SETTINGS_URL).mock(side_effect=httpx.ConnectError("no route to nextcloud"))

    with caplog.at_level(logging.DEBUG):
        await admin_settings.register_admin_form(env=ENV)

    assert [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("status_code", [400, 401, 500])
async def test_a_refused_registration_is_one_log_line(
    caplog: pytest.LogCaptureFixture, status_code: int
) -> None:
    respx.post(SETTINGS_URL).mock(return_value=httpx.Response(status_code, json={}))

    with caplog.at_level(logging.DEBUG):
        await admin_settings.register_admin_form(env=ENV)

    assert [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.anyio
@respx.mock
async def test_a_broken_deploy_environment_is_not_an_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``exapp_settings`` raises when a variable is missing, and this function never does."""
    broken = {key: value for key, value in ENV.items() if key != config.ENV_APP_SECRET}
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    with caplog.at_level(logging.DEBUG):
        await admin_settings.register_admin_form(env=broken)

    assert not route.called


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("outcome", ["ok", "refused", "unreachable"])
async def test_the_app_secret_never_reaches_a_log_record(
    caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    route = respx.post(SETTINGS_URL)
    if outcome == "unreachable":
        route.mock(side_effect=httpx.ConnectError("no route to nextcloud"))
    else:
        route.mock(return_value=httpx.Response(200 if outcome == "ok" else 500, json={}))

    with caplog.at_level(logging.DEBUG):
        await admin_settings.register_admin_form(env=ENV)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert APP_SECRET not in logged
    assert base64.b64encode(f":{APP_SECRET}".encode()).decode() not in logged


# --- the hook in the enable handler -----------------------------------------------


@respx.mock
def test_enabling_the_app_registers_both_forms() -> None:
    """One route, two calls: the personal signpost and the admin form of this plan."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    with client() as http:
        response = http.put("/enabled?enabled=1", headers=appapi_headers())

    assert response.status_code == 200
    assert response.json() == {"error": ""}
    assert response.headers["cache-control"] == "no-store"
    assert form_ids(route) == [settings_form.FORM_ID, admin_settings.ADMIN_FORM_ID]


@respx.mock
def test_disabling_the_app_registers_nothing() -> None:
    """AppAPI hands out the forms of enabled apps only, so a disable has nothing to do."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    with client() as http:
        response = http.put("/enabled?enabled=0", headers=appapi_headers())

    assert response.status_code == 200
    assert not route.called


@respx.mock
def test_a_failing_admin_registration_leaves_the_error_field_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pitfall 11 of phase 2: a non empty error field disables the app again at once."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    async def boom(*, env: object = None) -> None:
        raise httpx.ConnectError("nextcloud is not reachable")

    monkeypatch.setattr(admin_settings, "register_admin_form", boom)

    with client() as http:
        response = http.put("/enabled?enabled=1", headers=appapi_headers())

    assert response.status_code == 200
    assert response.json() == {"error": ""}
    assert response.headers["cache-control"] == "no-store"
    assert form_ids(route) == [settings_form.FORM_ID], "the other form still went out"


@respx.mock
def test_a_failing_personal_registration_does_not_stop_the_admin_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two registrations, two try blocks: one failure never costs the other one."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    async def boom(*, env: object = None) -> None:
        raise httpx.ConnectError("nextcloud is not reachable")

    monkeypatch.setattr(settings_form, "register_settings_form", boom)

    with client() as http:
        response = http.put("/enabled?enabled=1", headers=appapi_headers())

    assert response.status_code == 200
    assert response.json() == {"error": ""}
    assert form_ids(route) == [admin_settings.ADMIN_FORM_ID]


@respx.mock
def test_a_rejected_enable_registers_nothing() -> None:
    """No headers, no registration: the guard runs before anything reaches Nextcloud."""
    route = respx.post(SETTINGS_URL).mock(return_value=httpx.Response(200, json={}))

    with client() as http:
        response = http.put("/enabled?enabled=1")

    assert response.status_code == 401
    assert not route.called


# --- the text catalogue -----------------------------------------------------------


def test_the_new_texts_are_published_in_all() -> None:
    """``__all__`` is what a text catalogue is, and what keeps the dead code gate green."""
    for name in (
        "ADMIN_SETTINGS_TITLE",
        "ADMIN_SETTINGS_DESCRIPTION",
        "ADMIN_SETTINGS_PLACE",
        "ADMIN_FIELD_PUBLIC_URL_LABEL",
        "ADMIN_FIELD_PUBLIC_URL_DESCRIPTION",
        "ADMIN_FIELD_DCR_LABEL",
        "ADMIN_FIELD_DCR_DESCRIPTION",
        "ADMIN_FIELD_CIMD_LABEL",
        "ADMIN_FIELD_CIMD_DESCRIPTION",
        "ADMIN_FIELD_ALLOWLIST_LABEL",
        "ADMIN_FIELD_ALLOWLIST_DESCRIPTION",
        "ADMIN_FIELD_ALLOWED_CLIENTS_LABEL",
        "ADMIN_FIELD_ALLOWED_CLIENTS_DESCRIPTION",
        "SETUP_PUBLIC_URL_TITLE",
        "SETUP_PUBLIC_URL_BODY",
        "SETUP_PUBLIC_URL_HINT",
    ):
        assert name in strings.__all__, f"{name} is missing from the catalogue"
        assert getattr(strings, name)


def test_the_setup_copy_names_the_place_and_the_restart_step() -> None:
    """What plan 05-04 shows when no public URL is configured anywhere."""
    assert strings.ADMIN_SETTINGS_PLACE in strings.SETUP_PUBLIC_URL_BODY
    assert "enable" in strings.SETUP_PUBLIC_URL_BODY.lower()


@pytest.mark.parametrize(
    "name",
    [
        "ADMIN_SETTINGS_TITLE",
        "ADMIN_SETTINGS_DESCRIPTION",
        "ADMIN_FIELD_PUBLIC_URL_DESCRIPTION",
        "ADMIN_FIELD_DCR_DESCRIPTION",
        "ADMIN_FIELD_CIMD_DESCRIPTION",
        "ADMIN_FIELD_ALLOWLIST_DESCRIPTION",
        "ADMIN_FIELD_ALLOWED_CLIENTS_DESCRIPTION",
        # The longest sentence of the whole form, and the newest, so it is held by the same
        # rule as the rest of the catalogue rather than by a review.
        "ADMIN_FIELD_AUDIT_LOG_LABEL",
        "ADMIN_FIELD_AUDIT_LOG_DESCRIPTION",
        "SETUP_PUBLIC_URL_TITLE",
        "SETUP_PUBLIC_URL_BODY",
        "SETUP_PUBLIC_URL_HINT",
    ],
)
def test_no_new_sentence_carries_an_em_dash_or_an_emoji(name: str) -> None:
    """The copy rules of this project, held by a test rather than by a review."""
    text: str = getattr(strings, name)
    # Escaped rather than written out: the dashes this project forbids are exactly the two
    # characters a linter would flag as ambiguous in a source file (RUF001).
    assert chr(0x2014) not in text, "em dash"
    assert chr(0x2013) not in text, "en dash"
    assert text.isascii(), "English copy only, and nothing that renders as an icon"

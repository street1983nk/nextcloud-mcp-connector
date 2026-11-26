"""Unit tests for the OCS layer and the app detection behind graceful degradation.

Covered on purpose, all paths: the two mandatory headers (D-18), the fixture of a real
capabilities answer, an instance without Notes and without Deck, an HTML login page
instead of JSON, the app-JSON error format of Notes and Deck (pitfall 9), the exact
wording of the missing-app error (D-15) and the cache behaviour, including the proof that
the cache only saves latency and never changes an answer (D-20).

Two of them belong to Talk and are worth naming here. The app detection reads the section
``spreed`` and treats an empty array as absent, because that is what an instance sends when
Talk is installed but switched off for the asking account. And ``parse_ocs`` accepts an
envelope with the created status: the Talk send route documents 201 as its only success, and
without it a successfully sent message would read as a failure (T1).

The Mail block at the end covers the second detection channel, which is the one thing in this
module that is not read out of the capabilities answer at all: Mail has no section there, so
the navigation of the signed in user answers instead. Four states are covered (listed,
not listed, empty, not a list), plus the two properties that make the channel affordable: the
extra request happens once per cache window and only for Mail, and it does not extend the
lifetime of the snapshot it is written into.
"""

import dataclasses
import json
from pathlib import Path

import httpx
import pytest
import respx

from mcp_connector.errors import AppMissingError, ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.clients import ocs
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"

# The second detection channel, frozen as a literal: it is a core OCS route and not an app
# route, which is the whole reason it can answer a question about an app that may be absent.
NAVIGATION_URL = f"{BASE}/ocs/v2.php/core/navigation/apps"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

#: A navigation entry as Nextcloud 34.0.3 sends it, field for field.
MAIL_ENTRY = {
    "id": "mail",
    "app": "mail",
    "type": "link",
    "name": "Mail",
    "order": 3,
    "href": f"{BASE}/index.php/apps/mail/",
    "icon": f"{BASE}/index.php/apps/mail/img/app.svg",
    "active": False,
    "default": False,
    "classes": "",
    "unread": 0,
}

FILES_ENTRY = {
    "id": "files",
    "app": "files",
    "type": "link",
    "name": "Dateien",
    "order": 0,
    "href": f"{BASE}/index.php/apps/files/",
    "active": False,
    "unread": 0,
}

LOGIN_PAGE = (
    '<!DOCTYPE html>\n<html class="ng-csp" data-placeholder-focus="false">\n'
    "<head><title>Login - Nextcloud</title></head>\n"
    '<body><form method="post" name="login"><input name="user"></form></body></html>\n'
)


def capabilities_fixture() -> dict:
    return json.loads((FIXTURES / "ocs_capabilities.json").read_text(encoding="utf-8"))


def envelope(data: object, statuscode: int = 200, message: str = "OK") -> dict:
    """An OCS v2 envelope around any payload."""
    return {
        "ocs": {
            "meta": {"status": "ok", "statuscode": statuscode, "message": message},
            "data": data,
        }
    }


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    """Every test starts with an empty cache; leaking one would hide a real call."""
    capabilities.clear_cache()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.mark.anyio
async def test_every_ocs_request_carries_the_two_mandatory_headers(clients: NcClients) -> None:
    """D-18: without both headers Nextcloud answers with a login page, not with JSON."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        await capabilities.load(clients)

    request = route.calls[0].request
    assert request.headers["OCS-APIRequest"] == "true"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Authorization"].startswith("Basic ")


@pytest.mark.anyio
async def test_the_capabilities_fixture_reports_notes_and_deck(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        caps = await capabilities.load(clients)

    assert caps.notes_available is True
    assert caps.notes_api_versions == ("0.2", "1.3")
    assert caps.deck_available is True
    assert caps.deck_api_versions == ("1.0", "1.1")
    assert caps.can_create_boards is True


@pytest.mark.anyio
async def test_missing_keys_switch_the_flags_off_without_an_exception(clients: NcClients) -> None:
    """An instance without the optional apps is a normal instance, not an error."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=envelope({"capabilities": {"core": {}}}))
        )
        caps = await capabilities.load(clients)

    assert caps.notes_available is False
    assert caps.notes_api_versions == ()
    assert caps.deck_available is False
    assert caps.can_create_boards is False


@pytest.mark.anyio
async def test_a_deck_without_board_permission_is_reported_honestly(clients: NcClients) -> None:
    payload = envelope({"capabilities": {"deck": {"version": "1.18.3", "canCreateBoards": False}}})
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(200, json=payload))
        caps = await capabilities.load(clients)

    assert caps.deck_available is True
    assert caps.can_create_boards is False


@pytest.mark.anyio
async def test_an_enabled_tables_app_reports_both_api_generations(clients: NcClients) -> None:
    payload = envelope(
        {
            "capabilities": {
                "tables": {
                    "enabled": True,
                    "version": "2.2.2",
                    "apiVersions": ["1.0", "2.0"],
                    "features": ["favorite", "archive"],
                }
            }
        }
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(200, json=payload))
        caps = await capabilities.load(clients)

    assert caps.tables_available is True
    assert caps.tables_api_versions == ("1.0", "2.0")
    assert caps.has("tables") is True


@pytest.mark.anyio
async def test_an_installed_but_disabled_tables_app_counts_as_absent(clients: NcClients) -> None:
    """The one difference to Deck, and the reason the flag is not the section presence.

    Tables publishes an explicit ``enabled``. A section with ``enabled: false`` means the app
    is installed and switched off, and an app that is switched off answers no request, so
    treating the section as proof of availability would produce a 404 on an HTML page where a
    sentence belongs.
    """
    payload = envelope(
        {"capabilities": {"tables": {"enabled": False, "apiVersions": ["1.0", "2.0"]}}}
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(200, json=payload))
        caps = await capabilities.load(clients)

    assert caps.tables_available is False
    assert caps.has("tables") is False


@pytest.mark.anyio
async def test_an_instance_without_a_tables_section_reports_it_as_absent(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        caps = await capabilities.load(clients)

    assert caps.tables_available is False
    assert caps.tables_api_versions == ()


def test_a_single_api_version_string_is_tolerated_for_tables() -> None:
    """An instance that answers one version as a plain string is not a broken instance."""
    caps = capabilities.parse({"capabilities": {"tables": {"enabled": True, "apiVersions": "2.0"}}})
    assert caps.tables_available is True
    assert caps.tables_api_versions == ("2.0",)


@pytest.mark.anyio
async def test_a_talk_section_reports_its_features_and_the_chat_length_of_the_instance(
    clients: NcClients,
) -> None:
    """Talk publishes neither ``enabled`` nor ``apiVersions``; ``features`` is its statement."""
    payload = envelope(
        {
            "capabilities": {
                "spreed": {
                    "features": ["chat-v2", "conversation-v4", "chat-permission"],
                    "config": {"chat": {"max-length": 32000, "read-privacy": 0}},
                }
            }
        }
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(200, json=payload))
        caps = await capabilities.load(clients)

    assert caps.spreed_available is True
    assert caps.has("spreed") is True
    assert caps.spreed_features == ("chat-v2", "conversation-v4", "chat-permission")
    assert caps.spreed_chat_max_length == 32000


def test_an_instance_without_a_talk_section_reports_it_as_absent() -> None:
    """A Nextcloud without Talk is a normal Nextcloud, and the fallback length still holds."""
    caps = capabilities.parse({"capabilities": {"core": {}}})

    assert caps.spreed_available is False
    assert caps.has("spreed") is False
    assert caps.spreed_features == ()
    assert caps.spreed_chat_max_length == capabilities.DEFAULT_CHAT_MAX_LENGTH


def test_a_talk_section_that_is_an_empty_array_counts_as_absent() -> None:
    """The case Tables does not have: Talk answers ``[]`` when it is off for this user.

    An empty array is what a Nextcloud sends when Talk is installed but not available to the
    account asking, so the flag is "section present *and* not empty" rather than just
    present. Reading it as available would produce a 404 on an HTML page where a sentence
    belongs.
    """
    caps = capabilities.parse({"capabilities": {"spreed": []}})

    assert caps.spreed_available is False
    assert caps.has("spreed") is False
    assert caps.spreed_chat_max_length == 32000


def test_a_single_talk_feature_string_is_tolerated() -> None:
    """Same tolerance as the API version reader: one value may arrive unwrapped."""
    caps = capabilities.parse({"capabilities": {"spreed": {"features": "chat-v2"}}})

    assert caps.spreed_available is True
    assert caps.spreed_features == ("chat-v2",)
    assert caps.spreed_chat_max_length == 32000


def test_an_unreadable_chat_length_falls_back_instead_of_capping_at_zero() -> None:
    """A cap read from garbage would refuse every message; the fallback is the safer answer."""
    caps = capabilities.parse(
        {"capabilities": {"spreed": {"config": {"chat": {"max-length": "not a number"}}}}}
    )

    assert caps.spreed_chat_max_length == capabilities.DEFAULT_CHAT_MAX_LENGTH


@pytest.mark.anyio
async def test_require_app_names_the_missing_talk_app_and_the_next_step(
    clients: NcClients,
) -> None:
    """The user cannot install an app, so the one action names who can (D-15)."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=envelope({"capabilities": {"spreed": []}}))
        )
        with pytest.raises(AppMissingError) as excinfo:
            await capabilities.require_app(clients, "spreed")

    assert excinfo.value.message == "The Talk app is not available on this Nextcloud."
    assert "Talk app" in excinfo.value.hint
    assert excinfo.value.hint != excinfo.value.message


def test_an_envelope_with_the_created_status_is_a_success_and_not_an_error() -> None:
    """T1: the Talk send route documents 201 as its only success, and OCS v2 passes it on.

    ``V2Response::render`` writes the raw HTTP status into ``ocs.meta.statuscode``, so a sent
    message arrives with 201 in the envelope. While the success set held only 100 and 200,
    that read as "an unexpected status 201" and invited the model to send the message twice.
    """
    response = httpx.Response(201, json=envelope({"id": 4711, "token": "abcd1234"}, 201))

    assert ocs.parse_ocs(response, what="the sent message") == {"id": 4711, "token": "abcd1234"}
    assert sorted(ocs._OK_STATUS) == [100, 200, 201]


def test_an_envelope_with_a_rejected_password_stays_an_error() -> None:
    """The counter-check to the widened success set: only 201 moved, nothing else."""
    response = httpx.Response(200, json=envelope(None, 401, "Current user is not logged in"))

    with pytest.raises(ToolError) as excinfo:
        ocs.parse_ocs(response, what="the sent message")

    assert "app password" in excinfo.value.message.lower()


def test_has_refuses_an_app_this_server_does_not_check() -> None:
    """An unknown name is a programming error, never a silent False.

    The name used here is deliberately an app this project does *not* check. It used to be
    ``spreed``, then ``mail``, and it had to change both times, when Talk became the fourth
    and Mail the fifth checked app. That is the point of the test: the mapping in ``has()``
    is the list of apps, and a name outside it is a typo at the developer. ``cospend`` is a
    real Nextcloud app and one this project has no tool for.
    """
    caps = capabilities.parse({"capabilities": {"tables": {"enabled": True}}})
    assert caps.has("tables") is True
    assert caps.has("mail") is False, "checked since phase 10, and unanswered means absent"
    with pytest.raises(ValueError, match="cospend"):
        caps.has("cospend")


@pytest.mark.anyio
async def test_require_app_names_the_missing_tables_app_and_an_alternative(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(
                200, json=envelope({"capabilities": {"tables": {"enabled": False}}})
            )
        )
        with pytest.raises(AppMissingError) as excinfo:
            await capabilities.require_app(clients, "tables")

    assert excinfo.value.message == "The Tables app is not enabled on this Nextcloud."
    assert "Tables app" in excinfo.value.hint
    assert excinfo.value.hint != excinfo.value.message


@pytest.mark.anyio
async def test_an_html_login_page_explains_itself_instead_of_raising_a_keyerror(
    clients: NcClients,
) -> None:
    """The classic symptom of a missing OCS-APIRequest header (pitfall 9)."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(
                200, text=LOGIN_PAGE, headers={"content-type": "text/html; charset=UTF-8"}
            )
        )
        with pytest.raises(ToolError) as excinfo:
            await capabilities.load(clients)

    assert "HTML" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_rejected_app_password_is_reported_and_never_retried(clients: NcClients) -> None:
    """Nextcloud counts failures per source IP; a retry would slow down every user."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(401, json={}))
        with pytest.raises(ToolError) as excinfo:
            await capabilities.load(clients)

    assert route.call_count == 1, "an authentication failure is never repeated"
    assert "app password" in excinfo.value.message.lower()


@pytest.mark.anyio
async def test_an_ocs_error_envelope_becomes_a_tool_error(clients: NcClients) -> None:
    payload = {
        "ocs": {
            "meta": {
                "status": "failure",
                "statuscode": 400,
                "message": "No valid filters provided",
            },
            "data": [],
        }
    }
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{BASE}/ocs/v2.php/search/providers/notes/search").mock(
            return_value=httpx.Response(400, json=payload)
        )
        response = await ocs.ocs_get(
            clients.client, clients.creds, "/search/providers/notes/search", params={"term": ""}
        )
        with pytest.raises(ToolError) as excinfo:
            ocs.parse_ocs(response, what="the note search")

    assert "No valid filters provided" in f"{excinfo.value.message} {excinfo.value.hint}"


@pytest.mark.anyio
async def test_parse_app_json_reads_the_notes_and_deck_error_format(clients: NcClients) -> None:
    """Notes and Deck answer ``{"status": 4xx, "message": ...}``, not an OCS envelope."""
    url = f"{BASE}/index.php/apps/notes/api/v1/notes/999"
    with respx.mock(assert_all_called=True) as mock:
        mock.get(url).mock(
            return_value=httpx.Response(404, json={"status": 404, "message": "Note not found"})
        )
        response = await clients.client.get(url)
        with pytest.raises(ToolError) as excinfo:
            ocs.parse_app_json(response, what="the note")

    assert "Note not found" in f"{excinfo.value.message} {excinfo.value.hint}"


def test_parse_app_json_returns_the_payload_of_a_successful_answer() -> None:
    response = httpx.Response(200, json={"id": 12, "title": "Protokoll"})
    assert ocs.parse_app_json(response, what="the note") == {"id": 12, "title": "Protokoll"}


def test_parse_ocs_and_parse_app_json_are_separate_functions() -> None:
    """One envelope parser per API family; mixing them is exactly pitfall 9."""
    assert callable(ocs.parse_ocs)
    assert callable(ocs.parse_app_json)
    assert ocs.parse_ocs is not ocs.parse_app_json


@pytest.mark.anyio
async def test_require_app_names_the_missing_notes_app_and_an_alternative(
    clients: NcClients,
) -> None:
    """D-15, exact wording: the sentence a user can act on without reading our code."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=envelope({"capabilities": {}}))
        )
        with pytest.raises(AppMissingError) as excinfo:
            await capabilities.require_app(clients, "notes")

    assert excinfo.value.message == "The Notes app is not installed on this Nextcloud."
    assert "Notes app" in excinfo.value.hint
    assert excinfo.value.hint != excinfo.value.message


@pytest.mark.anyio
async def test_require_app_also_covers_deck(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=envelope({"capabilities": {"notes": {}}}))
        )
        with pytest.raises(AppMissingError) as excinfo:
            await capabilities.require_app(clients, "deck")

    assert excinfo.value.message == "The Deck app is not installed on this Nextcloud."


@pytest.mark.anyio
async def test_require_app_returns_the_capabilities_when_the_app_is_there(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        caps = await capabilities.require_app(clients, "notes")

    assert caps.notes_available is True


@pytest.mark.anyio
async def test_two_calls_within_the_ttl_make_exactly_one_http_call(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        first = await capabilities.load(clients)
        second = await capabilities.load(clients)

    assert route.call_count == 1, "the second call inside the TTL is served from the cache"
    assert first == second


@pytest.mark.anyio
async def test_an_expired_entry_is_fetched_again(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache is a latency optimisation and may be empty at any time (D-20)."""
    monkeypatch.setattr(capabilities, "TTL_SECONDS", 0.0)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        first = await capabilities.load(clients)
        second = await capabilities.load(clients)

    assert route.call_count == 2
    assert first == second, "an empty cache never changes the answer, only the latency"


@pytest.mark.anyio
async def test_the_cache_is_kept_per_credential_context(clients: NcClients) -> None:
    """Two users on the same instance never share an entry (threat T-01-42)."""
    other = NcClients(client=clients.client, creds=Credentials(BASE, "bob", "another-app-password"))
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        await capabilities.load(clients)
        await capabilities.load(other)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_a_server_error_is_reported_as_a_degraded_answer(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(503, text="service down"))
        with pytest.raises(ToolError) as excinfo:
            await capabilities.load(clients)

    assert "503" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_redirect_is_never_followed(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(302, headers={"location": "https://elsewhere.test/"})
        )
        with pytest.raises(ToolError) as excinfo:
            await capabilities.load(clients)

    assert "redirect" in excinfo.value.message.lower()


@pytest.mark.anyio
async def test_a_navigation_entry_for_mail_is_what_makes_the_app_available(
    clients: NcClients,
) -> None:
    """The second detection channel end to end, and the proof that it is actually asked.

    ``assert_all_called=True`` over both routes is the assertion here: the capabilities
    answer alone can never report Mail, because Mail publishes no section in it, so a green
    test without the second request would be a test of nothing.
    """
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        mock.get(NAVIGATION_URL).mock(
            return_value=httpx.Response(200, json=envelope([FILES_ENTRY, MAIL_ENTRY]))
        )
        caps = await capabilities.require_app(clients, "mail")

    assert caps.mail_available is True
    assert caps.has("mail") is True


@pytest.mark.anyio
async def test_a_navigation_without_mail_reports_the_app_as_absent(clients: NcClients) -> None:
    """A Nextcloud without Mail is a normal Nextcloud, and it says so in one sentence."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        mock.get(NAVIGATION_URL).mock(
            return_value=httpx.Response(200, json=envelope([FILES_ENTRY]))
        )
        with pytest.raises(AppMissingError) as excinfo:
            await capabilities.require_app(clients, "mail")

    assert excinfo.value.message == "The Mail app is not available on this Nextcloud."
    assert "Mail app" in excinfo.value.hint
    assert excinfo.value.hint != excinfo.value.message
    assert "navigation" not in f"{excinfo.value.message} {excinfo.value.hint}".lower()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "entry",
    [
        {"app": "mail", "type": "link", "name": "Mail"},
        {"id": "mail", "type": "link", "name": "Mail"},
        {"id": "mail-something", "app": "mail", "type": "settings"},
    ],
    ids=["app only", "id only", "differing id and another type"],
)
async def test_either_field_alone_identifies_the_mail_app(
    clients: NcClients, entry: dict[str, object]
) -> None:
    """Both fields carry ``mail`` in 5.11.1, and a second entry of one app may differ.

    The last case also states the missing filter positively: ``type`` is never looked at,
    because a filter on it would be an assumption about an answer shape with nothing to gain.
    """
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        mock.get(NAVIGATION_URL).mock(return_value=httpx.Response(200, json=envelope([entry])))
        caps = await capabilities.load_mail(clients)

    assert caps.mail_available is True


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [[], {"apps": ["mail"]}, None], ids=["empty", "object", "null"])
async def test_a_deformed_navigation_answer_is_an_error_and_never_a_missing_app(
    clients: NcClients, payload: object
) -> None:
    """Every instance has navigation, so an empty answer is deformed and not an answer.

    Reading it as "Mail is missing" would be the worst of both worlds: a wrong sentence about
    somebody else's instance, delivered with the confidence of a measurement. Same decision as
    the provider list of ``unified_search``, where zero providers is an error with a way out.
    """
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        mock.get(NAVIGATION_URL).mock(return_value=httpx.Response(200, json=envelope(payload)))
        with pytest.raises(ToolError) as excinfo:
            await capabilities.require_app(clients, "mail")

    assert not isinstance(excinfo.value, AppMissingError), "deformed is not the same as absent"
    assert excinfo.value.hint
    assert "Mail app is not available" not in excinfo.value.message


@pytest.mark.anyio
async def test_a_second_mail_call_inside_the_cache_window_asks_nothing_again(
    clients: NcClients,
) -> None:
    """Two requests for the first Mail tool call, none for the second (D-20)."""
    with respx.mock(assert_all_called=True) as mock:
        capabilities_route = mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        navigation_route = mock.get(NAVIGATION_URL).mock(
            return_value=httpx.Response(200, json=envelope([MAIL_ENTRY]))
        )
        first = await capabilities.require_app(clients, "mail")
        second = await capabilities.require_app(clients, "mail")

    assert capabilities_route.call_count == 1
    assert navigation_route.call_count == 1, "the refill happens once per cache window"
    assert first == second


@pytest.mark.anyio
async def test_a_talk_call_never_pays_for_the_navigation_request(clients: NcClients) -> None:
    """The refill hangs in ``require_app`` and not in ``load``, and this is why it matters."""
    payload = envelope({"capabilities": {"spreed": {"features": ["chat-v2"]}}})
    with respx.mock(assert_all_called=False) as mock:
        mock.get(CAPABILITIES_URL).mock(return_value=httpx.Response(200, json=payload))
        navigation_route = mock.get(NAVIGATION_URL).mock(
            return_value=httpx.Response(200, json=envelope([MAIL_ENTRY]))
        )
        caps = await capabilities.require_app(clients, "spreed")

    assert caps.has("spreed") is True
    assert len(navigation_route.calls) == 0, "Notes, Deck, Tables and Talk never ask this route"


@pytest.mark.anyio
async def test_the_second_question_does_not_extend_the_life_of_the_snapshot(
    clients: NcClients,
) -> None:
    """The refill writes the same key with the **original** timestamp, and stays in one entry.

    A refreshed timestamp would let a Mail user keep a stale capabilities snapshot alive for
    as long as they keep asking, which is exactly the kind of quiet lifetime extension the TTL
    exists to prevent.
    """
    key = (BASE, USER, USER)
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=capabilities_fixture())
        )
        mock.get(NAVIGATION_URL).mock(return_value=httpx.Response(200, json=envelope([MAIL_ENTRY])))
        await capabilities.load(clients)
        stored_at = capabilities._cache[key][0]
        await capabilities.load_mail(clients)

    assert capabilities._cache[key][0] == stored_at
    assert capabilities._cache[key][1].mail_available is True
    assert len(capabilities._cache) == 1, "the answer lands in the entry that already exists"


def test_an_unanswered_mail_question_is_not_the_same_as_an_absent_app() -> None:
    """``None`` is the third value that makes the refill path possible without a third cache."""
    fresh = capabilities.parse({"capabilities": {"core": {}}})

    assert fresh.mail_available is None, "None means not asked yet, and never absent"
    assert fresh.has("mail") is False
    assert dataclasses.replace(fresh, mail_available=True).has("mail") is True

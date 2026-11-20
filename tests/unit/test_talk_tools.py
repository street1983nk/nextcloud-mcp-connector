"""Unit tests for the two Talk tools, all paths.

The three content traps of this phase are pinned here, because none of them is visible in a
happy path:

*   the conversation list is sorted **before** it is cut. The app builds its query without an
    ``ORDER BY``, so a cut without a sort answers with 50 arbitrary conversations instead of
    the 50 newest, and on a small instance that is invisible (T5). The fixture is deliberately
    unsorted and the test asserts the sequence of tokens, not the number of them.
*   the write pre-check reads the resolved ``permissions`` and not ``attendeePermissions``.
    The fixture carries a conversation with ``permissions`` 254 next to
    ``attendeePermissions`` 0, which is the ordinary case on any instance, and a regression to
    the raw field turns that test red with the reason in its name (T3).
*   type 4 is write protected although its ``readOnly`` flag says 0, and every account has
    exactly one of those (T4).

Everything else is the honest-failure catalogue of D-15 and SRV-04: a missing Talk app stops
both tools before the first Talk request, an empty ``spreed`` section behaves like a missing
one, an unknown level names both that exist, and the send path refuses six different ways
before a single byte leaves this process.
"""

import inspect
import json
from pathlib import Path
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector import config, paging
from mcp_connector.errors import AppMissingError, ToolError
from mcp_connector.exapp.ui import strings
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import marks
from mcp_connector.tools import talk as talk_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"

# The same frozen literals as in the client test: the tool layer must not be able to move a
# route by accident either, and the two API versions of this family are the reason.
ROOM_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v4/room"
CHAT_BASE = f"{BASE}/ocs/v2.php/apps/spreed/api/v1/chat"
CHAT_URL = f"{CHAT_BASE}/abcd1234"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

#: One of the two sequences this server writes into a text itself. A chat message that may
#: write it back would decide the framing of foreign text (threat T-09-24).
MARKER = marks.EXCERPT_TRUNCATION

#: The ``spreed`` section as an instance with Talk 24 answers it: no ``enabled`` field and no
#: ``apiVersions``, so the presence of the section is the detection.
SPREED_INSTALLED = {
    "features": ["chat-v2", "conversation-v4", "chat-permission", "mention-permissions"],
    "config": {"chat": {"max-length": 32000}},
}


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tests assert the behaviour without any kein-ki tag; the guard states are
    tested in the *_exclusion test modules."""
    guard_routes.patch_untagged(monkeypatch)


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def envelope(data: Any, statuscode: int = 200, message: str = "OK") -> dict[str, Any]:
    """An OCS v2 envelope around any payload."""
    return {
        "ocs": {
            "meta": {"status": "ok", "statuscode": statuscode, "message": message},
            "data": data,
        }
    }


def capabilities_payload(*, spreed: dict | None = SPREED_INSTALLED) -> dict[str, Any]:
    section: dict[str, Any] = {"core": {}}
    if spreed is not None:
        section["spreed"] = spreed
    return envelope({"capabilities": section})


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    capabilities.clear_cache()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def mock_capabilities(mock: respx.MockRouter, *, spreed: dict | None = SPREED_INSTALLED) -> None:
    mock.get(CAPABILITIES_URL).mock(
        return_value=httpx.Response(200, json=capabilities_payload(spreed=spreed))
    )


def talk_routes(mock: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    """Catch-all routes for both API versions, to assert that nothing was requested."""
    return mock.route(url__startswith=ROOM_URL), mock.route(url__startswith=CHAT_BASE)


def mock_rooms(mock: respx.MockRouter, rooms: Any = None) -> respx.Route:
    payload = fixture("talk_rooms.json") if rooms is None else rooms
    return mock.get(ROOM_URL).mock(return_value=httpx.Response(200, json=envelope(payload)))


def room(token: str, **overrides: Any) -> dict[str, Any]:
    """One conversation of the fixture with a new token, for the list-length cases."""
    template = fixture("talk_rooms.json")[0]
    return {**template, "token": token, **overrides}


def mock_messages(
    mock: respx.MockRouter,
    payload: Any = None,
    *,
    last_given: int | None = None,
    status: int = 200,
) -> respx.Route:
    """The history route. The continuation of the app travels in a response header (T8)."""
    headers = {} if last_given is None else {"X-Chat-Last-Given": str(last_given)}
    if status == 304:
        return mock.get(CHAT_URL).mock(return_value=httpx.Response(304, headers=headers))
    body = fixture("talk_messages.json") if payload is None else payload
    return mock.get(CHAT_URL).mock(
        return_value=httpx.Response(status, json=envelope(body), headers=headers)
    )


def message(**overrides: Any) -> dict[str, Any]:
    """The newest message of the fixture with fields replaced, for the single-case tests."""
    template = fixture("talk_messages.json")[0]
    return {**template, **overrides}


#: What Talk answers a successful send with. The status is 201 in the transport **and** in the
#: OCS envelope, which is the reason plan 09-01 put 201 into the success set of the parser.
SENT_MESSAGE = {
    "id": 5105,
    "token": "abcd1234",
    "actorType": "users",
    "actorId": "alice",
    "actorDisplayName": "Alice Beispiel",
    "timestamp": 1755260000,
    "message": "Die Maße sind geprüft",
    "messageParameters": {},
    "messageType": "comment",
    "systemMessage": "",
    "expirationTimestamp": 0,
    "isReplyable": True,
    "markdown": True,
    "reactions": {},
    "referenceId": "",
}


def mock_send(mock: respx.MockRouter) -> respx.Route:
    """The send route of the one conversation of the fixture."""
    return mock.post(CHAT_URL).mock(
        return_value=httpx.Response(201, json=envelope(SENT_MESSAGE, statuscode=201))
    )


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["browse_conversations", "browse_messages", "send"])
async def test_a_missing_talk_app_stops_both_tools_before_the_first_request(
    clients: NcClients, tool: str
) -> None:
    """SRV-04 and D-15: one sentence with something to do, and zero Talk requests."""
    calls = {
        "browse_conversations": lambda: talk_tools.browse(clients),
        "browse_messages": lambda: talk_tools.browse(clients, level="messages", token="abcd1234"),
        "send": lambda: talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft"),
    }
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, spreed=None)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(AppMissingError) as excinfo:
            await calls[tool]()

    assert room_calls.call_count == 0, "no request may go to an app that is not available"
    assert chat_calls.call_count == 0
    assert "Talk app" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_an_empty_spreed_section_behaves_like_a_missing_one(clients: NcClients) -> None:
    """An instance with Talk switched off for this account answers an empty array."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, spreed={})
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(AppMissingError):
            await talk_tools.browse(clients)

    assert room_calls.call_count == 0
    assert chat_calls.call_count == 0


@pytest.mark.anyio
async def test_an_unknown_level_is_refused_and_names_both_of_them(clients: NcClients) -> None:
    """The schema rejects it first; the function stays honest when called directly."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.browse(clients, level="rooms")

    assert room_calls.call_count == 0, "the level is checked before the app is asked about"
    assert chat_calls.call_count == 0
    for level in ("conversations", "messages"):
        assert level in excinfo.value.hint


@pytest.mark.anyio
async def test_the_conversation_list_is_sorted_before_it_is_cut(clients: NcClients) -> None:
    """T5 and trap 5: the app has no ``ORDER BY``, so the sequence is ours to make.

    The fixture is deliberately stored in an order that contradicts ``lastActivity``. This
    test asserts the sequence of tokens and not the number of them, because a cut without a
    sort has the right count and the wrong content.
    """
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients)

    assert [entry["token"] for entry in result["results"]] == [
        "efgh5678",
        "abcd1234",
        "rdon7890",
        "npms2468",
        "chlg9012",
    ]


@pytest.mark.anyio
async def test_a_conversation_projects_the_fields_a_model_reads(clients: NcClients) -> None:
    """The numeric room id and everything about calls, lobby and avatars stay out."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        rooms = mock_rooms(mock)

        result = await talk_tools.browse(clients)

    assert rooms.calls.last.request.url.params["includeLastMessage"] == "true"
    assert result["level"] == "conversations"
    assert result["count"] == 5
    group = next(entry for entry in result["results"] if entry["token"] == "abcd1234")
    assert group == {
        "token": "abcd1234",
        "name": "Baustelle Süd",
        "type": 2,
        "unread": 3,
        "unread_mention": True,
        "unread_mention_direct": False,
        "last_activity": 1755180000,
        "read_only": 0,
        "can_send": True,
        "url": f"{BASE}/index.php/call/abcd1234",
        "last_message": "Bob Beispiel hat die Maße geprüft",
    }
    for dropped in ("id", "hasCall", "lobbyState", "avatarVersion", "sipEnabled", "attendeeId"):
        assert dropped not in group


@pytest.mark.anyio
async def test_a_one_to_one_conversation_is_named_by_its_display_name(
    clients: NcClients,
) -> None:
    """``name`` is a JSON array of user ids there, which is not something to show anybody."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients)

    direct = next(entry for entry in result["results"] if entry["token"] == "efgh5678")
    assert direct["name"] == "Carla Grüßgott"
    assert direct["type"] == 1


@pytest.mark.anyio
async def test_the_three_conversations_nobody_may_write_in_say_so(clients: NcClients) -> None:
    """``can_send`` is the pre-check one step earlier, and it has three reasons (T3, T4)."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients)

    can_send = {entry["token"]: entry["can_send"] for entry in result["results"]}
    assert can_send == {
        "efgh5678": True,
        "abcd1234": True,
        "rdon7890": False,
        "npms2468": False,
        "chlg9012": False,
    }


@pytest.mark.anyio
async def test_a_conversation_that_was_put_aside_does_not_appear(clients: NcClients) -> None:
    """The API has no parameter for it, so the filter is ours (T5)."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients)

    assert "arch3456" not in [entry["token"] for entry in result["results"]]
    assert result["count"] == 5, "the fixture has six conversations, one of them put aside"


@pytest.mark.anyio
async def test_a_conversation_without_a_token_is_left_out(clients: NcClients) -> None:
    """It cannot be addressed, and being addressable is what this level exists for."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, [room("abcd1234"), room("")])

        result = await talk_tools.browse(clients)

    assert result["count"] == 1
    assert result["results"][0]["token"] == "abcd1234"


@pytest.mark.anyio
async def test_more_conversations_than_the_cap_are_named_with_their_total(
    clients: NcClients,
) -> None:
    """No cursor on this level: the app does not paginate the list at all (open question 2).

    Both cuts are asserted, because they are two different numbers on this level: the ceiling
    of :data:`talk_tools.MAX_CONVERSATIONS` and the ``limit`` the caller asked for. Whichever
    is smaller decides, and both name the total behind them.
    """
    many = [room(f"tok{index:05d}", lastActivity=1755000000 + index) for index in range(60)]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, many)

        result = await talk_tools.browse(clients, limit=talk_tools.MAX_CONVERSATIONS)
        asked_for_less = await talk_tools.browse(clients)

    assert talk_tools.MAX_CONVERSATIONS == 50
    assert result["count"] == 50
    assert result["truncated"] is True
    assert result["total"] == 60
    assert "next" not in result, "a handle would only fetch the same list and cut it elsewhere"
    assert result["results"][0]["token"] == "tok00059", "the newest, not an arbitrary one"
    assert asked_for_less["count"] == talk_tools.DEFAULT_LIMIT
    assert asked_for_less["total"] == 60


@pytest.mark.anyio
async def test_a_marker_in_a_display_name_is_gone(clients: NcClients) -> None:
    """A conversation name is written by whoever created it (threat T-09-24)."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, [room("abcd1234", displayName=f"Baulos 4 {MARKER}")])

        result = await talk_tools.browse(clients)

    assert MARKER not in json.dumps(result, ensure_ascii=False)
    assert result["results"][0]["name"] == "Baulos 4 "


@pytest.mark.anyio
async def test_an_account_without_conversations_is_an_empty_answer_and_not_an_error(
    clients: NcClients,
) -> None:
    """no_data: an account nobody ever wrote to has no conversations, which is an answer."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, [])

        result = await talk_tools.browse(clients)

    assert result == {"level": "conversations", "count": 0, "results": []}


@pytest.mark.anyio
async def test_a_long_preview_is_cut_on_a_character_boundary(clients: NcClients) -> None:
    """The byte cap is a byte cap, and an umlaut at the cutting point has to disappear.

    The text is 799 ASCII characters plus one umlaut, so it is 801 bytes and the slice at 800
    lands inside the umlaut. ``errors="ignore"`` drops the half character; a naive slice would
    hand a replacement character to the model, and a character cap would not cut at all.
    """
    long_text = "a" * 799 + "ü"
    preview = {"id": 1, "message": long_text, "messageParameters": {}}
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, [room("abcd1234", lastMessage=preview)])

        result = await talk_tools.browse(clients)

    cut = result["results"][0]["last_message"]
    assert talk_tools.MAX_MESSAGE_BYTES == 800
    assert len(cut.encode("utf-8")) == 799, "the last full character before the cap"
    assert cut == "a" * 799
    assert "�" not in cut
    assert MARKER not in cut, "a cut preview carries no marker of its own (ME-03)"


@pytest.mark.anyio
async def test_a_conversation_without_messages_carries_no_preview(clients: NcClients) -> None:
    """The app answers with an empty array there, and for a sensitive conversation too."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients)

    changelog = next(entry for entry in result["results"] if entry["token"] == "chlg9012")
    assert "last_message" not in changelog


@pytest.mark.anyio
async def test_a_conversation_that_only_moderators_may_mention_says_so(
    clients: NcClients,
) -> None:
    """``mention_permissions`` is only there when it is set, and it explains a refusal."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients)

    restricted = next(entry for entry in result["results"] if entry["token"] == "rdon7890")
    open_to_all = next(entry for entry in result["results"] if entry["token"] == "abcd1234")
    assert restricted["mention_permissions"] == 1
    assert "mention_permissions" not in open_to_all


@pytest.mark.anyio
async def test_the_message_level_without_a_token_is_refused(clients: NcClients) -> None:
    """The refusal names the call that hands out the tokens, so it costs one round trip."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.browse(clients, level="messages")

    assert room_calls.call_count == 0
    assert chat_calls.call_count == 0
    assert "token" in excinfo.value.message
    assert "level=conversations" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_history_read_without_a_limit_reads_twenty_and_not_everything(
    clients: NcClients,
) -> None:
    """TALK-02: the property only the URL shows. Left out, the parameter reads 100."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        chat = mock_messages(mock, last_given=5100)

        await talk_tools.browse(clients, level="messages", token="abcd1234")

    params = chat.calls.last.request.url.params
    assert talk_tools.DEFAULT_LIMIT == 20
    assert params["limit"] == "20"
    assert params["lastKnownMessageId"] == "0"
    assert params["lookIntoFuture"] == "0", "the tool must not be able to start a long poll"


@pytest.mark.anyio
@pytest.mark.parametrize(("limit", "expected"), [(999, "50"), (0, "1")])
async def test_a_limit_outside_the_range_is_capped_instead_of_refused(
    clients: NcClients, limit: int, expected: str
) -> None:
    """The model asked a legitimate question with an unhelpful number."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        chat = mock_messages(mock, last_given=5100)

        await talk_tools.browse(clients, level="messages", token="abcd1234", limit=limit)

    assert chat.calls.last.request.url.params["limit"] == expected


@pytest.mark.anyio
async def test_the_envelope_names_the_conversation_the_history_belongs_to(
    clients: NcClients,
) -> None:
    """A wrong pick is visible in the answer, without a second tool call for the name."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["level"] == "messages"
    assert result["token"] == "abcd1234"
    assert result["conversation"] == "Baustelle Süd"


@pytest.mark.anyio
async def test_a_window_with_a_continuation_carries_truncated_and_a_handle(
    clients: NcClients,
) -> None:
    """T8: the handle is the id out of the response header, scoped to this conversation."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["truncated"] is True
    assert paging.decode_cursor(result["next"]) == {"c": "abcd1234", "o": 5100}


@pytest.mark.anyio
async def test_a_cursor_of_this_conversation_becomes_the_last_known_message_id(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        chat = mock_messages(mock, last_given=5000)

        await talk_tools.browse(
            clients,
            level="messages",
            token="abcd1234",
            cursor=paging.encode_cursor({"o": 5100, "c": "abcd1234"}),
        )

    assert chat.calls.last.request.url.params["lastKnownMessageId"] == "5100"


@pytest.mark.anyio
async def test_a_cursor_on_the_conversation_level_is_refused_before_any_request(
    clients: NcClients,
) -> None:
    """IN-04: silently handing back the first page again is paging in a circle.

    Only ``level=messages`` ever puts a ``next`` into an answer, so a handle on the
    conversation level is a handle of the message level or one somebody invented. It is
    refused with a sentence and a next step, and the refusal stands before the capabilities
    request, so it costs no request at all.
    """
    handle = paging.encode_cursor({"o": 5100, "c": "abcd1234"})
    with respx.mock(assert_all_called=False) as mock:
        caps = mock.get(CAPABILITIES_URL)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.browse(clients, level="conversations", cursor=handle)

    assert caps.call_count == 0, "the refusal is cheaper than the capabilities request"
    assert len(room_calls.calls) == 0
    assert len(chat_calls.calls) == 0
    assert "level='conversations'" in excinfo.value.message
    assert "no next page" in excinfo.value.message
    assert "level=messages" in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize("blank", ["", "   ", None])
async def test_no_cursor_on_the_conversation_level_is_not_a_refusal(
    clients: NcClients, blank: str | None
) -> None:
    """Edge: the registration layer sends an empty string, and empty is "no handle"."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)

        result = await talk_tools.browse(clients, level="conversations", cursor=blank)

    assert result["level"] == "conversations"
    assert result["count"]


@pytest.mark.anyio
async def test_a_cursor_of_another_conversation_is_refused_instead_of_applied(
    clients: NcClients,
) -> None:
    """A page of the wrong chat is an answer nobody can notice is wrong."""
    foreign = paging.encode_cursor({"o": 5100, "c": "efgh5678"})
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.browse(clients, level="messages", token="abcd1234", cursor=foreign)

    assert chat_calls.call_count == 0, "a handle of another conversation reads no page"
    assert room_calls.call_count == 0, "the handle is the cheaper refusal of the two"
    assert "conversation" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_an_empty_history_is_an_answer_and_not_a_configuration_problem(
    clients: NcClients,
) -> None:
    """no_data and T2: a fresh conversation answers 304, and 304 is not a redirect."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, status=304)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["count"] == 0
    assert result["results"] == []
    assert "next" not in result
    assert "truncated" not in result
    assert result["conversation"] == "Baustelle Süd"


@pytest.mark.anyio
async def test_a_window_of_only_system_messages_is_empty_and_still_offers_the_next_page(
    clients: NcClients,
) -> None:
    """Trap 6: the end of the history is the missing header and never an empty window.

    The app sets the continuation from the oldest message it read and drops the invisible
    ones afterwards; the positive list of this module does the same a second time. Reading
    "no more history" out of an empty window would hide everything older than it.
    """
    system_only = [
        item for item in fixture("talk_messages.json") if item["messageType"] == "system"
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, system_only, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["count"] == 0
    assert result["truncated"] is True
    assert paging.decode_cursor(result["next"]) == {"c": "abcd1234", "o": 5100}


@pytest.mark.anyio
async def test_the_placeholders_of_a_message_are_resolved_and_a_mention_keeps_its_at_sign(
    clients: NcClients,
) -> None:
    """Muster 5: the app resolved the display names already, so this reads its answer.

    ``{actor}`` and ``{mention-user1}`` both carry type ``user``, and only the second one is a
    mention: prefixing the first would make every message look as if it mentioned its own
    author. A file name is a value and keeps no prefix either.
    """
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert [entry["id"] for entry in result["results"]] == [5104, 5103, 5102]
    newest = result["results"][0]
    assert newest["message"] == "Bob Beispiel hat die Maße an @Alice Beispiel übergeben"
    assert newest["actor"] == "Bob Beispiel"
    assert newest["timestamp"] == 1755180000
    assert result["results"][2]["message"] == (
        "Die Datei Spülprotokoll.pdf liegt jetzt im Ordner Übergabe"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "parameters",
    [{}, {"ticket": {"type": "highlight", "id": "4711", "name": "  "}}],
    ids=["unknown", "nameless"],
)
async def test_a_placeholder_nobody_can_resolve_stays_in_the_text(
    clients: NcClients, parameters: dict[str, Any]
) -> None:
    """Nothing is guessed here: a placeholder without a name is left as it came."""
    raw = [message(id=42, message="Der Vorgang {ticket} ist offen", messageParameters=parameters)]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, raw)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["results"][0]["message"] == "Der Vorgang {ticket} ist offen"


@pytest.mark.anyio
async def test_a_long_message_is_cut_on_a_character_boundary_and_says_so_beside_the_text(
    clients: NcClients,
) -> None:
    """Muster 7 and ME-03: the cut is a field, and the umlaut at the cap disappears.

    799 ASCII characters plus an umlaut are 801 bytes, so the slice at 800 lands inside the
    umlaut. A naive slice would hand a replacement character to the model, a character cap
    would not cut at all, and a marker inside the text would let a chat message forge one.
    """
    raw = [message(id=42, message="a" * 799 + "ü" + " und weiter", messageParameters={})]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, raw)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    entry = result["results"][0]
    assert entry["message_truncated"] is True
    assert "truncated" not in entry, "the entry level flag is the message one, never the page one"
    assert entry["message"] == "a" * 799
    assert "�" not in entry["message"]
    assert MARKER not in entry["message"]
    assert "truncated" not in json.dumps(entry["message"])


@pytest.mark.anyio
async def test_a_cut_window_and_a_cut_message_are_two_keys_with_two_meanings(
    clients: NcClients,
) -> None:
    """DF-11-01: the case that made one word for two cuts a problem, in one single answer.

    Both flags are set here at the same time and neither of them can be derived from the
    other: the **window** was cut, so there is a ``next`` to continue with, and the **text** of
    one entry was cut at :data:`talk_tools.MAX_MESSAGE_BYTES`, which no cursor continues
    because the whole message is one ``fetch`` away and not one page further. While both were
    called ``truncated``, a model reading the entry level flag as a page flag paged in a
    circle, which is the same finding IN-01 named for ``mail_browse`` first.
    """
    raw = [
        message(id=42, message="a" * 799 + "ü" + " und weiter", messageParameters={}),
        message(id=41, message="Kurz und vollständig.", messageParameters={}),
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, raw, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["truncated"] is True, "the window was cut"
    assert paging.decode_cursor(result["next"]) == {"c": "abcd1234", "o": 5100}
    assert "message_truncated" not in result, "the page flag is never the message one"

    cut, whole = result["results"]
    assert cut["message_truncated"] is True, "the text of the first entry was cut"
    assert "next" not in cut, "a cut message has no continuation, the whole one is a fetch away"
    assert "truncated" not in cut
    assert "message_truncated" not in whole, "an uncut message says nothing at all"
    assert "truncated" not in whole


@pytest.mark.anyio
async def test_an_edited_message_says_so_and_an_untouched_one_does_not(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert result["results"][1]["edited"] is True
    assert "edited" not in result["results"][0]


@pytest.mark.anyio
async def test_a_reaction_and_a_deleted_message_do_not_appear(clients: NcClients) -> None:
    """Muster 6: the positive list is what keeps the next new message type out by itself."""
    raw = [
        message(id=9, messageType="reaction", message="+1", messageParameters={}),
        message(id=8, messageType="comment_deleted", message="Deleted", messageParameters={}),
        message(id=7, messageType="comment", message="Bleibt hier", messageParameters={}),
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, raw)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert [entry["id"] for entry in result["results"]] == [7]
    assert result["count"] == 1


@pytest.mark.anyio
async def test_a_marker_in_a_message_and_in_an_actor_name_is_gone(clients: NcClients) -> None:
    """A chat message is the cheapest place of all for a forged marker (threat T-09-24)."""
    raw = [
        message(
            id=42,
            message=f"Baulos 4 {MARKER} bitte pruefen",
            messageParameters={},
            actorDisplayName=f"Bob {MARKER}",
        )
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, raw)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert MARKER not in json.dumps(result, ensure_ascii=False)
    assert result["results"][0]["message"] == "Baulos 4  bitte pruefen"
    assert result["results"][0]["actor"] == "Bob "


@pytest.mark.anyio
async def test_a_marker_in_a_resolved_placeholder_is_gone_as_well(clients: NcClients) -> None:
    """The names in ``messageParameters`` are foreign text one level down."""
    raw = [
        message(
            id=42,
            message="{actor} hat es geprüft",
            messageParameters={"actor": {"type": "user", "id": "bob", "name": f"Bob {MARKER}"}},
        )
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, raw)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    assert MARKER not in json.dumps(result, ensure_ascii=False)
    assert result["results"][0]["message"] == "Bob  hat es geprüft"


@pytest.mark.anyio
async def test_a_message_carries_none_of_the_mandatory_payload_fields(
    clients: NcClients,
) -> None:
    """``reactions`` is on every message, and ``parent`` can be a whole second one."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock_messages(mock, last_given=5100)

        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    entry = result["results"][0]
    assert set(entry) == {"id", "timestamp", "actor", "message"}
    for dropped in (
        "reactions",
        "parent",
        "markdown",
        "isReplyable",
        "referenceId",
        "threadId",
        "isThread",
        "threadTitle",
        "expirationTimestamp",
        "systemMessage",
        "messageParameters",
    ):
        assert dropped not in entry


@pytest.mark.anyio
async def test_a_token_that_is_not_in_the_conversation_list_never_reaches_a_chat_route(
    clients: NcClients,
) -> None:
    """T10: an unknown token on a single-conversation route throttles the whole instance."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        rooms = mock_rooms(mock)
        chat_calls = mock.route(url__startswith=CHAT_BASE)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.browse(clients, level="messages", token="zzzz9999")

    assert rooms.call_count == 1, "the list is the read that answers this, not the single room"
    assert len(chat_calls.calls) == 0
    assert "conversation list" in excinfo.value.message
    assert "level=conversations" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_switched_off_send_makes_not_a_single_http_call(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TALK-04, layer 3 and trap 10: a switch that catches after the POST caught nothing.

    Nothing is mocked but the catch-all, so this also proves that the switch is read before
    the capabilities request: with the switch off there is no request at all to answer.
    """
    monkeypatch.setenv(config.ENV_TALK_SEND, "0")
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(url__startswith=BASE)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    assert len(route.calls) == 0, "the outgoing channel is closed, so nothing may leave"
    assert "switched off" in excinfo.value.message
    assert "administrator" in excinfo.value.hint
    assert strings.ADMIN_SETTINGS_PLACE in excinfo.value.hint
    assert "disabled and enabled again" in excinfo.value.hint
    assert "talk_browse is unaffected" in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize("empty", ["", "   ", None])
async def test_a_send_without_a_token_never_asks_for_the_conversation_list(
    clients: NcClients, empty: str | None
) -> None:
    """IN-01: the symmetry with ``browse``, which refuses a missing token before any request.

    The conversation list is the read that resolves a token, so a caller who supplied none has
    nothing to resolve and must not pay for the round trip. The second reason is the empty
    string itself: it is what a conversation the payload lists without a token of its own would
    match, and a match there would be worse than the refusal.
    """
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, empty, "Die Maße sind geprüft")  # type: ignore[arg-type]

    assert len(room_calls.calls) == 0, "there is no token to look up, so nothing is looked up"
    assert len(chat_calls.calls) == 0
    assert "token" in excinfo.value.message
    assert "level=conversations" in excinfo.value.hint


@pytest.mark.anyio
async def test_the_switch_is_read_before_the_app_is_detected(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every other tool of this server starts with the app detection; this one must not."""
    monkeypatch.setenv(config.ENV_TALK_SEND, "0")
    with respx.mock(assert_all_called=False) as mock:
        caps = mock.get(CAPABILITIES_URL)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError):
            await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    assert len(caps.calls) == 0, "not even the capabilities are asked for"
    assert len(room_calls.calls) == 0
    assert len(chat_calls.calls) == 0


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["1", "true", "", "vielleicht"])
async def test_the_switch_is_on_unless_it_says_off(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """The shipped state is on, so an unreadable value must not close the channel (T-09-13)."""
    monkeypatch.setenv(config.ENV_TALK_SEND, value)
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        post = mock_send(mock)

        result = await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    assert post.call_count == 1
    assert result["sent"] is True


@pytest.mark.anyio
async def test_a_sent_message_answers_with_its_id_its_conversation_and_its_address(
    clients: NcClients,
) -> None:
    """No retry anywhere: the answer is what lets the model read back instead of repeating."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        post = mock_send(mock)

        result = await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    assert json.loads(post.calls.last.request.content) == {"message": "Die Maße sind geprüft"}
    assert result == {
        "sent": True,
        "id": 5105,
        "token": "abcd1234",
        "conversation": "Baustelle Süd",
        "timestamp": 1755260000,
        "url": f"{BASE}/index.php/call/abcd1234",
    }


@pytest.mark.anyio
async def test_a_conversation_with_the_chat_permission_may_be_written_in(
    clients: NcClients,
) -> None:
    """The regression to T3: ``permissions`` 128 next to ``attendeePermissions`` 0 is allowed.

    That combination is the ordinary case on any instance, because Talk resolves the
    permissions through a fallback chain and leaves the raw participant value at 0. A
    pre-check on the raw field would refuse almost every account in almost every
    conversation, and the failure would look like a permission problem instead of a field
    name.
    """
    only_chat = room("abcd1234", permissions=talk_tools.PERMISSIONS_CHAT, attendeePermissions=0)
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, [only_chat])
        post = mock_send(mock)

        result = await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    assert post.call_count == 1, "the resolved permissions carry bit 128, so this may be sent"
    assert result["id"] == 5105


@pytest.mark.anyio
async def test_a_note_to_self_is_not_locked_away_with_the_read_only_conversations(
    clients: NcClients,
) -> None:
    """Type 6 is writable, and only type 4 is the one Talk keeps read only (T4)."""
    note = room("abcd1234", type=6, displayName="Notiz an mich")
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock, [note])
        post = mock_send(mock)

        await talk_tools.send(clients, "abcd1234", "Maße noch prüfen")

    assert post.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("rdon7890", "read only"),
        ("chlg9012", "changelog conversation"),
        ("npms2468", "no chat permission"),
    ],
    ids=["read-only", "changelog", "no-chat-permission"],
)
async def test_a_conversation_nobody_may_write_in_is_refused_before_the_post(
    clients: NcClients, target: str, expected: str
) -> None:
    """Three refusals, three sentences, and no request that could only end in a 403."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        post = mock.post(f"{CHAT_BASE}/{target}")

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, target, "Die Maße sind geprüft")

    assert len(post.calls) == 0, "a request that can only end in 403 must never leave"
    assert expected in excinfo.value.message
    assert "can_send" in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize(
    "text",
    [
        "@all bitte die Maße prüfen",
        "@ALL bitte die Maße prüfen",
        "Bitte @here einmal lesen",
        'Bitte @"all" einmal lesen',
        "Abnahme morgen @all",
        # One case per collective spelling the Nextcloud comment parser can answer with
        # (``lib/private/Comments/Comment.php:216`` in server v34.0.0): quoted, which is the
        # form that works, and unquoted, which is refused as a precaution the same way
        # ``@here`` is.
        'Bitte @"group/bauleitung" die Maße prüfen',
        "Bitte @group/bauleitung die Maße prüfen",
        'Bitte @"team/baulos-4" die Maße prüfen',
        "Bitte @team/baulos-4 die Maße prüfen",
        'Bitte @"federated_group/planung@cloud.example" lesen',
        "Bitte @federated_group/planung@cloud.example lesen",
        'Bitte @"federated_team/planung@cloud.example" lesen',
        "Bitte @federated_team/planung@cloud.example lesen",
        # Upper case on a prefix, because the pattern carries ``re.IGNORECASE`` and the
        # server regex does too.
        'Bitte @"GROUP/Bauleitung" die Maße prüfen',
    ],
)
async def test_a_collective_mention_is_refused_before_anything_is_read(
    clients: NcClients, text: str
) -> None:
    """T11 and T-09-23: one tool call must not become a notification for a whole collective.

    Every spelling of this list ends in one notification per member: ``@all`` covers every
    participant of the conversation, and the four prefixed types are resolved to their members
    in spreed v24.0.4 (``lib/Chat/Notifier.php:525`` for groups, ``:581`` for teams).
    """
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", text)

    assert len(room_calls.calls) == 0
    assert len(chat_calls.calls) == 0
    assert "everybody or a whole group" in excinfo.value.message
    assert "one by one" in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name",
    [
        "@allan",
        "@allison",
        "@alle-vier",
        "@heretic",
        # The three prefixed types that address exactly one person, which is what this tool
        # is for (``lib/Chat/Parser/UserMention.php:139-145`` lists all six prefixes).
        '@"federated_user/alice@cloud.example"',
        '@"guest/a1b2c3d4"',
        '@"email/a1b2c3d4"',
        # A quoted ordinary user id, the form Talk writes when the id carries a space.
        '@"alice mueller"',
        # The ``/`` is the boundary of the four prefixes, so a person whose id starts with
        # one of those words stays a person.
        "@grouping",
        "@teamster",
        '@"group"',
        # And the bare words are ordinary text without an ``@`` in front of them.
        "Die group und das team der",
    ],
)
async def test_a_mention_of_a_real_person_is_not_a_collective_mention(
    clients: NcClients, name: str
) -> None:
    """The two boundaries are the point: a plain containment test eats legitimate mentions."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        post = mock_send(mock)

        await talk_tools.send(clients, "abcd1234", f"{name} bitte die Maße prüfen")

    assert post.call_count == 1


@pytest.mark.anyio
async def test_a_message_longer_than_the_instance_allows_is_refused_with_the_number(
    clients: NcClients,
) -> None:
    """The limit belongs to the instance: it comes out of the capabilities, not out of us."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, spreed={"config": {"chat": {"max-length": 120}}})
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", "ü" * 200)

    assert len(room_calls.calls) == 0
    assert len(chat_calls.calls) == 0
    assert "200 characters" in excinfo.value.message
    assert "120 per message" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_message_of_multi_byte_characters_is_counted_the_way_the_server_counts_it(
    clients: NcClients,
) -> None:
    """IN-06: the pre-check counts code points after a trim, because the server does.

    ``OC\\Comments\\Comment::setMessage`` (nextcloud/server v34.0.0,
    ``lib/private/Comments/Comment.php:186-189``) trims first and then compares
    ``mb_strlen($message, 'UTF-8')``, and spreed v24.0.4 reaches it with
    ``MAX_CHAT_LENGTH`` from ``lib/Chat/ChatManager.php:407``.

    The text below is 120 umlauts plus a newline and two spaces, so the three ways to measure
    it disagree on purpose: 243 bytes, 123 characters untrimmed and 120 characters the way the
    server counts. At a limit of 120 only the third reading sends it, and it is the reading
    Nextcloud uses, so the message has to go out and it has to go out unchanged.
    """
    at_the_limit = "ü" * 120 + "\n  "
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock, spreed={"config": {"chat": {"max-length": 120}}})
        mock_rooms(mock)
        post = mock_send(mock)

        await talk_tools.send(clients, "abcd1234", at_the_limit)

    assert len(at_the_limit.encode("utf-8")) == 243, "a byte count would have refused this"
    assert len(at_the_limit) == 123, "an untrimmed character count would have refused it too"
    assert post.call_count == 1
    sent = json.loads(post.calls[0].request.content.decode("utf-8"))
    assert sent["message"] == at_the_limit, "the text goes out as it came, the server trims it"


@pytest.mark.anyio
async def test_one_character_over_the_instance_limit_is_refused_with_the_counted_number(
    clients: NcClients,
) -> None:
    """The other side of the same boundary: 121 of 120, and the number in the sentence."""
    too_long = "ü" * 121 + "\n"
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, spreed={"config": {"chat": {"max-length": 120}}})
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", too_long)

    assert len(room_calls.calls) == 0
    assert len(chat_calls.calls) == 0
    assert "121 characters" in excinfo.value.message, "the trailing newline is not counted"
    assert "120 per message" in excinfo.value.message


@pytest.mark.anyio
async def test_an_instance_without_a_chat_length_falls_back_to_the_number_talk_ships(
    clients: NcClients,
) -> None:
    """32000 stands in the capabilities module once, as the fallback and nowhere else."""
    too_long = "a" * (capabilities.DEFAULT_CHAT_MAX_LENGTH + 1)
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, spreed={"features": ["chat-v2"]})
        room_calls, chat_calls = talk_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", too_long)

    assert len(room_calls.calls) == 0
    assert len(chat_calls.calls) == 0
    assert "32000 per message" in excinfo.value.message


@pytest.mark.anyio
async def test_a_token_nobody_knows_never_reaches_a_chat_route(clients: NcClients) -> None:
    """T10 and T-09-21: Nextcloud never sees an invented token in a path at all."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        rooms = mock_rooms(mock)
        chat_calls = mock.route(url__startswith=CHAT_BASE)

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "zzzz9999", "Die Maße sind geprüft")

    assert rooms.call_count == 1
    assert len(chat_calls.calls) == 0
    assert "conversation list" in excinfo.value.message
    assert "level=conversations" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_sent_message_without_an_id_is_reported_instead_of_faked(
    clients: NcClients,
) -> None:
    """An id nobody sent is the shape that invites a second send (threat T-09-25)."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock.post(CHAT_URL).mock(
            return_value=httpx.Response(201, json=envelope({"token": "abcd1234"}, statuscode=201))
        )

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    assert "no id" in excinfo.value.message
    assert "Baustelle Süd" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_four_hundred_of_the_app_is_passed_through_with_its_own_message(
    clients: NcClients,
) -> None:
    """The app knows its own limits; a second validator here would be a second truth."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock_rooms(mock)
        mock.post(CHAT_URL).mock(
            return_value=httpx.Response(
                400, json=envelope(None, statuscode=400, message="Message too long")
            )
        )

        with pytest.raises(ToolError) as excinfo:
            await talk_tools.send(clients, "abcd1234", "Die Maße sind geprüft")

    # Wording fix of plan 35-11: the Nextcloud text is quoted so the sentence can end.
    assert 'Nextcloud says: "Message too long".' in excinfo.value.message


def test_the_levels_and_the_limits_are_the_ones_the_schema_will_offer() -> None:
    """Plan 09-04 builds the input schema out of exactly these five values."""
    assert talk_tools.LEVELS == ("conversations", "messages")
    assert talk_tools.DEFAULT_LIMIT == 20
    assert talk_tools.MAX_LIMIT == 50
    assert talk_tools.MAX_CONVERSATIONS == 50
    assert talk_tools.MAX_MESSAGE_BYTES == 800


def test_the_kept_message_types_are_a_positive_list_and_not_a_parameter() -> None:
    """Open question 3: no ``include_system``, and a new verb of the app stays out by itself."""
    # Sorted rather than compared as a set: ruff reads a set literal on the right of an
    # equality as a Yoda condition (SIM300), and a fixed order names the missing verb.
    assert sorted(talk_tools.KEPT_TYPES) == [
        "comment",
        "object_shared",
        "private_reply",
        "voice-message",
    ]
    assert "include_system" not in inspect.signature(talk_tools.browse).parameters

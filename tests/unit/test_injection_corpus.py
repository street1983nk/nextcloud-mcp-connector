"""The injection corpus: one poisoned value per content family, held as data.

A prompt injection arrives as content: a file name, a calendar summary, a mail
subject, a chat message. The contract this server makes about all of them is the
same two sentences, and this file pins it per family instead of leaving it to be
inferred from one corridor. **First**: the text arrives character for character
as data, in the one field that carries content, because rewriting foreign text
would be a second truth about it (the D-57 decision: no masking, origin as
structured fields, the text as a pure data field). **Second**: the instruction
stays in that field, and no other field of the answer picks it up, so a client
that renders provenance can tell where the sentence came from.

The corpus deliberately reuses the sentence of ``test_tools_context.py``, so one
grep finds every place the suite holds it. What is pinned elsewhere and not
repeated here: the ``prepare_context`` corridor (test_tools_context.py, plan
04-02), and the marker filter that strips this server's own framing sequences
out of foreign chat text (test_talk_tools.py, threat T-09-24).
"""

import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import guard_routes
import httpx
import pytest
import respx
from test_tools_context import INJECTION

from mcp_connector import ids
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import calendar as calendar_tools
from mcp_connector.tools import files as files_tools
from mcp_connector.tools import mail as mail_tools
from mcp_connector.tools import marks
from mcp_connector.tools import talk as talk_tools
from mcp_connector.tools import tasks as tasks_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

SEARCH_URL = f"{BASE}/remote.php/dav/"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
PERSONAL = f"{CALENDAR_HOME}personal/"
ALPHA = f"{CALENDAR_HOME}projekt%20alpha/"
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"
NAVIGATION_URL = f"{BASE}/ocs/v2.php/core/navigation/apps"
MAIL_PREFIX = f"{BASE}/ocs/v2.php/apps/mail"
MAILBOX_ID = 7
MESSAGES_URL = f"{MAIL_PREFIX}/ocs/mailboxes/{MAILBOX_ID}/messages"
ROOM_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v4/room"
CHAT_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v1/chat/abcd1234"


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard states live in the *_exclusion modules; this corpus is about text."""
    guard_routes.patch_untagged(monkeypatch)


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    capabilities.clear_cache()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def envelope(data: Any, statuscode: int = 200, message: str = "OK") -> dict[str, Any]:
    return {
        "ocs": {
            "meta": {"status": "ok", "statuscode": statuscode, "message": message},
            "data": data,
        }
    }


def everything_but(answer: dict[str, Any], content_key: str) -> str:
    """The whole answer as text, minus the one field that is allowed to carry the content.

    This is the second sentence of the contract made checkable: dropping the content
    field and serialising the rest proves the instruction did not leak into a note, a
    hint, a degraded entry or any field a model might read as this server's own voice.
    """
    rest = {key: value for key, value in answer.items() if key != content_key}
    return json.dumps(rest, ensure_ascii=False)


# --- a file name (files_search) --------------------------------------------------------


@pytest.mark.anyio
async def test_a_file_name_that_is_an_instruction_stays_a_file_name(clients: NcClients) -> None:
    poisoned = f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/Docs/poisoned.md</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>{INJECTION}</d:displayname>
        <d:getcontenttype>text/markdown</d:getcontenttype>
        <d:getlastmodified>Thu, 14 Aug 2026 10:00:00 GMT</d:getlastmodified>
        <d:getcontentlength>100</d:getcontentlength>
        <d:resourcetype/>
        <oc:fileid>5000</oc:fileid>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=poisoned)
        )
        result = await files_tools.search(clients, query="instructions")

    assert result["items"][0]["name"] == INJECTION, "character for character, as data"
    assert INJECTION not in everything_but(result, "items"), (
        "the instruction is a name among the items and never part of any other field"
    )


# --- a calendar summary (calendar_list_events) ------------------------------------------


@pytest.mark.anyio
async def test_a_calendar_summary_that_is_an_instruction_stays_a_summary(
    clients: NcClients,
) -> None:
    poisoned = f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/remote.php/dav/calendars/alice/personal/poisoned.ics</d:href>
    <d:propstat>
      <d:prop>
        <d:getetag>&quot;11aa22bb&quot;</d:getetag>
        <cal:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sabre//Sabre VObject 4.5.6//EN
BEGIN:VEVENT
UID:poisoned-uid
DTSTAMP:20260901T101500Z
DTSTART:20260915T120000Z
DTEND:20260915T130000Z
SUMMARY:{INJECTION}
END:VEVENT
END:VCALENDAR
</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    empty = '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>'
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=httpx.Response(207, text=fixture_text("caldav_calendars_207.xml"))
        )
        mock.route(method="REPORT", url=PERSONAL).mock(
            return_value=httpx.Response(207, text=poisoned)
        )
        mock.route(method="REPORT", url=ALPHA).mock(return_value=httpx.Response(207, text=empty))
        result = await calendar_tools.list_events(
            clients, start="2026-09-01T00:00:00+02:00", end="2026-11-01T00:00:00+01:00"
        )

    assert result["count"] == 1
    assert result["events"][0]["summary"] == INJECTION, "character for character, as data"
    assert INJECTION not in everything_but(result, "events")


# --- a mail subject and preview (mail_browse) --------------------------------------------


@pytest.mark.anyio
async def test_a_mail_subject_that_is_an_instruction_stays_a_subject(clients: NcClients) -> None:
    """A1's channel: the author of a mail needs no account anywhere, so this family is the
    cheapest way to put text in front of the model, and the projection must neither reword
    it nor let it travel outside the envelope fields."""
    poisoned = {
        "databaseId": 4711,
        "uid": 12,
        "remoteId": 12,
        "messageId": "<abc@nc.test>",
        "mailboxId": MAILBOX_ID,
        "subject": INJECTION,
        "previewText": f"{INJECTION} und zwar sofort.",
        "dateInt": 1755181000,
        "flags": {"seen": False, "hasAttachments": False},
        "from": [{"label": "Bob Beispiel", "email": "bob@example.org"}],
        "to": [{"label": "Alice Beispiel", "email": "alice@nc.test"}],
        "cc": [],
        "bcc": [],
        "tags": {},
        "attachments": [],
    }
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(200, json=envelope({"capabilities": {"core": {}}}))
        )
        mock.get(NAVIGATION_URL).mock(
            return_value=httpx.Response(
                200, json=envelope([{"id": "mail", "app": "mail", "type": "link"}])
            )
        )
        mock.get(MESSAGES_URL).mock(return_value=httpx.Response(200, json=envelope([poisoned])))
        result = await mail_tools.browse(clients, level="messages", mailbox_id=str(MAILBOX_ID))

    entry = result["results"][0]
    assert entry["subject"] == INJECTION, "character for character, as data"
    assert entry["preview"] == f"{INJECTION} und zwar sofort."
    assert INJECTION not in everything_but(result, "results")


# --- a chat message (talk_browse) ---------------------------------------------------------


@pytest.mark.anyio
async def test_a_chat_message_that_is_an_instruction_stays_a_message(clients: NcClients) -> None:
    spreed = {
        "features": ["chat-v2", "conversation-v4", "chat-permission", "mention-permissions"],
        "config": {"chat": {"max-length": 32000}},
    }
    poisoned = json.loads(fixture_text("talk_messages.json"))[0]
    poisoned = {**poisoned, "message": INJECTION, "messageParameters": {}}
    with respx.mock(assert_all_called=True) as mock:
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(
                200,
                json=envelope({"capabilities": {"core": {}, "spreed": spreed}, "version": {}}),
            )
        )
        mock.get(ROOM_URL).mock(
            return_value=httpx.Response(
                200, json=envelope(json.loads(fixture_text("talk_rooms.json")))
            )
        )
        mock.get(CHAT_URL).mock(
            return_value=httpx.Response(
                200, json=envelope([poisoned]), headers={"X-Chat-Last-Given": "5104"}
            )
        )
        result = await talk_tools.browse(clients, level="messages", token="abcd1234")

    texts = [entry["message"] for entry in result["results"]]
    assert texts == [INJECTION], "character for character, as data"
    assert INJECTION not in everything_but(result, "results")


# --- a task from a shared list (tasks_search, tasks_read) ------------------------------------


SHARED_TASK_LIST = "spike30-b-rw_shared_by_bob"
SHARED_TASK_LIST_URL = f"{CALENDAR_HOME}{SHARED_TASK_LIST}/"
SHARED_TASK_NAME = "poisoned-task.ics"


def shared_task(*lines: str) -> str:
    """One VTODO of the list ``bob`` shared with ``alice``, built like the Tasks app writes it."""
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Nextcloud Tasks v0.18.1",
            "BEGIN:VTODO",
            "UID:poisoned-task",
            "CREATED:20261111T125033Z",
            "DTSTAMP:20261111T125217Z",
            *lines,
            "END:VTODO",
            "END:VCALENDAR",
            "",
        ]
    )


def task_multistatus(ics: str) -> str:
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        'xmlns:cal="urn:ietf:params:xml:ns:caldav"><d:response>'
        f"<d:href>/remote.php/dav/calendars/alice/{SHARED_TASK_LIST}/{SHARED_TASK_NAME}</d:href>"
        '<d:propstat><d:prop><d:getetag>"1"</d:getetag>'
        f"<cal:calendar-data>{xml_escape(ics)}</cal:calendar-data></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )


def mock_task_home(mock: respx.MockRouter) -> None:
    mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
        return_value=httpx.Response(207, text=fixture_text("caldav_home_task_lists.xml"))
    )


@pytest.mark.anyio
async def test_a_shared_task_whose_title_and_tags_are_instructions_stays_data(
    clients: NcClients,
) -> None:
    ics = shared_task(
        f"SUMMARY:{INJECTION}",
        f"CATEGORIES:{INJECTION}",
        f"DESCRIPTION:{INJECTION}",
    )
    with respx.mock(assert_all_called=True) as mock:
        mock_task_home(mock)
        mock.route(method="REPORT", url=SHARED_TASK_LIST_URL).mock(
            return_value=httpx.Response(207, text=task_multistatus(ics))
        )
        result = await tasks_tools.search_tasks(clients, list_name="spike30-b-rw")

    hit = result["tasks"][0]
    assert hit["summary"] == INJECTION, "character for character, as data"
    assert hit["tags"] == [INJECTION]
    assert hit["list"] == {"name": "spike30-b-rw", "shared": True, "writable": True}
    assert "description" not in hit, "the description comes only through tasks_read"
    assert INJECTION not in everything_but(result, "tasks")
    assert "bob" not in json.dumps(result)


@pytest.mark.anyio
async def test_a_shared_task_whose_long_description_is_an_instruction_stays_data(
    clients: NcClients,
) -> None:
    filler = "x" * (tasks_tools.MAX_DESCRIPTION_BYTES + 500)
    ics = shared_task("SUMMARY:plain", f"DESCRIPTION:{INJECTION} {filler}")
    task_id = ids.encode_task(ids.task_list_key(SHARED_TASK_LIST), SHARED_TASK_NAME)
    with respx.mock(assert_all_called=True) as mock:
        mock_task_home(mock)
        mock.route(method="GET", url=f"{SHARED_TASK_LIST_URL}{SHARED_TASK_NAME}").mock(
            return_value=httpx.Response(200, text=ics)
        )
        mock.route(method="REPORT", url=SHARED_TASK_LIST_URL).mock(
            return_value=httpx.Response(
                207, text='<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>'
            )
        )
        result = await tasks_tools.read_task(clients, task_id=task_id)

    assert result["description"].startswith(INJECTION), "as data, in the content field"
    assert result["description_truncated"] is True
    assert len(result["description"].encode("utf-8")) == tasks_tools.MAX_DESCRIPTION_BYTES
    assert INJECTION not in everything_but(result, "description")
    for marker in (marks.EXCERPT_TRUNCATION, marks.FINAL_TRUNCATION, "[truncated"):
        assert marker not in result["description"]


@pytest.mark.anyio
async def test_a_forged_marker_in_a_shared_task_title_is_filtered(clients: NcClients) -> None:
    forged = marks.FINAL_TRUNCATION
    ics = shared_task(f"SUMMARY:{INJECTION} {forged}")
    with respx.mock(assert_all_called=True) as mock:
        mock_task_home(mock)
        mock.route(method="REPORT", url=SHARED_TASK_LIST_URL).mock(
            return_value=httpx.Response(207, text=task_multistatus(ics))
        )
        result = await tasks_tools.search_tasks(clients, list_name="spike30-b-rw")

    assert result["tasks"][0]["summary"] == f"{INJECTION} "
    assert forged not in json.dumps(result)

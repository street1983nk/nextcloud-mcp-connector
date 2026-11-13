"""Unit tests for the CalDAV client of the tasks bundle.

The cases follow the classification of plan 32-03 and the measurements of plan 32-02:

* the recorded home of the spike (own lists, a shared list with and without write
  permission, two Deck calendars, trash bin, deleted calendar, inbox, outbox, subscription)
* hand built collections for every kind that must drop out
* the name rule of a shared list: the owner suffix is recognised through
  ``owner-displayname`` and never printed; without a matching suffix the name comes from the
  URI part before the share marker, never from the raw display name
* an account without a task list and a home that answers 404 (case E6) are results
* the REPORT bodies, the object name from the href, the raw bytes, and the status check

The person who shared a list in the fixture is ``bob``. No name, key, message or hint below
may carry that string (D-32-06, D-32-14).
"""

import hashlib
import re
from pathlib import Path

import httpx
import pytest
import respx
from lxml import etree

from mcp_connector import ids
from mcp_connector.errors import (
    REASON_GUARD_TRIPPED,
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ToolError,
)
from mcp_connector.nextcloud.clients import caldav, tasks
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
HOME_PATH = "/remote.php/dav/calendars/alice/"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

OWNER = "bob"
RW_URI = "spike30-b-rw_shared_by_bob"
RO_URI = "spike30-b-ro_shared_by_bob"

ALL_PRIVILEGES = ("write", "write-properties", "write-content", "bind", "unbind", "read")
READ_PRIVILEGES = ("write-properties", "read", "read-acl")

NS = (
    'xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav" '
    'xmlns:cs="http://calendarserver.org/ns/" xmlns:oc="http://owncloud.org/ns" '
    'xmlns:x1="http://nextcloud.com/ns"'
)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def collection(
    uri: str,
    *,
    types: str = "<cal:calendar/>",
    components: tuple[str, ...] = ("VTODO",),
    privileges: tuple[str, ...] = ALL_PRIVILEGES,
    displayname: str | None = None,
    read_only: str | None = None,
    owner: str | None = None,
) -> str:
    """One ``d:response`` the way sabre writes it: found props in 200, missing in 404."""
    found = [f"<d:resourcetype><d:collection/>{types}</d:resourcetype>"]
    missing: list[str] = []
    if displayname is None:
        missing.append("<d:displayname/>")
    else:
        found.append(f"<d:displayname>{displayname}</d:displayname>")
    comps = "".join(f'<cal:comp name="{name}"/>' for name in components)
    found.append(
        f"<cal:supported-calendar-component-set>{comps}</cal:supported-calendar-component-set>"
    )
    privs = "".join(f"<d:privilege><d:{name}/></d:privilege>" for name in privileges)
    found.append(f"<d:current-user-privilege-set>{privs}</d:current-user-privilege-set>")
    if read_only is None:
        missing.append("<oc:read-only/>")
    else:
        found.append(f"<oc:read-only>{read_only}</oc:read-only>")
    if owner is None:
        missing.append("<x1:owner-displayname/>")
    else:
        found.append(f"<x1:owner-displayname>{owner}</x1:owner-displayname>")
    return (
        f"<d:response><d:href>{HOME_PATH}{uri}/</d:href>"
        f"<d:propstat><d:prop>{''.join(found)}</d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        f"<d:propstat><d:prop>{''.join(missing)}</d:prop>"
        "<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat></d:response>"
    )


def home(*responses: str) -> bytes:
    own_home = (
        f"<d:response><d:href>{HOME_PATH}</d:href><d:propstat><d:prop>"
        "<d:resourcetype><d:collection/></d:resourcetype></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
    )
    body = f'<?xml version="1.0"?><d:multistatus {NS}>{own_home}{"".join(responses)}'
    return (body + "</d:multistatus>").encode("utf-8")


def parse(*responses: str) -> list[tasks.TaskList]:
    return tasks.parse_task_home(home(*responses), home_path=HOME_PATH)


def by_uri(lists: list[tasks.TaskList]) -> dict[str, tasks.TaskList]:
    return {entry.uri: entry for entry in lists}


def assert_no_owner(lists: list[tasks.TaskList]) -> None:
    for entry in lists:
        assert OWNER not in entry.name, entry
        assert OWNER not in entry.key, entry
        assert "_shared_by_" not in entry.name, entry
        assert "_shared_by_" not in entry.key, entry


def shared_key(uri: str) -> str:
    return "s" + hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------------------
# Discovery on the recorded home of the spike
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_recorded_home_yields_own_and_shared_lists_and_nothing_else(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=httpx.Response(207, content=fixture_bytes("caldav_home_task_lists.xml"))
        )
        lists = await tasks.discover_task_lists(client, creds)

    assert [entry.uri for entry in lists] == [
        "spike30-aufgaben",
        "spike30-gemischt",
        RW_URI,
        RO_URI,
    ], "Deck, deleted calendar, inbox, outbox, trash bin and subscription drop out"
    assert_no_owner(lists)

    request = route.calls[0].request
    assert request.headers["Depth"] == "1"
    assert request.headers["Content-Type"] == "application/xml"


@pytest.mark.anyio
async def test_no_deck_calendar_is_ever_a_task_list(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    """E9: type and components of a Deck calendar look exactly like a task list."""
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=httpx.Response(207, content=fixture_bytes("caldav_home_task_lists.xml"))
        )
        lists = await tasks.discover_task_lists(client, creds)

    assert not [entry for entry in lists if entry.uri.startswith("app-generated--")]
    assert not [entry for entry in lists if entry.name.startswith("Deck:")]


def test_the_own_list_is_own_writable_and_keyed_by_its_uri() -> None:
    lists = by_uri(
        tasks.parse_task_home(fixture_bytes("caldav_home_task_lists.xml"), home_path=HOME_PATH)
    )

    own = lists["spike30-aufgaben"]
    assert own.shared is False
    assert own.own is True
    assert own.writable is True
    assert own.key == "spike30-aufgaben"
    assert own.name == "spike30-aufgaben"


def test_the_shared_list_with_write_permission_is_shared_writable_and_neutral() -> None:
    lists = by_uri(
        tasks.parse_task_home(fixture_bytes("caldav_home_task_lists.xml"), home_path=HOME_PATH)
    )

    shared = lists[RW_URI]
    assert shared.shared is True
    assert shared.own is False
    assert shared.writable is True
    assert shared.key == shared_key(RW_URI)
    assert re.fullmatch(r"s[0-9a-f]{16}", shared.key)
    assert shared.key == ids.task_list_key(RW_URI)
    assert shared.name == "spike30-b-rw", "never the raw display name with ' (bob)'"
    assert " (bob)" not in shared.name


def test_the_read_only_shared_list_is_shared_and_not_writable() -> None:
    lists = by_uri(
        tasks.parse_task_home(fixture_bytes("caldav_home_task_lists.xml"), home_path=HOME_PATH)
    )

    shared = lists[RO_URI]
    assert shared.shared is True
    assert shared.writable is False
    assert shared.name == "spike30-b-ro"
    assert shared.key == shared_key(RO_URI)


def test_no_name_and_no_key_of_the_recorded_home_names_the_owner() -> None:
    lists = tasks.parse_task_home(fixture_bytes("caldav_home_task_lists.xml"), home_path=HOME_PATH)
    assert_no_owner(lists)
    assert all(OWNER not in repr((entry.key, entry.name)) for entry in lists)


# --------------------------------------------------------------------------------------
# Every kind that is not a task list, hand built
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "types", "components"),
    [
        ("papierkorb", "<x1:trash-bin/>", ("VTODO",)),
        ("trashbin", "<cal:calendar/>", ("VTODO",)),
        ("weg", "<cal:calendar/><x1:deleted-calendar/>", ("VTODO",)),
        ("weg-ohne-typ", "<x1:deleted-calendar/>", ("VTODO",)),
        ("eingang", "<cal:schedule-inbox/>", ("VTODO",)),
        ("ausgang", "<cal:schedule-outbox/>", ("VTODO",)),
        ("inbox", "<cal:calendar/>", ("VTODO",)),
        ("outbox", "<cal:calendar/>", ("VTODO",)),
        ("abo", "<cs:subscribed/>", ("VTODO", "VEVENT")),
        ("abo-als-kalender", "<cal:calendar/><cs:subscribed/>", ("VTODO",)),
        ("ordner", "", ("VTODO",)),
        ("termine", "<cal:calendar/>", ("VEVENT",)),
        ("ohne-komponenten", "<cal:calendar/>", ()),
        ("app-generated--deck--board-9", "<cal:calendar/>", ("VTODO",)),
    ],
)
def test_a_collection_that_is_no_task_list_is_left_out(
    uri: str, types: str, components: tuple[str, ...]
) -> None:
    assert parse(collection(uri, types=types, components=components)) == []


def test_a_collection_with_vevent_and_vtodo_is_a_task_list() -> None:
    lists = parse(collection("gemischt", components=("VEVENT", "VTODO")))
    assert [entry.uri for entry in lists] == ["gemischt"]


def test_the_home_itself_is_never_a_task_list() -> None:
    assert parse() == []


# --------------------------------------------------------------------------------------
# shared and writable
# --------------------------------------------------------------------------------------


def test_a_list_with_read_only_in_a_2xx_propstat_is_shared_even_without_the_uri_marker() -> None:
    entry = parse(collection("team", displayname="Team", read_only="", owner="Carol"))[0]
    assert entry.shared is True
    assert entry.writable is True


def test_a_list_with_the_uri_marker_is_shared_even_without_read_only() -> None:
    entry = parse(collection("team_shared_by_bob", displayname="Team (Bob B.)"))[0]
    assert entry.shared is True
    assert entry.key == shared_key("team_shared_by_bob")
    assert_no_owner([entry])


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_a_read_only_share_is_never_writable_whatever_its_privileges(value: str) -> None:
    entry = parse(collection(RW_URI, read_only=value, privileges=ALL_PRIVILEGES))[0]
    assert entry.writable is False


@pytest.mark.parametrize("value", ["", "0", "false", "FALSE"])
def test_a_share_with_write_permission_is_writable(value: str) -> None:
    entry = parse(collection(RW_URI, read_only=value, privileges=("bind", "read")))[0]
    assert entry.writable is True


@pytest.mark.parametrize("privilege", ["write", "write-content", "bind", "all"])
def test_each_decided_privilege_alone_allows_writing(privilege: str) -> None:
    entry = parse(collection("own", privileges=(privilege, "read")))[0]
    assert entry.writable is True


def test_write_properties_alone_does_not_allow_writing() -> None:
    """32-02: write-properties stands on read only shares and on Deck calendars too."""
    entry = parse(collection("own", privileges=READ_PRIVILEGES))[0]
    assert entry.writable is False


# --------------------------------------------------------------------------------------
# The name rule (D-32-14, ENTSCHEID namensregel=owner-displayname)
# --------------------------------------------------------------------------------------


def test_the_owner_suffix_is_removed_when_it_matches_owner_displayname() -> None:
    entry = parse(collection(RW_URI, displayname="Team-Aufgaben (bob)", read_only="", owner="bob"))[
        0
    ]
    assert entry.name == "Team-Aufgaben"
    assert_no_owner([entry])


def test_an_owner_name_with_brackets_of_its_own_is_removed_whole() -> None:
    entry = parse(
        collection(
            "x_shared_by_bob", displayname="Plan (bob (Team))", read_only="", owner="bob (Team)"
        )
    )[0]
    assert entry.name == "Plan"


def test_a_suffix_that_does_not_match_never_leaves_the_raw_display_name() -> None:
    entry = parse(
        collection(RW_URI, displayname="Team-Aufgaben (bob)", read_only="", owner="Robert")
    )[0]
    assert entry.name == "spike30-b-rw"
    assert_no_owner([entry])


def test_a_missing_owner_displayname_falls_back_to_the_uri_part() -> None:
    entry = parse(collection(RW_URI, displayname="Team-Aufgaben (bob)", read_only=""))[0]
    assert entry.name == "spike30-b-rw"


def test_a_shared_list_without_a_display_name_falls_back_to_the_uri_part() -> None:
    entry = parse(collection(RW_URI, read_only="", owner="bob"))[0]
    assert entry.name == "spike30-b-rw"


def test_a_shared_list_with_nothing_before_the_marker_is_named_by_its_key() -> None:
    uri = "_shared_by_bob"
    entry = parse(collection(uri, displayname="(bob)", read_only="", owner="bob"))[0]
    assert entry.name == shared_key(uri)
    assert_no_owner([entry])


def test_a_name_that_is_only_the_suffix_is_not_an_empty_name() -> None:
    entry = parse(collection(RW_URI, displayname=" (bob)", read_only="", owner="bob"))[0]
    assert entry.name == "spike30-b-rw"


def test_an_own_list_keeps_its_display_name_unchanged() -> None:
    entry = parse(collection("mine", displayname="Mine (alice)", owner="alice"))[0]
    assert entry.shared is False
    assert entry.name == "Mine (alice)"
    assert entry.key == "mine"


def test_an_own_list_without_a_display_name_is_named_by_its_uri() -> None:
    entry = parse(collection("ohne-name"))[0]
    assert entry.name == "ohne-name"


# --------------------------------------------------------------------------------------
# E6: no task list, and a home that answers 404
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_fresh_account_with_only_event_calendars_has_no_task_list(
    client: httpx.AsyncClient,
) -> None:
    fresh = Credentials(BASE, "fresh30", SECRET)
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=f"{BASE}/remote.php/dav/calendars/fresh30/").mock(
            return_value=httpx.Response(207, content=fixture_bytes("caldav_home_fresh_account.xml"))
        )
        assert await tasks.discover_task_lists(client, fresh) == []


@pytest.mark.anyio
async def test_a_home_that_answers_404_is_no_task_list_and_no_error(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=httpx.Response(404, text="not found")
        )
        assert await tasks.discover_task_lists(client, creds) == []


@pytest.mark.anyio
async def test_an_empty_207_is_no_task_list_and_no_error(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    """32-02 measured exactly this for an account that never logged in."""
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=httpx.Response(207, content=home())
        )
        assert await tasks.discover_task_lists(client, creds) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "needle"),
    [
        (401, "app password"),
        (403, "permission"),
        (302, "redirect"),
        (500, "500"),
        (503, "503"),
        (429, "rate limiting"),
    ],
)
async def test_other_statuses_of_the_discovery_are_errors_with_bundle_hints(
    client: httpx.AsyncClient, creds: Credentials, status: int, needle: str
) -> None:
    headers = {"Location": "http://evil.test/"} if 300 <= status < 400 else {}
    with respx.mock(assert_all_called=True) as mock:
        route = mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=httpx.Response(status, text="x", headers=headers)
        )
        with pytest.raises(ToolError) as excinfo:
            await tasks.discover_task_lists(client, creds)

    assert route.call_count == 1, "no retry, ever"
    assert needle in excinfo.value.message.lower()
    assert "calendar_" not in excinfo.value.hint
    assert "calendar_" not in excinfo.value.message
    if status == 403:
        assert excinfo.value.reason == REASON_PERMISSION_DENIED


def test_the_discovery_body_asks_for_everything_the_classification_reads() -> None:
    body = etree.fromstring(tasks.build_task_discovery_body(), parser=davxml.hardened_parser())
    asked = {str(element.tag) for element in body.iter() if isinstance(element.tag, str)}
    assert f"{{{davxml.DAV}}}displayname" in asked
    assert f"{{{davxml.DAV}}}resourcetype" in asked
    assert f"{{{davxml.CAL}}}supported-calendar-component-set" in asked
    assert f"{{{davxml.DAV}}}current-user-privilege-set" in asked
    assert f"{{{davxml.OC}}}read-only" in asked
    assert "{http://nextcloud.com/ns}owner-displayname" in asked
    assert "{http://nextcloud.org/ns}owner-displayname" not in asked


def test_the_calendar_discovery_body_is_not_the_task_discovery_body() -> None:
    assert tasks.build_task_discovery_body() != caldav.build_discovery_body()


# --------------------------------------------------------------------------------------
# REPORT bodies
# --------------------------------------------------------------------------------------


def _tree(body: bytes) -> etree._Element:
    return etree.fromstring(body, parser=davxml.hardened_parser())


def _no_window(root: etree._Element) -> None:
    assert root.find(f".//{{{davxml.CAL}}}time-range") is None
    assert root.find(f".//{{{davxml.CAL}}}expand") is None


def test_the_todo_query_for_all_tasks_has_no_narrowing() -> None:
    root = _tree(tasks.build_todo_query(None))
    comps = [element.get("name") for element in root.findall(f".//{{{davxml.CAL}}}comp-filter")]
    assert comps == ["VCALENDAR", "VTODO"]
    assert root.find(f".//{{{davxml.CAL}}}prop-filter") is None
    assert root.find(f".//{{{davxml.CAL}}}calendar-data") is not None
    _no_window(root)


def test_the_todo_query_for_open_tasks_asks_for_completed_not_defined() -> None:
    root = _tree(tasks.build_todo_query(completed=False))
    prop_filter = root.find(f".//{{{davxml.CAL}}}prop-filter")
    assert prop_filter is not None
    assert prop_filter.get("name") == "COMPLETED"
    assert prop_filter.find(f"{{{davxml.CAL}}}is-not-defined") is not None
    _no_window(root)


def test_the_todo_query_for_done_tasks_asks_for_completed_defined() -> None:
    root = _tree(tasks.build_todo_query(completed=True))
    prop_filter = root.find(f".//{{{davxml.CAL}}}prop-filter")
    assert prop_filter is not None
    assert prop_filter.get("name") == "COMPLETED"
    assert prop_filter.find(f"{{{davxml.CAL}}}is-not-defined") is None
    _no_window(root)


@pytest.mark.parametrize("prop", ["RELATED-TO", "UID"])
def test_the_related_query_uses_the_decided_text_match(prop: str) -> None:
    root = _tree(tasks.build_related_query(prop, "parent-uid-1"))
    prop_filter = root.find(f".//{{{davxml.CAL}}}prop-filter")
    assert prop_filter is not None
    assert prop_filter.get("name") == prop
    match = prop_filter.find(f"{{{davxml.CAL}}}text-match")
    assert match is not None
    assert match.get("collation") == "i;octet"
    assert match.get("match-type") == "contains"
    assert match.text == "parent-uid-1"
    _no_window(root)


def test_a_uid_with_markup_stays_text_in_the_related_query() -> None:
    root = _tree(tasks.build_related_query("UID", "<x/>&amp;"))
    match = root.find(f".//{{{davxml.CAL}}}text-match")
    assert match is not None
    assert match.text == "<x/>&amp;"


def test_the_related_query_refuses_another_property() -> None:
    with pytest.raises(ValueError, match="prop must be one of"):
        tasks.build_related_query("SUMMARY", "x")


def test_the_related_query_refuses_an_empty_uid_before_any_request() -> None:
    with pytest.raises(ToolError) as excinfo:
        tasks.build_related_query("RELATED-TO", "  ")
    assert excinfo.value.reason == REASON_GUARD_TRIPPED


# --------------------------------------------------------------------------------------
# query_todos and get_todo
# --------------------------------------------------------------------------------------

SHARED_LIST = tasks.TaskList(
    uri=RW_URI, key=shared_key(RW_URI), name="spike30-b-rw", shared=True, writable=True
)
SHARED_URL = f"{CALENDAR_HOME}{RW_URI}/"


def report(*entries: tuple[str, str | None]) -> bytes:
    parts = []
    for href, data in entries:
        prop = '<d:getetag>"e"</d:getetag>'
        if data is not None:
            prop += f"<cal:calendar-data>{data}</cal:calendar-data>"
        parts.append(
            f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{prop}</d:prop>"
            "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        )
    body = f'<?xml version="1.0"?><d:multistatus {NS}>{"".join(parts)}</d:multistatus>'
    return body.encode("utf-8")


TODO_TEXT = (
    "BEGIN:VCALENDAR&#13;\nBEGIN:VTODO&#13;\nUID:uid-a&#13;\nEND:VTODO&#13;\nEND:VCALENDAR&#13;\n"
)


@pytest.mark.anyio
async def test_query_todos_names_objects_by_their_href_and_keeps_the_raw_bytes(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = tasks.build_todo_query(None)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.route(method="REPORT", url=SHARED_URL).mock(
            return_value=httpx.Response(
                207,
                content=report(
                    (f"{HOME_PATH}{RW_URI}/a%20b.ics", TODO_TEXT),
                    (f"{HOME_PATH}{RW_URI}/without-data.ics", None),
                    (f"{HOME_PATH}{RW_URI}/blank.ics", "   "),
                    (f"{HOME_PATH}{RW_URI}/", TODO_TEXT),
                ),
            )
        )
        found = await tasks.query_todos(client, creds, SHARED_LIST, body)

    assert [entry.object_name for entry in found] == ["a b.ics"], "name from the href, not UID"
    assert found[0].ics.startswith(b"BEGIN:VCALENDAR\r\n"), "raw bytes, CRLF kept, unparsed"
    assert b"UID:uid-a\r\n" in found[0].ics

    request = route.calls[0].request
    assert request.headers["Depth"] == "1"
    assert request.content == body


@pytest.mark.anyio
async def test_query_todos_reports_a_failure_with_the_list_name_only(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="REPORT", url=SHARED_URL).mock(return_value=httpx.Response(503))
        with pytest.raises(ToolError) as excinfo:
            await tasks.query_todos(client, creds, SHARED_LIST, tasks.build_todo_query())

    assert "spike30-b-rw" in excinfo.value.message
    assert OWNER not in f"{excinfo.value.message} {excinfo.value.hint}"


@pytest.mark.anyio
async def test_get_todo_returns_the_stored_bytes(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    stored = fixture_bytes("tasks_app/subtask.ics")
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(f"{SHARED_URL}x.ics").mock(
            return_value=httpx.Response(
                200, content=stored, headers={"Content-Type": "text/calendar; charset=utf-8"}
            )
        )
        assert await tasks.get_todo(client, creds, SHARED_LIST, "x.ics") == stored

    assert route.calls[0].request.headers["Accept"] == "text/calendar"


@pytest.mark.anyio
async def test_get_todo_404_is_an_unknown_task_without_the_shared_uri(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{SHARED_URL}gone.ics").mock(return_value=httpx.Response(404))
        with pytest.raises(ToolError) as excinfo:
            await tasks.get_todo(client, creds, SHARED_LIST, "gone.ics")

    error = excinfo.value
    assert error.reason == REASON_UNKNOWN_ID
    assert error.message.startswith("Nextcloud does not know the task gone.ics")
    text = f"{error.message} {error.hint}"
    assert OWNER not in text
    assert "_shared_by_" not in text
    assert "tasks_search" in error.hint
    assert "calendar_" not in text


# --------------------------------------------------------------------------------------
# The task wording of the one writer
# --------------------------------------------------------------------------------------


def test_the_task_wording_never_claims_a_list_is_gone() -> None:
    wording = tasks.TASK_WORDING
    assert "not found or does not allow writing" in wording.missing
    assert "does not exist" not in wording.missing
    assert "list=" in wording.forbidden_hint
    for hint in (
        wording.replaced_hint,
        wording.exists_hint,
        wording.forbidden_hint,
        wording.missing_hint,
        wording.unsupported_hint,
        wording.unexpected_hint,
    ):
        assert "calendar_" not in hint, hint
    assert "tasks_search" in wording.missing_hint


@pytest.mark.anyio
async def test_a_write_to_a_shared_list_names_the_list_and_not_its_owner(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.put(f"{SHARED_URL}new.ics").mock(return_value=httpx.Response(404))
        with pytest.raises(ToolError) as excinfo:
            await caldav.put_new_object(
                client,
                creds,
                SHARED_LIST.uri,
                "new.ics",
                b"x",
                tasks.TASK_WORDING,
                SHARED_LIST.name,
            )

    error = excinfo.value
    assert error.reason == REASON_UNKNOWN_ID
    assert error.message == "The task list spike30-b-rw was not found or does not allow writing."
    assert OWNER not in f"{error.message} {error.hint}"


# --------------------------------------------------------------------------------------
# Source guards
# --------------------------------------------------------------------------------------


def test_the_module_shares_no_event_reader_of_the_calendar_client() -> None:
    """The event reader flattens floating times to UTC and walks VEVENT only (I3)."""
    source = Path(tasks.__file__).read_text(encoding="utf-8")
    for name in ("_value_of", "parse_ics", "_ok_props", "parse_calendar_home"):
        assert name not in source, name


def test_the_module_builds_its_bodies_with_lxml() -> None:
    source = Path(tasks.__file__).read_text(encoding="utf-8")
    assert "<c:" not in source
    assert "<d:" not in source


def test_the_own_property_is_the_opposite_of_shared() -> None:
    assert SHARED_LIST.own is False
    own = tasks.TaskList(uri="t", key="t", name="t", shared=False, writable=True)
    assert own.own is True

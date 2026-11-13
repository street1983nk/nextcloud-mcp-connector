"""Unit tests for the one generic create-only CalDAV writer (TASK-07, TASK-06).

``caldav.py`` carries exactly one ``.put(``, and the gate in
``tests/contract/test_no_destructive_calls.py`` counts it. The writer takes its wording as a
parameter, so a task list gets task sentences and an event calendar keeps the sentences it
had before phase 32, word for word. The wording below is a test wording: the real one for
tasks lives in ``clients/tasks.py``.

Two promises are pinned here beside the status branches: the label the caller hands in is
the only name of the collection a sentence carries (the URI of a shared list holds the
account id of its owner, D-32-14), and the 404 sentence of the task wording does not claim
that the list does not exist (D-31-09: a read only shared list answers a PUT with 404).
"""

import httpx
import pytest
import respx

from mcp_connector.errors import (
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from mcp_connector.nextcloud.clients import caldav
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
PERSONAL = f"{CALENDAR_HOME}personal/"
SHARED_URI = "team-list_shared_by_bob"
SHARED = f"{CALENDAR_HOME}{SHARED_URI}/"
LABEL = "Team"

TEST_WORDING = caldav.WriteWording(
    replaced="The write replaced an existing task {name} (status {status}).",
    replaced_hint="Report this instance; it ignores If-None-Match.",
    exists="A task object named {name} already exists.",
    exists_hint="Create the task again; it gets a new name.",
    forbidden="No permission to write to the task list {label}.",
    forbidden_hint="Name a list you can write to with list=...",
    missing="The task list {label} was not found or does not allow writing.",
    missing_hint="Call tasks_search once to see the task lists of this account.",
    unsupported="Nextcloud rejected the task as an unsupported media type.",
    unsupported_hint="This is a bug in this connector; please report it.",
    what="the task list {label}",
    unexpected="Nextcloud answered the new task with an unexpected status {status}.",
    unexpected_hint="Check the Nextcloud log; the task was probably not created.",
)


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


async def _write(
    client: httpx.AsyncClient, creds: Credentials, response: httpx.Response
) -> dict[str, object]:
    with respx.mock(assert_all_called=True) as mock:
        mock.put(f"{SHARED}new.ics").mock(return_value=response)
        return await caldav.put_new_object(
            client, creds, SHARED_URI, "new.ics", b"x", TEST_WORDING, LABEL
        )


async def _refusal(
    client: httpx.AsyncClient, creds: Credentials, response: httpx.Response
) -> ToolError:
    with pytest.raises(ToolError) as excinfo:
        await _write(client, creds, response)
    error = excinfo.value
    text = f"{error.message} {error.hint}"
    assert "bob" not in text, "the URI of a shared list never reaches a sentence"
    assert "_shared_by_" not in text
    assert "calendar_" not in text, "a task sentence never names a tool of another bundle"
    return error


# --------------------------------------------------------------------------------------
# The generic writer
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_201_is_a_creation_with_its_etag(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.put(f"{SHARED}new.ics").mock(
            return_value=httpx.Response(201, headers={"ETag": '"e1"'})
        )
        result = await caldav.put_new_object(
            client, creds, SHARED_URI, "new.ics", b"BEGIN:VCALENDAR\r\n", TEST_WORDING, LABEL
        )

    request = route.calls[0].request
    assert request.headers["If-None-Match"] == "*"
    assert request.headers["Content-Type"] == "text/calendar; charset=utf-8"
    assert request.content == b"BEGIN:VCALENDAR\r\n"
    assert result["created"] is True
    assert result["etag"] == '"e1"'
    assert result["object_name"] == "new.ics"
    assert SHARED_URI not in result.values(), "the result never carries the collection URI"


@pytest.mark.anyio
@pytest.mark.parametrize("status", [200, 204])
async def test_a_replacing_answer_uses_the_replaced_sentence(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    error = await _refusal(client, creds, httpx.Response(status))
    assert error.message == f"The write replaced an existing task new.ics (status {status})."
    assert error.hint == TEST_WORDING.replaced_hint


@pytest.mark.anyio
async def test_a_412_is_a_conflict_with_the_exists_sentence(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(client, creds, httpx.Response(412, text="exists"))
    assert isinstance(error, ConflictError)
    assert error.message == "A task object named new.ics already exists."
    assert error.hint == TEST_WORDING.exists_hint


@pytest.mark.anyio
async def test_a_403_is_permission_denied_and_names_the_label(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(client, creds, httpx.Response(403, text="forbidden"))
    assert error.reason == REASON_PERMISSION_DENIED
    assert error.message == "No permission to write to the task list Team."
    assert "list=" in error.hint


@pytest.mark.anyio
@pytest.mark.parametrize("status", [404, 409])
async def test_a_404_or_409_says_not_found_or_not_writable(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    """D-31-09: a read only shared list answers 404, so "does not exist" would be a guess."""
    error = await _refusal(client, creds, httpx.Response(status, text="nope"))
    assert error.reason == REASON_UNKNOWN_ID
    assert error.message == "The task list Team was not found or does not allow writing."
    assert "not found or does not allow writing" in error.message
    assert "does not exist" not in error.message


@pytest.mark.anyio
async def test_a_415_uses_the_unsupported_sentence(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(client, creds, httpx.Response(415))
    assert error.message == TEST_WORDING.unsupported


@pytest.mark.anyio
async def test_a_server_error_goes_through_the_general_checker_with_the_label(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(client, creds, httpx.Response(503, text="down"))
    assert "503" in error.message
    assert "the task list Team" in error.message


@pytest.mark.anyio
async def test_a_rejected_password_goes_through_the_general_checker(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(client, creds, httpx.Response(401))
    assert "app password" in error.message.lower()


@pytest.mark.anyio
async def test_a_redirect_goes_through_the_general_checker_with_the_label(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(
        client, creds, httpx.Response(302, headers={"Location": "http://evil.test/"})
    )
    assert "redirect" in error.message.lower()
    assert "the task list Team" in error.message


@pytest.mark.anyio
async def test_any_other_status_uses_the_unexpected_sentence(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await _refusal(client, creds, httpx.Response(207))
    assert error.message == "Nextcloud answered the new task with an unexpected status 207."
    assert error.hint == TEST_WORDING.unexpected_hint


def test_the_module_still_carries_exactly_one_put() -> None:
    """The count gate holds the whole code base; this holds the one module (TASK-07)."""
    from pathlib import Path

    source = Path(caldav.__file__).read_text(encoding="utf-8")
    assert source.count(".put(") == 1


# --------------------------------------------------------------------------------------
# put_event is a wrapper and says what it said before phase 32
# --------------------------------------------------------------------------------------


async def _event_refusal(
    client: httpx.AsyncClient, creds: Credentials, response: httpx.Response
) -> ToolError:
    with respx.mock(assert_all_called=True) as mock:
        mock.put(f"{PERSONAL}ev.ics").mock(return_value=response)
        with pytest.raises(ToolError) as excinfo:
            await caldav.put_event(client, creds, "personal", "ev.ics", b"x")
    return excinfo.value


@pytest.mark.anyio
async def test_put_event_returns_the_same_shape_as_before(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.put(f"{PERSONAL}ev.ics").mock(
            return_value=httpx.Response(201, headers={"ETag": '"e2"'})
        )
        result = await caldav.put_event(client, creds, "personal", "ev.ics", b"x")

    assert result == {
        "calendar": "personal",
        "object_name": "ev.ics",
        "etag": '"e2"',
        "created": True,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "message", "hint", "reason"),
    [
        (
            204,
            "Nextcloud reports that the write replaced an existing event ev.ics (status 204).",
            (
                "This server sends If-None-Match: * and expects a refusal instead. Report "
                "this instance: it does not honour the precondition."
            ),
            None,
        ),
        (
            412,
            "An event object named ev.ics already exists.",
            "This server never overwrites events. Create the event under a new name.",
            None,
        ),
        (
            403,
            "No permission to write to the calendar personal.",
            "Pick one of your own calendars, or ask its owner for write permission.",
            REASON_PERMISSION_DENIED,
        ),
        (
            404,
            "The calendar personal does not exist.",
            "Call calendar_list_events once to see the calendars of this account.",
            REASON_UNKNOWN_ID,
        ),
        (
            409,
            "The calendar personal does not exist.",
            "Call calendar_list_events once to see the calendars of this account.",
            REASON_UNKNOWN_ID,
        ),
        (
            415,
            "Nextcloud rejected the event as an unsupported media type.",
            "This is a bug in this connector; please report it with the event data.",
            None,
        ),
        (
            503,
            "Nextcloud reported a server error (503) for the calendar personal.",
            "This is a problem on the Nextcloud side. Retry later or check its log.",
            None,
        ),
        (
            207,
            "Nextcloud answered the new event with an unexpected status 207.",
            "Check the Nextcloud log for that request; the event was probably not created.",
            None,
        ),
    ],
)
async def test_put_event_keeps_every_sentence_word_for_word(
    client: httpx.AsyncClient,
    creds: Credentials,
    status: int,
    message: str,
    hint: str,
    reason: str | None,
) -> None:
    error = await _event_refusal(client, creds, httpx.Response(status, text="x"))
    assert error.message == message
    assert error.hint == hint
    if reason is not None:
        assert error.reason == reason

"""What one recorded tool call may say, and what it may cost.

Two questions run through this file. The first is the boundary of T-18-01: a row names the
parameters that were *set* and nothing else, so the case that matters most here is the one
that searches a conspicuous value in **every** column of the written row and does not find
it. The second is D-13: a log that cannot write must not end the call it was recording, so a
store double that raises on every append is a case and not a hope.

Nothing here needs a running server. The wrapper ``graceful`` builds is called directly with
a context assembled by hand, in the shape ``test_oauth_credentials.py`` and
``test_audit_caller.py`` build theirs, and nothing is registered on the module singleton
``mcp``: ``tests/contract/test_tool_surface.py`` compares the registry against a frozen
literal, so a leftover test tool would turn that file red.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from starlette.requests import Request

from mcp_connector.audit import AUDIT_STATE_ATTR
from mcp_connector.audit.record import Recorder
from mcp_connector.audit.store import CLIENT_NAME_LIMIT, AuditStore, Entry
from mcp_connector.errors import (
    REASON_PERMISSION_DENIED,
    REASON_UNSPECIFIED,
    ToolError,
)
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity
from mcp_connector.server import graceful

#: A real tool of the allowlist, so the intersection in the recorder is the real one. Its
#: allowed names are ``cursor``, ``limit`` and ``path``.
TOOL = "files_list"

NC_USER = "alice"
AUTH_ID = "the-flow-this-authorization-was-born-in"
CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
CLIENT_NAME = "Claude"

#: The value the third case hunts for. It is not a word of any column name, so a hit is a
#: leak and never a coincidence.
SECRET_VALUE = "SECRETVALUE"

#: The two halves of a refusal, both of them written for the model and both of them naming a
#: real path. Neither may appear in a row (T-18-01).
REFUSAL_MESSAGE = "No permission to write to /private/payroll-2026.txt."
REFUSAL_HINT = "Ask the owner of the folder to share it with write permission."


def identity(client_name: str = CLIENT_NAME) -> OAuthIdentity:
    """The identity the transport boundary resolves once per request."""
    return OAuthIdentity(
        nc_user=NC_USER,
        principal=NC_USER,
        app_password="aaaaa-bbbbb-ccccc-ddddd-eeeee",
        auth_id=AUTH_ID,
        client_id=CLIENT_ID,
        client_name=client_name,
    )


class FakeRequestContext:
    """What the SDK hands a tool: the request of the message, and the call parameters."""

    def __init__(self, request: Request, params: Any) -> None:
        self.request = request
        self.params = params


class FakeContext:
    """A tool context with a request the two readers of the recording path can read."""

    def __init__(
        self,
        *,
        params: Any = None,
        recorder: object | None = None,
        who: OAuthIdentity | None = None,
    ) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [],
            }
        )
        if who is not None:
            setattr(request.state, OAUTH_STATE_ATTR, who)
        if recorder is not None:
            setattr(request.state, AUDIT_STATE_ATTR, recorder)
        self.headers: dict[str, str] = {}
        self.request_context = FakeRequestContext(request, params)


def call_of(**arguments: Any) -> dict[str, Any]:
    """The parameters of one ``tools/call`` message, with exactly the keys that were set."""
    return {"name": TOOL, "arguments": dict(arguments)}


class ExplodingStore(AuditStore):
    """A store that cannot write, in the one way a deployment really breaks: the volume.

    The message carries a path on purpose. It is what the fail-open case asserts must not
    reach the log, because the rule of D-13 is the type of the failure and never its
    sentence.
    """

    async def append(self, entry: Entry) -> int:
        raise OSError("no space left on device: /var/lib/mcp_connector/audit.sqlite3")


@pytest.fixture
def audit_file(tmp_path: Path) -> Path:
    """The path of the store this file writes to, so a test can read it back by hand."""
    return tmp_path / "audit.sqlite3"


@pytest.fixture
def recorder(audit_file: Path) -> Recorder:
    """A recorder over a real store in ``tmp_path``: no double, no patch, a real file."""
    store = AuditStore(audit_file)

    async def provider() -> AuditStore:
        return store

    return Recorder(store_provider=provider)


def written(path: Path) -> list[dict[str, Any]]:
    """Every row of the store, read with a connection of our own and past the store API."""
    if not path.exists():
        return []
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM entries ORDER BY seq")]
    finally:
        connection.close()


def one_row(path: Path) -> dict[str, Any]:
    """The single row a single recorded call leaves behind."""
    rows = written(path)
    assert len(rows) == 1, f"expected exactly one recorded call, found {len(rows)}"
    return rows[0]


def every_column(row: dict[str, Any]) -> str:
    """Every value of the row as one string, so a search covers the whole row and not a field."""
    return "\n".join(f"{name}={value!r}" for name, value in row.items())


@graceful
async def probe(ctx: Any = None, path: str = "/", limit: int = 25) -> str:
    """A tool shaped function with a default the caller does not set (pitfall 1)."""
    return "answered"


@graceful
async def refusing(ctx: Any = None, *, error: BaseException) -> str:
    """A tool shaped function that ends in the exception the case hands it."""
    raise error


@pytest.mark.anyio
async def test_only_the_names_the_caller_set_are_recorded(
    recorder: Recorder, audit_file: Path
) -> None:
    """Pitfall 1: the SDK materialises ``limit`` before the call, the message does not have it."""
    context = FakeContext(params=call_of(path="/notes"), recorder=recorder, who=identity())

    # Exactly how the SDK calls it: every field of the argument model, defaults included.
    assert await probe(ctx=context, path="/notes", limit=25) == "answered"

    assert one_row(audit_file)["params"] == '["path"]'


@pytest.mark.anyio
async def test_an_invented_parameter_name_reaches_no_entry(
    recorder: Recorder, audit_file: Path
) -> None:
    """T-18-02: an unknown key stands in the message even after pydantic threw it away."""
    context = FakeContext(
        params=call_of(path="/notes", not_a_parameter="anything"),
        recorder=recorder,
        who=identity(),
    )

    await probe(ctx=context, path="/notes")

    assert one_row(audit_file)["params"] == '["path"]'


@pytest.mark.anyio
async def test_no_column_of_the_entry_carries_a_parameter_value(
    recorder: Recorder, audit_file: Path
) -> None:
    """T-18-01, and the search covers the whole row rather than the parameter column alone."""
    context = FakeContext(params=call_of(path=SECRET_VALUE), recorder=recorder, who=identity())

    await probe(ctx=context, path=SECRET_VALUE)

    row = every_column(one_row(audit_file))
    assert SECRET_VALUE not in row, f"a parameter value reached a column of the entry:\n{row}"


@pytest.mark.anyio
async def test_a_call_that_worked_is_recorded_as_ok(recorder: Recorder, audit_file: Path) -> None:
    """The ordinary row: the outcome class of D-07 and no reason next to it."""
    context = FakeContext(params=call_of(path="/notes"), recorder=recorder, who=identity())

    await probe(ctx=context, path="/notes")

    row = one_row(audit_file)
    assert (row["outcome"], row["reason"], row["kind"]) == ("ok", None, "call")
    assert (row["nc_user"], row["tool"]) == (NC_USER, TOOL)
    assert (row["client_id"], row["auth_id"], row["client_name"]) == (
        CLIENT_ID,
        AUTH_ID,
        CLIENT_NAME,
    )
    assert row["duration_ms"] >= 0


@pytest.mark.anyio
async def test_a_refusal_is_recorded_with_its_identifier_and_never_with_its_sentence(
    recorder: Recorder, audit_file: Path
) -> None:
    """D-07 and T-18-01 in one row: the fixed identifier stays, the two sentences do not."""
    context = FakeContext(params=call_of(path="/notes"), recorder=recorder, who=identity())
    refused = ToolError(REFUSAL_MESSAGE, REFUSAL_HINT, reason=REASON_PERMISSION_DENIED)

    with pytest.raises(ValueError, match="No permission to write"):
        await refusing(ctx=context, error=refused)

    row = one_row(audit_file)
    assert (row["outcome"], row["reason"]) == ("rejected", REASON_PERMISSION_DENIED)
    printed = every_column(row)
    assert REFUSAL_MESSAGE not in printed, f"exc.message reached the entry:\n{printed}"
    assert REFUSAL_HINT not in printed, f"exc.hint reached the entry:\n{printed}"


@pytest.mark.anyio
async def test_a_refusal_without_an_identifier_stays_unspecified(
    recorder: Recorder, audit_file: Path
) -> None:
    """D-17: the roughly 223 untouched raise sites read as "not determined", not as a guess."""
    context = FakeContext(params=call_of(path="/notes"), recorder=recorder, who=identity())

    with pytest.raises(ValueError, match="Nothing to see"):
        await refusing(ctx=context, error=ToolError("Nothing to see.", "Try another path."))

    row = one_row(audit_file)
    assert (row["outcome"], row["reason"]) == ("rejected", REASON_UNSPECIFIED)


@pytest.mark.anyio
async def test_any_other_exception_is_recorded_as_failed_and_passes_through_unchanged(
    recorder: Recorder, audit_file: Path
) -> None:
    """The broad branch catches to remember the class and hands the very object on."""
    context = FakeContext(params=call_of(path="/notes"), recorder=recorder, who=identity())
    programming_error = RuntimeError("a bug of this server")

    with pytest.raises(RuntimeError) as raised:
        await refusing(ctx=context, error=programming_error)

    assert raised.value is programming_error
    row = one_row(audit_file)
    assert (row["outcome"], row["reason"]) == ("failed", None)


@pytest.mark.anyio
async def test_a_store_that_cannot_write_costs_the_call_nothing(
    audit_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """D-13 and T-18-17: fail-open, one line, and that line names the type and nothing else."""
    broken = ExplodingStore(audit_file)

    async def provider() -> AuditStore:
        return broken

    context = FakeContext(
        params=call_of(path="/notes"),
        recorder=Recorder(store_provider=provider),
        who=identity(),
    )

    with caplog.at_level(logging.ERROR, logger="mcp_connector.audit.record"):
        assert await probe(ctx=context, path="/notes") == "answered"

    assert len(caplog.records) == 1
    logged = caplog.text
    assert "OSError" in logged
    assert "no space left" not in logged, f"the message of the failure reached the log:\n{logged}"
    assert "audit.sqlite3" not in logged, f"a path reached the log:\n{logged}"


@pytest.mark.anyio
async def test_without_a_recorder_nothing_is_written_and_nothing_is_logged(
    audit_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """stdio and the standalone HTTP mode run through here on every call: silence is the rule."""
    context = FakeContext(params=call_of(path="/notes"), recorder=None, who=identity())

    with caplog.at_level(logging.DEBUG, logger="mcp_connector.audit.record"):
        assert await probe(ctx=context, path="/notes") == "answered"

    assert written(audit_file) == []
    assert caplog.records == []


@pytest.mark.anyio
async def test_a_hostile_client_name_is_cleaned_and_cut_before_it_is_written(
    recorder: Recorder, audit_file: Path
) -> None:
    """T-18-08: the name comes from a dynamic registration, so it is written by an attacker."""
    hostile = "Claude\n\x00 Assistant" + "x" * 200
    context = FakeContext(
        params=call_of(path="/notes"), recorder=recorder, who=identity(client_name=hostile)
    )

    await probe(ctx=context, path="/notes")

    stored = one_row(audit_file)["client_name"]
    assert len(stored) <= CLIENT_NAME_LIMIT
    assert "\n" not in stored
    assert "\x00" not in stored
    assert stored.startswith("Claude Assistant")


@pytest.mark.anyio
async def test_a_control_character_in_a_name_becomes_a_space_and_melts_no_two_words(
    recorder: Recorder, audit_file: Path
) -> None:
    """The wanted change of plan 19-01: the rule replaces where it used to drop.

    Dropping the line break turned ``"Claude\\nAssistant"`` into the single word
    ``"ClaudeAssistant"``, a name nobody registered, and one that could stand for a different
    client in the output of the admin command. A space cannot melt two parts into one, which is
    why ``audit/text.py`` replaces every unprintable character instead of filtering it out.
    """
    context = FakeContext(
        params=call_of(path="/notes"),
        recorder=recorder,
        who=identity(client_name="Claude\nAssistant"),
    )

    await probe(ctx=context, path="/notes")

    assert one_row(audit_file)["client_name"] == "Claude Assistant"

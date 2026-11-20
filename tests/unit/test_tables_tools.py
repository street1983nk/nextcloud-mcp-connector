"""Unit tests for the two Tables tools, all paths.

The two properties that make ``tables_browse`` worth being one tool instead of three are
pinned first: every level answers with the same envelope (``level``, ``count``, ``results``),
and a row read is never a whole table read, because the default limit lands in the **URL**
and the answer names its own truncation next to ``rowsCount`` and ``offset``.

Everything else is the honest-failure catalogue of D-15 and SRV-04. A missing or disabled
Tables app stops both tools before the first Tables request, an unknown level names the three
that exist, and ``tables_create_row`` refuses four different ways before a single byte is
written: no write permission, an ambiguous title, an unknown title and a missing mandatory
column. Two of these cases a happy path never sees, and both have a test of their own: the
owner of a table whose share object reports ``read`` alone (K5), and a cursor handle that was
handed out for a different table.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from mcp_connector import paging
from mcp_connector.errors import AppMissingError, ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import marks
from mcp_connector.tools import tables as tables_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"

#: One of the two sequences this server writes into a text itself. A table that may write it
#: back would decide the framing of foreign text, which is the point of the filter (T-08-14).
MARKER = marks.EXCERPT_TRUNCATION

# The same frozen literals as in the client test: the tool layer must not be able to move a
# route by accident either.
V2_BASE = f"{BASE}/ocs/v2.php/apps/tables/api/2"
V1_BASE = f"{BASE}/index.php/apps/tables/api/1"
TABLES_URL = f"{V2_BASE}/tables"
TABLE_URL = f"{V2_BASE}/tables/7"
COLUMNS_URL = f"{V2_BASE}/columns/table/7"
CREATE_ROW_URL = f"{V2_BASE}/tables/7/rows"
ROWS_URL = f"{V1_BASE}/tables/7/rows/simple"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

TABLES_INSTALLED = {"enabled": True, "version": "2.2.2", "apiVersions": ["1.0", "2.0"]}
TABLES_DISABLED = {**TABLES_INSTALLED, "enabled": False}

#: The own table of the fixture: the share object reports ``read`` alone, and the owner may
#: write anyway (K5).
OWN_TABLE = {
    "id": 7,
    "title": "Übergaben Straßenbau",
    "rowsCount": 342,
    "columnsCount": 5,
    "isShared": False,
    "onSharePermissions": {
        "read": True,
        "create": False,
        "update": False,
        "delete": False,
        "manage": False,
    },
}

#: A table shared with this account without a create permission.
SHARED_TABLE = {
    **OWN_TABLE,
    "id": 7,
    "title": "Maße Prüfstücke",
    "isShared": True,
    "onSharePermissions": {"read": True, "create": False, "manage": False},
}

CREATED_ROW = {
    "id": 4711,
    "tableId": 7,
    "createdBy": "alice",
    "createdAt": "2026-08-21 10:14:02",
    "data": [{"columnId": 11, "value": "Baulos 4 übergeben"}],
    "dataByAlias": [],
}


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def envelope(data: Any, statuscode: int = 200, message: str = "OK") -> dict[str, Any]:
    """An OCS v2 envelope. The generation 1 row answer is bare and needs none."""
    return {
        "ocs": {
            "meta": {"status": "ok", "statuscode": statuscode, "message": message},
            "data": data,
        }
    }


def capabilities_payload(*, tables: dict | None = TABLES_INSTALLED) -> dict[str, Any]:
    section: dict[str, Any] = {"core": {}}
    if tables is not None:
        section["tables"] = tables
    return envelope({"capabilities": section})


def columns_without_the_collision() -> list[dict[str, Any]]:
    """The fixture columns minus the second "status" column.

    The fixture carries two columns whose titles normalise to the same value on purpose, so
    the ambiguity case has real data. Every other test needs a table whose titles resolve.
    """
    return [column for column in fixture("tables_columns.json") if column["id"] != 13]


def rows_payload(rows: int = 3) -> list[list[Any]]:
    """The title row plus ``rows`` value rows, exactly as generation 1 answers."""
    return fixture("tables_rows_simple.json")[: rows + 1]


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    capabilities.clear_cache()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def mock_capabilities(mock: respx.MockRouter, *, tables: dict | None = TABLES_INSTALLED) -> None:
    mock.get(CAPABILITIES_URL).mock(
        return_value=httpx.Response(200, json=capabilities_payload(tables=tables))
    )


def tables_routes(mock: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    """Catch-all routes for both generations, to assert that nothing was requested."""
    return mock.route(url__startswith=V2_BASE), mock.route(url__startswith=V1_BASE)


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["browse_tables", "browse_rows", "create_row"])
async def test_a_missing_tables_app_stops_both_tools_before_the_first_request(
    clients: NcClients, tool: str
) -> None:
    """SRV-04 and D-15: one sentence with an alternative, and zero Tables requests."""
    calls = {
        "browse_tables": lambda: tables_tools.browse(clients),
        "browse_rows": lambda: tables_tools.browse(clients, level="rows", table_id="7"),
        "create_row": lambda: tables_tools.create_row(clients, "7", '{"Aufgabe": "x"}'),
    }
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, tables=None)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(AppMissingError) as excinfo:
            await calls[tool]()

    assert v2_calls.call_count == 0, "no request may go to an app that is not installed"
    assert v1_calls.call_count == 0
    assert excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["browse_tables", "create_row"])
async def test_an_installed_but_disabled_app_behaves_like_a_missing_one(
    clients: NcClients, tool: str
) -> None:
    """An app that is switched off answers no request, so its section alone proves nothing."""
    calls = {
        "browse_tables": lambda: tables_tools.browse(clients),
        "create_row": lambda: tables_tools.create_row(clients, "7", '{"Aufgabe": "x"}'),
    }
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock, tables=TABLES_DISABLED)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(AppMissingError):
            await calls[tool]()

    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0


@pytest.mark.anyio
async def test_an_unknown_level_is_refused_and_names_all_three(clients: NcClients) -> None:
    """The schema rejects it first; the function stays honest when called directly."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.browse(clients, level="views")

    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0
    for level in ("tables", "columns", "rows"):
        assert level in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize("level", ["columns", "rows"])
async def test_a_level_below_the_table_needs_a_table_id(clients: NcClients, level: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.browse(clients, level=level)

    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0
    assert "table_id" in excinfo.value.message
    assert "level=tables" in excinfo.value.hint


@pytest.mark.anyio
async def test_browse_tables_projects_the_fields_a_model_reads(clients: NcClients) -> None:
    """Muster 6: views, column orders and editor names are payload nobody reads."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        route = mock.get(TABLES_URL).mock(
            return_value=httpx.Response(200, json=envelope(fixture("tables_tables.json")))
        )
        result = await tables_tools.browse(clients)

    assert route.call_count == 1
    assert result["level"] == "tables"
    assert result["count"] == 2
    first = result["results"][0]
    assert first == {
        "id": 7,
        "title": "Übergaben Straßenbau",
        "rowsCount": 342,
        "columnsCount": 4,
        "isShared": False,
        "can_create": True,
    }
    assert result["results"][1]["can_create"] is False, "shared without create"
    for dropped in ("views", "columnOrder", "sort", "ownerDisplayName", "createdBy", "lastEditBy"):
        assert dropped not in first


@pytest.mark.anyio
async def test_a_table_that_was_put_aside_does_not_appear(clients: NcClients) -> None:
    archived = [{**table, "archived": True} for table in fixture("tables_tables.json")]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLES_URL).mock(return_value=httpx.Response(200, json=envelope(archived)))
        result = await tables_tools.browse(clients)

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.anyio
async def test_browse_columns_keeps_the_limits_a_value_has_to_respect(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(fixture("tables_columns.json")))
        )
        result = await tables_tools.browse(clients, level="columns", table_id="7")

    mandatory = result["results"][0]
    assert mandatory == {
        "id": 11,
        "title": "Aufgabe",
        "type": "text",
        "mandatory": True,
        "subtype": "line",
        "textMaxLength": 255,
    }
    selection = result["results"][1]
    assert [option["label"] for option in selection["selectionOptions"]] == [
        "offen",
        "in Prüfung",
        "erledigt",
    ]
    assert "technicalName" not in mandatory
    assert "orderWeight" not in mandatory


@pytest.mark.anyio
async def test_rows_without_a_limit_read_twenty_five_and_not_the_table(
    clients: NcClients,
) -> None:
    """TABLES-01: the property only the URL shows. Without a limit this reads everything."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        rows = mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        await tables_tools.browse(clients, level="rows", table_id="7")

    assert tables_tools.DEFAULT_LIMIT == 25
    assert rows.calls.last.request.url.params["limit"] == "25"
    assert rows.calls.last.request.url.params["offset"] == "0"


@pytest.mark.anyio
@pytest.mark.parametrize(("limit", "expected"), [(5000, "200"), (0, "1")])
async def test_a_limit_outside_the_range_is_capped_instead_of_refused(
    clients: NcClients, limit: int, expected: str
) -> None:
    """The model asked a legitimate question with an unhelpful number."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        rows = mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        await tables_tools.browse(clients, level="rows", table_id="7", limit=limit)

    assert rows.calls.last.request.url.params["limit"] == expected


@pytest.mark.anyio
async def test_the_title_row_becomes_the_keys_and_is_not_a_row(clients: NcClients) -> None:
    """K8: ``limit=25`` answers with 26 lists, and the first one is not a row."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        result = await tables_tools.browse(clients, level="rows", table_id="7")

    assert result["count"] == 3, "three value rows, the title row is not one of them"
    assert result["results"][0]["Aufgabe"] == "Baulos 3 übergeben"
    assert result["results"][1]["status "] == "", "a missing value stays an empty string"
    assert result["table"] == "Übergaben Straßenbau"


@pytest.mark.anyio
async def test_more_rows_than_the_window_are_named_with_a_next_handle(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        result = await tables_tools.browse(clients, level="rows", table_id="7")

    assert result["rowsCount"] == 342
    assert result["offset"] == 0
    assert result["truncated"] is True
    assert paging.decode_cursor(result["next"]) == {"o": 3, "t": "7"}


@pytest.mark.anyio
@pytest.mark.parametrize("level", ["tables", "columns"])
async def test_a_cursor_on_a_level_without_a_next_page_is_refused_before_any_request(
    clients: NcClients, level: str
) -> None:
    """IN-04: silently handing back the first page again is paging in a circle.

    Only ``level=rows`` ever puts a ``next`` into an answer, so a handle on either of the
    other two levels is a handle of the row level or one somebody invented. Both are refused
    with a sentence and a next step, and the refusal stands before the capabilities request,
    so it costs no request at all: the catch-all route of the capabilities is asserted empty
    together with the two Tables generations.
    """
    handle = paging.encode_cursor({"o": 25, "t": "7"})
    with respx.mock(assert_all_called=False) as mock:
        caps = mock.get(CAPABILITIES_URL)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.browse(clients, level=level, table_id="7", cursor=handle)

    assert caps.call_count == 0, "the refusal is cheaper than the capabilities request"
    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0
    assert f"level={level!r}" in excinfo.value.message
    assert "no next page" in excinfo.value.message
    assert "level=rows" in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize("blank", ["", "   ", None])
async def test_no_cursor_on_the_table_level_is_not_a_refusal(
    clients: NcClients, blank: str | None
) -> None:
    """Edge: the registration layer sends an empty string, and empty is "no handle"."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLES_URL).mock(return_value=httpx.Response(200, json=envelope([OWN_TABLE])))

        result = await tables_tools.browse(clients, level="tables", cursor=blank)

    assert result["level"] == "tables"
    assert result["count"] == 1


@pytest.mark.anyio
async def test_a_cursor_of_another_table_is_refused_instead_of_applied(
    clients: NcClients,
) -> None:
    """T-08-17: the wrong page is an answer nobody can notice is wrong."""
    foreign = paging.encode_cursor({"o": 25, "t": "9"})
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        rows = mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.browse(clients, level="rows", table_id="7", cursor=foreign)

    assert rows.call_count == 0, "a handle of another table must not read a page"
    assert "table" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_table_with_no_rows_is_an_empty_answer_and_not_an_error(
    clients: NcClients,
) -> None:
    """no_data: only the title row came back, and that is a legitimate answer."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(
            return_value=httpx.Response(200, json=envelope({**OWN_TABLE, "rowsCount": 0}))
        )
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload(rows=0)))

        result = await tables_tools.browse(clients, level="rows", table_id="7")

    assert result["count"] == 0
    assert result["results"] == []
    assert result["rowsCount"] == 0
    assert "truncated" not in result
    assert "next" not in result


@pytest.mark.anyio
async def test_a_marker_is_removed_from_a_cell_that_is_not_a_plain_string(
    clients: NcClients,
) -> None:
    """WR-03: a multi selection cell is a list, and a list went through unfiltered.

    The type check around the filter covered exactly the shape the fixture happens to have.
    A cell that answers with a list of objects is the same foreign text one level down, so
    the marker has to be gone at every leaf and the numbers have to stay numbers.
    """
    payload = [
        ["Aufgabe", "Beteiligte", "Größe in m²"],
        [f"Baulos 3 {MARKER}", ["Alice", {"label": f"Bob {MARKER}"}], 12.5],
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=payload))

        result = await tables_tools.browse(clients, level="rows", table_id="7")

    row = result["results"][0]
    assert MARKER not in json.dumps(row, ensure_ascii=False)
    assert row["Aufgabe"] == "Baulos 3 "
    assert row["Beteiligte"] == ["Alice", {"label": "Bob "}]
    assert row["Größe in m²"] == 12.5, "a number stays a number, the filter is not a cast"


@pytest.mark.anyio
async def test_a_marker_in_a_selection_option_label_is_removed_as_well(
    clients: NcClients,
) -> None:
    """The other half of WR-03: the option labels of a column are foreign text too.

    Whoever manages the table writes them, and ``selectionOptions`` was handed through as it
    came. It is the one field of ``_COLUMN_LIMITS`` that carries text rather than a number.
    """
    columns = [
        {
            "id": 12,
            "title": f"Status {MARKER}",
            "type": "selection",
            "mandatory": False,
            "selectionOptions": [
                {"id": 0, "label": f"offen {MARKER}"},
                {"id": 1, "label": "fertig"},
            ],
        }
    ]
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(COLUMNS_URL).mock(return_value=httpx.Response(200, json=envelope(columns)))

        result = await tables_tools.browse(clients, level="columns", table_id="7")

    entry = result["results"][0]
    assert MARKER not in json.dumps(entry, ensure_ascii=False)
    assert entry["title"] == "Status "
    assert entry["selectionOptions"] == [{"id": 0, "label": "offen "}, {"id": 1, "label": "fertig"}]


@pytest.mark.anyio
async def test_a_page_that_carried_nothing_hands_out_no_handle_of_its_own_offset(
    clients: NcClients,
) -> None:
    """WR-02: the drifting row counter must not produce a cursor that points at itself.

    ``rowsCount`` still claims 342 rows while the page at offset 25 answers with nothing,
    which happens because Tables does not always subtract a deleted row. The old condition
    handed back ``o = 25``, the cursor that was just passed in, and a client that follows
    ``next`` while it is set never leaves that page.
    """
    handle = paging.encode_cursor({"o": 25, "t": "7"})
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload(rows=0)))

        result = await tables_tools.browse(clients, level="rows", table_id="7", cursor=handle)

    assert result["count"] == 0
    assert result["offset"] == 25
    assert result["rowsCount"] == 342, "the number the app reported is passed through as it is"
    assert "next" not in result, "a handle equal to the current cursor is an endless loop"
    assert "truncated" not in result


@pytest.mark.anyio
@pytest.mark.parametrize("broken", [None, "342", True, -1])
async def test_a_full_window_is_named_as_truncated_even_without_a_row_count(
    clients: NcClients, broken: Any
) -> None:
    """WR-01: the count is the usual signal, a full window is the one that is always there.

    Without it a table of 342 rows answers 3 rows, claims ``rowsCount: 3`` and reports no
    truncation, which is the silent cut this module promises not to do. A count that is a
    string, a bool or negative is no count either, so all four shapes take the same path.
    """
    info: dict[str, Any] = {key: value for key, value in OWN_TABLE.items() if key != "rowsCount"}
    if broken is not None:
        info["rowsCount"] = broken

    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(info)))
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        result = await tables_tools.browse(clients, level="rows", table_id="7", limit=3)

    assert result["count"] == 3
    assert "rowsCount" not in result, "a count nobody reported must not be invented"
    assert result["truncated"] is True
    assert paging.decode_cursor(result["next"]) == {"o": 3, "t": "7"}


@pytest.mark.anyio
async def test_a_window_that_was_not_filled_is_the_end_of_the_table(
    clients: NcClients,
) -> None:
    """The other half of WR-01: without a count, a short page is the last page."""
    info = {key: value for key, value in OWN_TABLE.items() if key != "rowsCount"}
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(info)))
        mock.get(ROWS_URL).mock(return_value=httpx.Response(200, json=rows_payload()))

        result = await tables_tools.browse(clients, level="rows", table_id="7", limit=25)

    assert result["count"] == 3
    assert "rowsCount" not in result
    assert "truncated" not in result
    assert "next" not in result


@pytest.mark.anyio
async def test_values_that_are_not_json_are_refused_with_an_example(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", "Aufgabe: Rückruf")

    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0
    assert "JSON" in excinfo.value.message
    assert "{" in excinfo.value.hint, "an example object is what makes the hint actionable"


@pytest.mark.anyio
async def test_values_that_are_a_json_list_get_their_own_sentence(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '["Aufgabe", "Rückruf"]')

    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0
    assert "list" in excinfo.value.message


@pytest.mark.anyio
async def test_an_empty_values_object_is_refused_before_any_request(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        v2_calls, v1_calls = tables_routes(mock)

        with pytest.raises(ToolError):
            await tables_tools.create_row(clients, "7", "{}")

    assert v2_calls.call_count == 0
    assert v1_calls.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("broken_id", [None, "11", True])
async def test_a_column_without_a_numeric_id_is_refused_instead_of_written(
    clients: NcClients, broken_id: Any
) -> None:
    """WR-04: ``str(None)`` is ``"None"``, and ``(int)"None"`` is the column 0 in the app.

    A deformed column object would therefore not fail, it would write the value into the
    first column of the table, and nothing in the answer would say so. A string id and a
    bool take the same path: the app casts the key, so only a real int is safe.
    """
    columns = [
        {key: value for key, value in column.items() if key != "id"}
        if column["id"] == 11
        else column
        for column in columns_without_the_collision()
    ]
    if broken_id is not None:
        columns[0]["id"] = broken_id

    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(return_value=httpx.Response(200, json=envelope(columns)))
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '{"Aufgabe": "Baulos 4"}')

    assert len(post.calls) == 0, "a value without a column id must never become a write"
    assert "Aufgabe" in excinfo.value.message
    assert "numeric id" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_an_unknown_column_title_lists_the_titles_that_exist(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(
                clients, "7", '{"Aufgabe": "Baulos 4", "Zuständig": "Bob"}'
            )

    assert len(post.calls) == 0, "an unknown title must not become a write"
    assert "Zuständig" in excinfo.value.message
    assert "Aufgabe" in excinfo.value.hint
    assert "Fällig am" in excinfo.value.hint


@pytest.mark.anyio
async def test_an_ambiguous_column_title_names_both_column_ids(clients: NcClients) -> None:
    """Tables has no unique constraint on titles, so this is a real case (open question 4)."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(fixture("tables_columns.json")))
        )
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(
                clients, "7", '{"Aufgabe": "Baulos 4", "Status": "offen"}'
            )

    assert len(post.calls) == 0, "writing into either of the two columns would be a guess"
    assert "12" in excinfo.value.message
    assert "13" in excinfo.value.message
    assert "Status" in excinfo.value.message


@pytest.mark.anyio
async def test_a_missing_mandatory_column_is_refused_with_its_title(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '{"Fällig am": "2026-09-01"}')

    assert len(post.calls) == 0, "the app would refuse this row anyway"
    assert "Aufgabe" in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_title_is_matched_trimmed_and_case_folded(clients: NcClients) -> None:
    """A trailing space and a lower case A still find "Aufgabe"; refusing would cost a trip."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        post = mock.post(CREATE_ROW_URL).mock(
            return_value=httpx.Response(200, json=envelope(CREATED_ROW))
        )

        result = await tables_tools.create_row(clients, "7", '{"aufgabe ": "Baulos 4"}')

    body = json.loads(post.calls.last.request.content)
    assert body["data"] == {"11": "Baulos 4"}
    assert result["values_written"] == {"Aufgabe": "Baulos 4"}


@pytest.mark.anyio
async def test_two_values_keys_for_the_same_column_are_refused_instead_of_last_wins(
    clients: NcClients,
) -> None:
    """WR-04: "Aufgabe" and "aufgabe " normalise to one column, and a write may not guess.

    A silent last wins would send only the later value, report only the later value under
    ``values_written`` and never show the caller an error: data loss with a healthy looking
    answer, on the one write path of this family.
    """
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(
                clients, "7", '{"Aufgabe": "Baulos 4", "aufgabe ": "Baulos 5"}'
            )

    assert len(post.calls) == 0, "neither of the two values may be written on a guess"
    assert "'Aufgabe'" in excinfo.value.message
    assert "'aufgabe '" in excinfo.value.message
    assert "one key per column" in excinfo.value.hint


@pytest.mark.anyio
async def test_two_unknown_keys_that_collide_are_refused_as_a_collision_first(
    clients: NcClients,
) -> None:
    """The collision refusal does not depend on the titles existing in the table at all."""
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '{"Zuständig": "Bob", "ZUSTÄNDIG ": "Eva"}')

    assert len(post.calls) == 0
    assert "twice" in excinfo.value.message


@pytest.mark.anyio
async def test_the_owner_may_write_although_the_share_object_reports_read_alone(
    clients: NcClients,
) -> None:
    """K5 and T-08-13: a literal read of ``create`` would refuse every owner."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        post = mock.post(CREATE_ROW_URL).mock(
            return_value=httpx.Response(200, json=envelope(CREATED_ROW))
        )

        result = await tables_tools.create_row(
            clients, "7", '{"Aufgabe": "Baulos 4 übergeben", "Größe in m²": 12.5}'
        )

    assert post.call_count == 1
    body = json.loads(post.calls.last.request.content)
    assert body["data"] == {"11": "Baulos 4 übergeben", "15": 12.5}
    assert list(body["data"]) == ["11", "15"], "keys are column ids, never titles"
    assert result["id"] == 4711
    assert result["table_id"] == "7"
    assert result["url"] == f"{BASE}/index.php/apps/tables/#/table/7"
    assert result["values_written"] == {
        "Aufgabe": "Baulos 4 übergeben",
        "Größe in m²": 12.5,
    }


@pytest.mark.anyio
async def test_a_shared_table_without_create_is_refused_before_the_post(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(SHARED_TABLE)))
        columns = mock.get(COLUMNS_URL)
        post = mock.post(CREATE_ROW_URL)

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '{"Aufgabe": "Baulos 4"}')

    assert len(post.calls) == 0, "a request that can only end in 403 must never leave"
    assert len(columns.calls) == 0, "the permission is decided before the columns are read"
    assert "Maße Prüfstücke" in excinfo.value.message
    assert "can_create" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_created_row_without_an_id_is_reported_instead_of_faked(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        mock.post(CREATE_ROW_URL).mock(
            return_value=httpx.Response(200, json=envelope({"tableId": 7}))
        )

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '{"Aufgabe": "Baulos 4"}')

    assert "id" in excinfo.value.message
    assert "Tables app" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_four_hundred_of_the_app_is_passed_through_with_its_own_message(
    clients: NcClients,
) -> None:
    """No hand rolled type validation: the app knows its column types, we do not."""
    with respx.mock(assert_all_called=True) as mock:
        mock_capabilities(mock)
        mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(OWN_TABLE)))
        mock.get(COLUMNS_URL).mock(
            return_value=httpx.Response(200, json=envelope(columns_without_the_collision()))
        )
        mock.post(CREATE_ROW_URL).mock(
            return_value=httpx.Response(
                400,
                json=envelope(None, statuscode=400, message="Value is not a valid number"),
            )
        )

        with pytest.raises(ToolError) as excinfo:
            await tables_tools.create_row(clients, "7", '{"Aufgabe": "Baulos 4"}')

    # Wording fix of plan 35-11: the Nextcloud text is quoted so the sentence can end.
    assert 'Nextcloud says: "Value is not a valid number".' in excinfo.value.message

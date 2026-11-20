"""Registration of the tables tools. The logic lives in :mod:`mcp_connector.tools.tables`.

``level`` is a ``Literal`` and therefore an enum in the input schema, not a free string:
the model sees the three valid values instead of guessing "row" or "sheets" and paying a
round trip for the correction (D-06, D-14).

Both tools are listed unconditionally, even on an instance without the Tables app. A
credential dependent ``tools/list`` is not cacheable, breaks the token budget gate and
surprises clients that persist tool lists; the honest answer to a missing app is the
sentence the tool returns (SRV-04).
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import tables as tables_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def tables_browse(
    level: Annotated[
        Literal["tables", "columns", "rows"],
        Field(description="What to list; columns and rows need a table_id"),
    ] = "tables",
    table_id: Annotated[str, Field(description="Table id from level=tables, e.g. 7")] = "",
    limit: Annotated[
        int, Field(ge=1, le=tables_tools.MAX_LIMIT, description="Maximum entries")
    ] = tables_tools.DEFAULT_LIMIT,
    cursor: Annotated[
        str, Field(description="Next page handle from a truncated answer; only level=rows")
    ] = "",
    ctx: Context | None = None,
) -> str:
    """List the user's Tables, the columns of one, or its rows."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await tables_tools.browse(
            clients,
            level=level,
            table_id=table_id or None,
            limit=limit,
            cursor=cursor or None,
        )
    )


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def tables_create_row(
    table_id: Annotated[str, Field(description="Table id from tables_browse")],
    values: Annotated[
        str,
        Field(
            description=(
                'One JSON object of column titles and values, e.g. {"Task":"Call back",'
                '"Amount":12.5}; text columns take strings, number columns numbers'
            )
        ),
    ],
    ctx: Context | None = None,
) -> str:
    """Add one new row to an existing table.

    A timeout does not mean nothing was written. Read back with tables_browse(level=rows)
    instead of calling this twice."""
    clients = deps.resolve_clients(ctx)
    return compact(await tables_tools.create_row(clients, table_id=table_id, values=values))

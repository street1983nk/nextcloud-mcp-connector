"""Registration of the deck tools. The logic lives in :mod:`mcp_connector.tools.deck`.

``level`` is a ``Literal`` and therefore an enum in the input schema, not a free string:
the model sees the three valid values instead of guessing "card" or "lists" and paying a
round trip for the correction (D-06, D-14).

Both tools are listed unconditionally, even on an instance without the Deck app. A
credential dependent ``tools/list`` is not cacheable, breaks the token budget gate and
surprises clients that persist tool lists; the honest answer to a missing app is the
sentence the tool returns (SRV-04).
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import deck as deck_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def deck_browse(
    level: Annotated[
        Literal["boards", "stacks", "cards"],
        Field(description="What to list; stacks and cards need a board_id"),
    ] = "boards",
    board_id: Annotated[str, Field(description="Board id from level=boards, e.g. 2")] = "",
    stack_id: Annotated[str, Field(description="Optional: only cards of this stack")] = "",
    limit: Annotated[
        int, Field(ge=1, le=deck_tools.MAX_LIMIT, description="Maximum number of entries")
    ] = deck_tools.DEFAULT_LIMIT,
    ctx: Context | None = None,
) -> str:
    """List Deck boards, the stacks of a board, or its cards."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await deck_tools.browse(
            clients,
            level=level,
            board_id=board_id or None,
            stack_id=stack_id or None,
            limit=limit,
        )
    )


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def deck_create_card(
    board_id: Annotated[str, Field(description="Board id from deck_browse")],
    stack_id: Annotated[str, Field(description="Stack id from deck_browse level=stacks")],
    title: Annotated[str, Field(description="Card title, at most 255 characters")],
    description: Annotated[str, Field(description="Optional card text, Markdown")] = "",
    duedate: Annotated[
        str, Field(description="Optional due date, e.g. 2026-09-01T10:00:00+00:00")
    ] = "",
    ctx: Context | None = None,
) -> str:
    """Create a new card in an existing stack."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await deck_tools.create_card(
            clients,
            board_id=board_id,
            stack_id=stack_id,
            title=title,
            description=description or None,
            duedate=duedate or None,
        )
    )

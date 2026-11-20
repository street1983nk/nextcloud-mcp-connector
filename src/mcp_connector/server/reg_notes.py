"""Registration of the notes tools. The logic lives in :mod:`mcp_connector.tools.notes`.

All three are listed unconditionally. ``tools/list`` stays static even on an instance
without the Notes app, because a credential dependent listing is not cacheable, breaks the
token budget measurement and surprises clients that persist tool lists. The honest answer
to a missing app is the sentence the tool returns, not a hidden tool (SRV-04).
"""

from typing import Annotated

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import notes as notes_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def notes_search(
    query: Annotated[str, Field(description="Words to look for in note titles and contents")],
    limit: Annotated[int, Field(ge=1, le=100, description="Maximum number of hits")] = 25,
    ctx: Context | None = None,
) -> str:
    """Search the user's Nextcloud notes by title and content."""
    clients = deps.resolve_clients(ctx)
    return compact(await notes_tools.search(clients, query=query, limit=limit))


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def notes_read(
    note_id: Annotated[str, Field(description="Note id from notes_search, e.g. note:12")],
    ctx: Context | None = None,
) -> str:
    """Read one note including its full content."""
    clients = deps.resolve_clients(ctx)
    return compact(await notes_tools.read(clients, note_id=note_id))


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def notes_create(
    title: Annotated[str, Field(description="Title of the new note")],
    content: Annotated[str, Field(description="Note text, Markdown is supported")],
    category: Annotated[str | None, Field(description="Optional category folder")] = None,
    ctx: Context | None = None,
) -> str:
    """Create a new note; the returned title is the one the server stored."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await notes_tools.create(clients, title=title, content=content, category=category)
    )

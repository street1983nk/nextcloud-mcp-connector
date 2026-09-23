"""Registration of the cloud wide search. The logic lives in :mod:`mcp_connector.tools.search`.

``providers`` is a comma separated string and not a list, on purpose: a list parameter
turns into an ``anyOf`` of array and null in the input schema, and every byte of that is
paid for in every ``tools/list`` of every session (schema diet, D-14).
"""

from typing import Annotated

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import search as search_tools
from . import READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def unified_search(
    query: Annotated[str, Field(description="Words to search for, e.g. budget 2026")],
    limit: Annotated[
        int, Field(ge=1, le=search_tools.MAX_LIMIT, description="Maximum hits per provider")
    ] = search_tools.DEFAULT_LIMIT,
    providers: Annotated[
        str, Field(description="Comma separated provider ids, e.g. files,notes; empty means all")
    ] = "",
    ctx: Context | None = None,
) -> str:
    """Search the whole Nextcloud across all installed search providers. The note of every answer says whether file contents were matched."""  # noqa: E501
    clients = deps.resolve_clients(ctx)
    return compact(
        await search_tools.unified_search(
            clients, query=query, limit=limit, providers=providers or None
        )
    )

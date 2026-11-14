"""Registration of the cloud wide search. The logic lives in :mod:`mcp_connector.tools.search`.

``providers`` is a comma separated string and not a list, on purpose: a list parameter
turns into an ``anyOf`` of array and null in the input schema, and every byte of that is
paid for in every ``tools/list`` of every session (schema diet, D-14).
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import config, deps
from ..tools import profile_fields as profile_fields_tools
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
        str, Field(description="Comma-separated provider ids, e.g. files,notes; empty means all")
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


if config.profile_fields_read_enabled():

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    @graceful
    async def profile_fields_browse(
        level: Annotated[Literal["definitions", "values", "search"], Field(description="Catalog, selected UID fields or exact search")] = "definitions",
        user_uid: Annotated[str, Field(description="Values: Nextcloud UID")] = "",
        field_keys: Annotated[str, Field(description="Values: comma-separated keys, max 12")] = "",
        field_key: Annotated[str, Field(description="Search: field key")] = "",
        value: Annotated[str, Field(description="Search: exact value")] = "",
        limit: Annotated[int, Field(ge=1, le=100, description="Search page size")] = 25,
        offset: Annotated[int, Field(ge=0, description="Search page offset")] = 0,
        ctx: Context | None = None,
    ) -> str:
        """Read selected Profile Fields with the current Nextcloud permissions."""
        return compact(await profile_fields_tools.browse(
            deps.resolve_clients(ctx), level=level, user_uid=user_uid,
            field_keys=field_keys, field_key=field_key, value=value,
            limit=limit, offset=offset,
        ))

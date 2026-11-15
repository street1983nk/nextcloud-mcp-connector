"""Profile Fields tools reuse Nextcloud's own account-specific OCS permissions."""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import profile_fields
from . import READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def profile_fields_browse(
    level: Annotated[
        Literal["definitions", "me", "values", "search"],
        Field(description="Definitions, own values, UID values, or exact field search"),
    ] = "me",
    user_uid: Annotated[str, Field(description="Admin: exact Nextcloud UID")] = "",
    field_keys: Annotated[str, Field(description="Admin UID values: up to 12 keys")] = "",
    field_key: Annotated[str, Field(description="Search: field key")] = "",
    value: Annotated[str, Field(description="Search: exact field value")] = "",
    limit: Annotated[int, Field(ge=1, le=100, description="Search page size")] = 25,
    offset: Annotated[int, Field(ge=0, description="Search page offset")] = 0,
    ctx: Context | None = None,
) -> str:
    """Read Profile Fields via native OCS using the connected Nextcloud account."""
    return compact(
        await profile_fields.browse(
            deps.resolve_clients(ctx),
            level=level,
            user_uid=user_uid,
            field_keys=field_keys,
            field_key=field_key,
            value=value,
            limit=limit,
            offset=offset,
        )
    )


"""Profile Fields tools reuse Nextcloud's own account-specific OCS permissions."""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import profile_fields
from . import CREATE_ONLY, MODIFY_EXISTING, READ_ONLY, compact, graceful, mcp


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


@mcp.tool(annotations=MODIFY_EXISTING, structured_output=False)
@graceful
async def profile_fields_set_value(
    field_id: Annotated[int, Field(ge=1, description="Existing field definition id")],
    value_json: Annotated[str, Field(description="New JSON value, e.g. true or string")],
    user_uid: Annotated[str, Field(description="Admin target UID; blank edits own field")] = "",
    visibility: Annotated[str, Field(description="Optional private, users or public")] = "",
    ctx: Context | None = None,
) -> str:
    """Create or update a field value within the caller's native Nextcloud permissions."""
    return compact(
        await profile_fields.set_value(
            deps.resolve_clients(ctx),
            field_id,
            value_json,
            user_uid=user_uid,
            visibility=visibility,
        )
    )


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def profile_fields_create_definition(
    definition_json: Annotated[str, Field(description="Admin: new field definition as JSON")],
    ctx: Context | None = None,
) -> str:
    """Create one definition as a Nextcloud instance administrator."""
    return compact(
        await profile_fields.save_definition(
            deps.resolve_clients(ctx),
            definition_json,
            definition_id=0,
        )
    )


@mcp.tool(annotations=MODIFY_EXISTING, structured_output=False)
@graceful
async def profile_fields_update_definition(
    definition_id: Annotated[int, Field(ge=1, description="Admin: existing definition id")],
    definition_json: Annotated[str, Field(description="Full definition JSON including policies")],
    ctx: Context | None = None,
) -> str:
    """Update a definition only when the connected Nextcloud admin is authorized."""
    return compact(
        await profile_fields.save_definition(
            deps.resolve_clients(ctx),
            definition_json,
            definition_id=definition_id,
        )
    )

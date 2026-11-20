"""Registration of the calendar tools. The logic lives in :mod:`mcp_connector.tools.calendar`.

The parameter descriptions carry one example each. That is the cheapest fix for the most
expensive CalDAV mistake: a model that guesses the time format sends a window sabre answers
with 400, and neither the model nor the user learns why (pitfall 4).
"""

from typing import Annotated

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import calendar as calendar_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def calendar_list_events(
    start: Annotated[
        str,
        Field(description="Window start, ISO 8601 with zone, e.g. 2026-09-01T00:00:00+02:00"),
    ],
    end: Annotated[str, Field(description="Window end, exclusive, same format as start")],
    calendar: Annotated[
        str | None, Field(description="One calendar by name or uri; default: all")
    ] = None,
    timezone: Annotated[
        str | None, Field(description="IANA zone for the output times, default UTC")
    ] = None,
    limit: Annotated[
        int, Field(ge=1, le=calendar_tools.MAX_LIMIT, description="Maximum number of events")
    ] = calendar_tools.DEFAULT_LIMIT,
    ctx: Context | None = None,
) -> str:
    """List calendar events in a time range (start and end are required, both with timezone)."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await calendar_tools.list_events(
            clients,
            start=start,
            end=end,
            calendar=calendar,
            timezone=timezone,
            limit=limit,
        )
    )


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def calendar_create_event(
    summary: Annotated[str, Field(description="Title of the new event")],
    start: Annotated[
        str,
        Field(description="Start, ISO 8601 with zone, e.g. 2026-09-15T14:00:00+02:00"),
    ],
    end: Annotated[str, Field(description="End, same format as start")],
    calendar: Annotated[
        str | None, Field(description="Target calendar by name or uri; default: personal")
    ] = None,
    location: Annotated[str | None, Field(description="Optional place")] = None,
    description: Annotated[str | None, Field(description="Optional longer text")] = None,
    all_day: Annotated[
        bool, Field(description="All day: start and end are plain dates, end is exclusive")
    ] = False,
    timezone: Annotated[
        str | None, Field(description="IANA zone to store the event in, e.g. Europe/Berlin")
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Create a new calendar event; returns the times the server confirmed."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await calendar_tools.create_event(
            clients,
            summary=summary,
            start=start,
            end=end,
            calendar=calendar,
            location=location,
            description=description,
            all_day=all_day,
            timezone=timezone,
        )
    )

"""Registration of the task tools. The logic lives in :mod:`mcp_connector.tools.tasks`.

The parameter on the wire is called ``list`` (E7), because that is the word a model reads in
a hit of ``tasks_search``. In Python it shadows the builtin, so the one place that names it
carries ``noqa: A002`` and hands it on as ``list_name=``, the same split as ``id`` and
``resource_id`` in ``fetch``. Examples sit only where a model would otherwise guess a format.
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import config, deps
from ..tools import tasks as tasks_tools
from . import CREATE_ONLY, MODIFY_EXISTING, READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def tasks_search(
    query: Annotated[
        str | None, Field(description="Words in title, description or tags; default: all")
    ] = None,
    status: Annotated[
        Literal["open", "completed", "all"], Field(description="Which tasks; default: open")
    ] = "open",
    due_by: Annotated[
        str | None,
        Field(description="Due on or before, YYYY-MM-DD or ISO 8601 with zone"),
    ] = None,
    list: Annotated[  # noqa: A002 - the wire name of E7, handed on as list_name
        str | None, Field(description="One list by name or key; default: all lists")
    ] = None,
    cursor: Annotated[
        str | None, Field(description="Cursor of the previous page, for the next 25")
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Search tasks (open by default) in own and shared task lists, 25 per page."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await tasks_tools.search_tasks(
            clients,
            query=query,
            status=status,
            due_by=due_by,
            list_name=list,
            cursor=cursor,
        )
    )


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def tasks_read(
    task_id: Annotated[str, Field(description="Task id from tasks_search")],
    ctx: Context | None = None,
) -> str:
    """Read one task with its description and its direct subtasks."""
    clients = deps.resolve_clients(ctx)
    return compact(await tasks_tools.read_task(clients, task_id=task_id))


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def tasks_create(
    summary: Annotated[str, Field(description="Title of the new task")],
    list: Annotated[  # noqa: A002 - the wire name of E7, handed on as list_name
        str | None,
        Field(description="List name or key from tasks_search; required for a list others can see"),
    ] = None,
    description: Annotated[str | None, Field(description="Optional longer text")] = None,
    due: Annotated[str | None, Field(description="YYYY-MM-DD, or ISO 8601 with zone")] = None,
    start: Annotated[str | None, Field(description="Same format as due")] = None,
    priority: Annotated[
        int | None, Field(ge=0, le=9, description="1 high to 9 low, 0 none")
    ] = None,
    tags: Annotated[list[str] | None, Field(description="Optional tags")] = None,
    timezone: Annotated[
        str | None, Field(description="IANA zone to store times in, e.g. Europe/Berlin")
    ] = None,
    parent: Annotated[
        str | None, Field(description="Task id from tasks_search; makes this a subtask")
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Create a task, create-only; never into a list others can see unless it is named."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await tasks_tools.create_task(
            clients,
            summary=summary,
            list_name=list,
            description=description,
            due=due,
            start=start,
            priority=priority,
            tags=tags,
            timezone=timezone,
            parent=parent,
        )
    )


if config.tasks_update_enabled():

    @mcp.tool(annotations=MODIFY_EXISTING, structured_output=False)
    @graceful
    async def tasks_complete(
        task_id: Annotated[str, Field(description="Task id from tasks_search")],
        etag: Annotated[str, Field(description="etag from tasks_read")],
        completed: Annotated[bool, Field(description="true: complete, false: reopen")],
        ctx: Context | None = None,
    ) -> str:
        """Complete or reopen a task; needs its etag from tasks_read. Completing also
        completes its subtasks first. Recurring tasks are refused."""
        clients = deps.resolve_clients(ctx)
        return compact(
            await tasks_tools.complete_task(
                clients, task_id=task_id, etag=etag, completed=completed
            )
        )

    @mcp.tool(annotations=MODIFY_EXISTING, structured_output=False)
    @graceful
    async def tasks_update(
        task_id: Annotated[str, Field(description="Task id from tasks_search")],
        etag: Annotated[str, Field(description="etag from tasks_read")],
        summary: Annotated[str | None, Field(description="New title")] = None,
        description: Annotated[str | None, Field(description="New longer text")] = None,
        due: Annotated[str | None, Field(description="New due")] = None,
        start: Annotated[str | None, Field(description="New start")] = None,
        priority: Annotated[
            int | None, Field(ge=0, le=9, description="1 high to 9 low, 0 none")
        ] = None,
        tags: Annotated[list[str] | None, Field(description="Replaces all tags")] = None,
        parent: Annotated[str | None, Field(description="Task id of the new parent")] = None,
        ctx: Context | None = None,
    ) -> str:
        """Change fields of a task; needs its etag from tasks_read. Omit or null keeps a
        field, an empty value clears it ("", [], priority 0); summary cannot be empty.
        Times with offset or Z, dates as YYYY-MM-DD."""
        clients = deps.resolve_clients(ctx)
        return compact(
            await tasks_tools.update_task(
                clients,
                task_id=task_id,
                etag=etag,
                summary=summary,
                description=description,
                due=due,
                start=start,
                priority=priority,
                tags=tags,
                parent=parent,
            )
        )

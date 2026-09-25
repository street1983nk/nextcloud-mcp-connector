"""Registration of the file tools. The logic lives in :mod:`mcp_connector.tools.files`.

No tool takes a user name: the identity comes from the auth channel through
``deps.resolve_clients`` only (threat T-01-12, confused deputy).
"""

import base64
from typing import Annotated
from urllib.parse import quote

from mcp.server.mcpserver import Context
from mcp.types import BlobResourceContents, EmbeddedResource, TextContent
from pydantic import Field

from .. import deps
from ..errors import ToolError
from ..tools import files as files_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_search(
    query: Annotated[str, Field(description="Part of a file or folder name, e.g. budget")],
    folder: Annotated[str, Field(description="Folder to search in, e.g. /Docs")] = "/",
    limit: Annotated[
        int, Field(ge=1, le=files_tools.MAX_SEARCH_LIMIT, description="Maximum number of hits")
    ] = files_tools.DEFAULT_SEARCH_LIMIT,
    cursor: Annotated[str, Field(description="'next' value of the previous answer")] = "",
    ctx: Context | None = None,
) -> str:
    """Search files and folders by name (matches names, not file contents)."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await files_tools.search(
            clients, query=query, folder=folder, limit=limit, cursor=cursor or None
        )
    )


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_list(
    path: Annotated[str, Field(description="Folder path, e.g. /Docs")] = "/",
    limit: Annotated[
        int, Field(ge=1, le=files_tools.MAX_LIST_LIMIT, description="Maximum number of entries")
    ] = files_tools.DEFAULT_LIST_LIMIT,
    cursor: Annotated[str, Field(description="'next' value of the previous answer")] = "",
    ctx: Context | None = None,
) -> str:
    """List the direct children of a folder."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await files_tools.list_dir(clients, path=path, limit=limit, cursor=cursor or None)
    )


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_read(
    path: Annotated[str, Field(description="Path inside the user's files, e.g. /Docs/notes.md")],
    offset: Annotated[int, Field(ge=0, description="Byte offset for a continued read")] = 0,
    ctx: Context | None = None,
) -> str:
    """Read a text file from Nextcloud; large files come back truncated with a next offset."""
    clients = deps.resolve_clients(ctx)
    return compact(await files_tools.read(clients, path=path, offset=offset))


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_download(
    path: Annotated[str, Field(description="Path of the file to download, e.g. /Docs/scan.pdf")],
    offset: Annotated[
        int, Field(ge=0, description="Byte offset; continue with next_offset from the prior chunk")
    ] = 0,
    chunk_bytes: Annotated[
        int,
        Field(
            ge=1,
            le=files_tools.HARD_DOWNLOAD_BYTES,
            description="Bytes in this chunk; default and maximum 8 MiB",
        ),
    ] = files_tools.DEFAULT_DOWNLOAD_BYTES,
    ctx: Context | None = None,
) -> list[TextContent | EmbeddedResource]:
    """Download any-size file in chunks; repeat with next_offset while truncated is true."""
    clients = deps.resolve_clients(ctx)
    result = await files_tools.download(clients, path=path, offset=offset, max_bytes=chunk_bytes)
    metadata = {key: value for key, value in result.items() if key != "content"}
    return [
        TextContent(text=compact(metadata)),
        EmbeddedResource(
            resource=BlobResourceContents(
                uri=(
                    f"nextcloud://files{quote(result['path'], safe='/')}"
                    f"?offset={result['offset']}&bytes={result['bytes']}"
                ),
                mime_type=result["content_type"],
                blob=base64.b64encode(result["content"]).decode("ascii"),
            )
        ),
    ]


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def files_upload(
    path: Annotated[str, Field(description="New file path; must not exist")],
    content: Annotated[
        str | None,
        Field(description="UTF-8 text; omit for binary"),
    ] = None,
    content_base64: Annotated[
        str | None,
        Field(description="Base64 chunk for binary upload"),
    ] = None,
    total_bytes: Annotated[
        int | None,
        Field(ge=0, description="Total binary size in bytes"),
    ] = None,
    chunk_index: Annotated[
        int,
        Field(ge=1, le=files_tools.MAX_UPLOAD_CHUNKS, description="Chunk number, starting at 1"),
    ] = 1,
    upload_id: Annotated[
        str,
        Field(description="Continuation id"),
    ] = "",
    final: Annotated[
        bool,
        Field(description="Assemble after this chunk"),
    ] = False,
    content_type: Annotated[
        str,
        Field(description="Binary MIME type"),
    ] = "application/octet-stream",
    ctx: Context | None = None,
) -> str:
    """Create text or upload large binary files as base64 chunks; never overwrites."""
    clients = deps.resolve_clients(ctx)
    if content_base64 is not None:
        if content is not None:
            raise ToolError(
                message="Send either content or content_base64, not both.",
                hint="Use content_base64 for PDF and other binary files.",
            )
        if total_bytes is None:
            raise ToolError(
                message="total_bytes is required with content_base64.",
                hint="Set it to the complete file size in bytes.",
            )
        return compact(
            await files_tools.upload_binary(
                clients,
                path=path,
                content_base64=content_base64,
                total_bytes=total_bytes,
                chunk_index=chunk_index,
                upload_id=upload_id,
                final=final,
                content_type=content_type,
            )
        )
    if any((total_bytes is not None, upload_id, final, chunk_index != 1)):
        raise ToolError(
            message="Binary upload fields require content_base64.",
            hint="Send the file bytes as base64, or remove the binary fields for text.",
        )
    if content is None:
        raise ToolError(
            message="Send content for a text file or content_base64 for a binary file.",
            hint="For a PDF, encode one chunk of its bytes as base64.",
        )
    return compact(await files_tools.upload(clients, path=path, content=content))

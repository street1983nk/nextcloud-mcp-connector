"""Registration of the mail tool. The logic lives in :mod:`mcp_connector.tools.mail`.

``level`` is a ``Literal`` and therefore an enum in the input schema, not a free string: the
model sees the three valid values instead of guessing "inbox" or "folders" and paying a round
trip for the correction (D-06, D-14).

The tool is listed unconditionally, even on an instance without the Mail app. A credential
dependent ``tools/list`` is not cacheable, breaks the token budget gate and surprises clients
that persist tool lists; the honest answer to a missing app is the sentence the tool returns
(SRV-04).

Empty strings are the defaults instead of ``None``, so no ``anyOf`` of string and null reaches
the schema; the body below turns them back into ``None`` before the call.

One tool and no second one, which is the whole security statement of this family: there is no
send, no draft, no move, no flag and no delete here, and the full text of a single mail travels
through the existing ``fetch`` with ``mail:<databaseId>`` rather than through a tool of its own.

The full filter grammar stands in ``README.md`` and in the runtime hint of
:data:`mcp_connector.tools.mail._FILTER_HINT`, never in this file: every byte here is paid for
in every ``tools/list`` of every session, a grammar is read once, and a wrong condition costs
exactly one round trip because the refusal names all seven types itself. What stays here is the
short form a model needs to write a condition at all: the level it applies to, the shape
``type:value``, the seven names and the one rule that silently swallows a wrong answer instead
of failing (``start`` and ``end`` are Unix seconds). The earlier wording of this paragraph sent
the grammar into the docstring of the tool "instead of the schema", which was measured wrong in
plan 11-07: a tool description and a ``Field`` description are two keys of the same
``tools/list`` payload, so moving text between them saves nothing and the line break of a
docstring costs two bytes where a description costs none. Only compression is a saving.

The docstring names both truncation keys, and that is the one sentence of it that buys itself
back: ``truncated`` is the cut **page**, ``preview_truncated`` the cut **preview** of a single
entry, and before plan 11-08 both were called ``truncated``. A model that reads the entry level
flag as a page flag pages in a circle, which costs more round trips than the fifty odd bytes
this sentence occupies; the filter line above it was compressed in the same edit so the tool
stays under its own ceiling (``MAX_TOOL_BYTES``, plan 11-07).
"""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import mail as mail_tools
from . import READ_ONLY, compact, graceful, mcp


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def mail_browse(
    level: Annotated[
        Literal["accounts", "mailboxes", "messages"],
        Field(description="What to list; mailboxes needs account_id, messages mailbox_id"),
    ] = "accounts",
    account_id: Annotated[str, Field(description="Account id from level=accounts")] = "",
    mailbox_id: Annotated[str, Field(description="Mailbox id from level=mailboxes")] = "",
    filter: Annotated[  # noqa: A002 - the name of the parameter in the Mail app
        str,
        Field(
            description=(
                "Only level=messages: space-separated type:value; types "
                "is/not/from/subject/tags/start/end; start/end in Unix seconds"
            )
        ),
    ] = "",
    limit: Annotated[
        int, Field(ge=1, le=mail_tools.MAX_LIMIT, description="Maximum entries")
    ] = mail_tools.DEFAULT_LIMIT,
    cursor: Annotated[
        str,
        Field(description="Next page handle from a truncated answer; only level=messages"),
    ] = "",
    ctx: Context | None = None,
) -> str:
    """List the mail accounts of this user, the mailboxes of one, or the messages of one.

    Envelopes newest first; the full text of one is a fetch("mail:<id>") away. Percent-encode a
    filter value with a space or colon (subject:Rechnung%20Mai). truncated: page cut;
    preview_truncated: preview cut. Reads only: never sends, drafts, moves, flags or
    deletes."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await mail_tools.browse(
            clients,
            level=level,
            account_id=account_id or None,
            mailbox_id=mailbox_id or None,
            filter=filter or None,
            limit=limit,
            cursor=cursor or None,
        )
    )

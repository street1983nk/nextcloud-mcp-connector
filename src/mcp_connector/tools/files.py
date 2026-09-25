"""File tools: finding, browsing, reading and downloading files, and creating new ones.

Three guards protect the model's context window and the user's data (threat T-01-13):
the path guard runs before any request, ``files_read`` refuses binary content instead of
shipping base64, and the size cap turns a large read into a marked slice with a
``next_offset`` instead of a multi-megabyte answer.

The binary download path has a per-response size ceiling and a continuation offset. It
returns an MCP embedded resource instead of putting base64 into a text answer, so a capable
client can save or forward the file without feeding its bytes to the model.

The two list tools add another guard: every answer that had to stop early says so with
``truncated`` and hands out a cursor handle, so a folder with ten thousand entries costs
one page, not one context window (threat T-01-34).

``upload`` is the only write in this package, and it can only create. Everything that
could turn it into a replace is refused before the request or by Nextcloud itself.
"""

import base64
import re
import uuid
from typing import Any

from .. import config, ids, paging
from ..errors import ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import dav

DEFAULT_MAX_BYTES = 512 * 1024
HARD_MAX_BYTES = 2 * 1024 * 1024

#: A download is carried inline as an MCP embedded resource. Bound each response, rather
#: than the total file: callers continue at ``next_offset`` until the whole file is local.
DEFAULT_DOWNLOAD_BYTES = 8 * 1024 * 1024
HARD_DOWNLOAD_BYTES = 8 * 1024 * 1024

#: Nextcloud's v2 chunk endpoint accepts chunks from 5 MiB through 5 GiB, except for the
#: final chunk. Keep each MCP request bounded while allowing a file to span up to 10,000 parts.
HARD_UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
MIN_UPLOAD_CHUNK_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_CHUNKS = 10_000

DEFAULT_SEARCH_LIMIT = 25
#: Nextcloud's own default cap for a search without an explicit limit. Going past it would
#: only make an answer longer, not more useful.
MAX_SEARCH_LIMIT = 100

DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 200

#: Ceiling for the number of hits fetched to serve one page. WebDAV SEARCH knows a limit
#: but no offset, so a later page is served by asking for more results and slicing. This
#: keeps that trick from turning into an unbounded request on page four hundred.
MAX_SEARCH_FETCH = 500

#: One sentence against a whole class of wrong model statements (pitfall 5). It rides on
#: every answer, not only on the empty ones: a short hit list is exactly the situation in
#: which a model concludes "the document does not exist".
SEARCH_NOTE = "matched on names only; contents are not indexed"

#: Appended to the note when the answer stopped at :data:`MAX_SEARCH_FETCH`. Without it a
#: capped answer would be indistinguishable from a complete one (WR-02).
SEARCH_CAP_NOTE = f"result window capped at {MAX_SEARCH_FETCH} hits; narrow the folder or the term"

_QUERY_HINT = (
    "Give part of a file or folder name, for example 'budget'. "
    "Words that only appear inside a document are not indexed."
)

_TEXT_TYPES = frozenset(
    {
        "application/json",
        "application/xml",
        "application/yaml",
        "application/x-yaml",
        "application/javascript",
        "application/sql",
    }
)
_TEXT_SUFFIXES = ("+json", "+xml", "+yaml")

# Names only parameters the registered tool actually has (WR-03): ``files_read`` takes
# ``path`` and ``offset``; ``max_bytes`` exists for Python callers only.
_SLICE_HINT = (
    "Large files are served in slices. Read from offset 0 and continue at the "
    "next_offset from each answer until truncated is no longer set."
)

DEFAULT_CONTENT_TYPE = "text/markdown"

# type/subtype with the token characters of RFC 9110. No parameters, no whitespace, and
# above all no control characters that could split the request header.
_CONTENT_TYPE_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+/[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
_UPLOAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_FILE_TARGET_HINT = (
    "Give the full path of the new file, for example /Docs/meeting-notes.md. "
    "This tool writes files; it does not create folders."
)


async def search(
    clients: NcClients,
    query: str,
    folder: str = "/",
    limit: int = DEFAULT_SEARCH_LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Search file and folder names below ``folder`` and return a compact hit list.

    The hits keep the order Nextcloud returns them in. That is deliberate: a later page is
    fetched by asking the server for more results and skipping the ones already seen, and
    re-sorting a partial result would make page two repeat entries from page one.

    A limit outside the range is capped instead of refused. The model asked a legitimate
    question with an unhelpful number, and an error would only cost a round trip.
    """
    term = (query or "").strip()
    if not term:
        raise ToolError(message="The search term is empty.", hint=_QUERY_HINT)

    target_folder = dav.safe_path(folder)
    capped = min(max(limit, 1), MAX_SEARCH_LIMIT)

    offset = 0
    if cursor:
        state = paging.decode_cursor(cursor)
        paging.check_scope(state, "q", term, "search")
        paging.check_scope(state, "f", target_folder, "search")
        offset = paging.read_offset(state)

    scope = dav.search_scope(clients.creds, target_folder)
    # One more than the window, so "there is more" is an observation and not a guess.
    fetch = min(offset + capped + 1, MAX_SEARCH_FETCH)
    hits = await dav.search(clients.client, clients.creds, scope, term, fetch)

    window = hits[offset : offset + capped]
    result: dict[str, Any] = {
        "query": term,
        "folder": target_folder,
        "count": len(window),
        "items": [_as_item(hit) for hit in window],
        "note": SEARCH_NOTE,
    }
    if len(hits) > offset + capped:
        result["truncated"] = True
        result["next"] = paging.encode_cursor({"o": offset + capped, "q": term, "f": target_folder})
    elif offset + capped + 1 > MAX_SEARCH_FETCH and len(hits) == MAX_SEARCH_FETCH:
        # The sentinel row could not be requested: the fetch was clamped at the ceiling
        # and the server filled it completely, so more hits may exist. No cursor here,
        # because a later page cannot be served past the ceiling (WR-02).
        result["truncated"] = True
        result["note"] = f"{SEARCH_NOTE}; {SEARCH_CAP_NOTE}"
    return result


async def list_dir(
    clients: NcClients,
    path: str = "/",
    limit: int = DEFAULT_LIST_LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List the direct children of one folder, folders first and then names.

    The order is fixed here rather than left to the server, because the pages of a listing
    are cut out of it: an unstable order would silently drop or repeat entries between two
    pages.
    """
    target = dav.safe_path(path)
    capped = min(max(limit, 1), MAX_LIST_LIMIT)

    offset = 0
    if cursor:
        state = paging.decode_cursor(cursor)
        paging.check_scope(state, "p", target, "listing")
        offset = paging.read_offset(state)

    itself, children = await dav.propfind_children(clients.client, clients.creds, target)
    if not itself["is_collection"]:
        raise ToolError(
            message=f"{target} is a file, not a folder.",
            hint="Use files_read to read a file, or list the folder that contains it.",
        )

    children.sort(key=lambda entry: (not entry["is_collection"], entry["name"].casefold()))
    window = children[offset : offset + capped]

    result: dict[str, Any] = {
        "path": target,
        "count": len(window),
        "items": [_as_item(child) for child in window],
    }
    if len(children) > offset + capped:
        result["truncated"] = True
        result["next"] = paging.encode_cursor({"o": offset + capped, "p": target})
    return result


def _as_item(entry: dict[str, Any]) -> dict[str, Any]:
    """Project one DAV entry onto the answer shape, without the fields it does not have.

    Every key is paid for in every hit of every answer, so an empty mimetype (folders have
    none) is left out instead of shipped as an empty string.
    """
    item: dict[str, Any] = {
        "path": entry["path"],
        "name": entry["name"],
        "kind": "folder" if entry["is_collection"] else "file",
        "size": entry["size"],
    }
    if entry["content_type"]:
        item["content_type"] = entry["content_type"]
    if entry["last_modified"]:
        item["modified"] = entry["last_modified"]
    if entry["fileid"]:
        item["id"] = ids.encode_file(entry["fileid"])
    return item


async def read(
    clients: NcClients,
    path: str,
    offset: int = 0,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """Read a text file and return stable fields: path, content, size, content_type.

    ``truncated`` is true when the answer stops before the end of the file; only then is
    ``next_offset`` present, so the caller never has to guess whether it saw everything.
    """
    if offset < 0:
        raise ToolError(
            message=f"offset must not be negative (got {offset}).",
            hint="Start at offset 0 and follow the next_offset from each answer.",
        )
    if max_bytes < 1 or max_bytes > HARD_MAX_BYTES:
        raise ToolError(
            message=f"max_bytes must be between 1 and {HARD_MAX_BYTES} bytes (got {max_bytes}).",
            hint=_SLICE_HINT,
        )

    target = dav.safe_path(path)
    info = await dav.stat(clients.client, clients.creds, target)

    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to see what is inside a folder.",
        )

    content_type = info["content_type"] or "application/octet-stream"
    if not _is_text(content_type):
        raise ToolError(
            message=f"{target} is {content_type} and not text.",
            hint="Use files_download to retrieve binary files in chunks.",
        )

    size = info["size"]
    if offset > 0 and offset >= size:
        raise ToolError(
            message=f"offset {offset} is at or past the end of {target} ({size} bytes).",
            hint="Read from a smaller offset, or stop: the file has no more content.",
        )

    # A file above HARD_MAX_BYTES is not refused: the answer is the first slice, marked
    # with ``truncated`` and ``next_offset``. Refusing at offset 0 would send the model
    # into a dead end, because the registered tool has no way to shrink the window
    # other than the offset it was just denied (WR-03).
    remaining = size - offset
    if remaining > 0:
        data = await dav.get_range(
            clients.client,
            clients.creds,
            target,
            offset=offset,
            limit=min(max_bytes, remaining),
        )
    else:
        data = b""

    if remaining > 0 and not data:
        raise ToolError(
            message=f"Nextcloud returned an empty chunk before the end of {target}.",
            hint="Retry from the same offset. If the file changed, restart from offset 0.",
        )
    content, used = _decode(data, target)
    result: dict = {
        "path": target,
        "content": content,
        "size": size,
        "content_type": content_type,
        "truncated": offset + used < size,
    }
    if result["truncated"]:
        result["next_offset"] = offset + used
    return result


async def download(
    clients: NcClients,
    path: str,
    offset: int = 0,
    max_bytes: int = DEFAULT_DOWNLOAD_BYTES,
) -> dict[str, Any]:
    """Read one binary slice for an MCP embedded resource.

    Unlike :func:`read`, this path accepts every MIME type and never decodes the body. A
    caller can therefore assemble a file of any total size while each response stays
    bounded by :data:`HARD_DOWNLOAD_BYTES`.
    """
    if offset < 0:
        raise ToolError(
            message=f"offset must not be negative (got {offset}).",
            hint="Start at offset 0 and follow next_offset until truncated is false.",
        )
    if max_bytes < 1 or max_bytes > HARD_DOWNLOAD_BYTES:
        raise ToolError(
            message=f"max_bytes must be between 1 and {HARD_DOWNLOAD_BYTES} bytes.",
            hint="Use the default chunk size or choose a smaller positive value.",
        )

    target = dav.safe_path(path)
    info = await dav.stat(clients.client, clients.creds, target)

    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to choose a file inside the folder.",
        )

    size = info["size"]
    if offset > 0 and offset >= size:
        raise ToolError(
            message=f"offset {offset} is at or past the end of {target} ({size} bytes).",
            hint="Use the next_offset from the previous chunk, or stop when truncated is false.",
        )

    if size == 0:
        data = b""
    else:
        requested = min(max_bytes, size - offset)
        data = await dav.get_range(
            clients.client,
            clients.creds,
            target,
            offset=offset,
            limit=requested,
        )
        data = data[:requested]

    if size > offset and not data:
        raise ToolError(
            message=f"Nextcloud returned an empty chunk before the end of {target}.",
            hint="Retry from the same offset. If it repeats, download the file in Nextcloud.",
        )

    result: dict[str, Any] = {
        "path": target,
        "size": size,
        "content_type": info["content_type"] or "application/octet-stream",
        "offset": offset,
        "bytes": len(data),
        "truncated": offset + len(data) < size,
        "content": data,
    }
    if result["truncated"]:
        result["next_offset"] = offset + len(data)
    return result


async def upload(
    clients: NcClients,
    path: str,
    content: str,
    content_type: str = DEFAULT_CONTENT_TYPE,
) -> dict:
    """Create a new text file and return path, etag and ``created``.

    There is no overwrite mode and no force flag, by design (D-03, TOOL-09). If something
    already exists at the target, Nextcloud refuses the request and the caller gets a
    conflict it can act on: pick another name.
    """
    if (path or "").strip().endswith("/"):
        raise ToolError(
            message=f"{path!r} names a folder, not a file.",
            hint=_FILE_TARGET_HINT,
        )

    target = dav.safe_path(path)
    if target == config.files_root():
        raise ToolError(
            message="The upload target is the root folder, not a file.",
            hint=_FILE_TARGET_HINT,
        )

    if not _CONTENT_TYPE_RE.fullmatch(content_type or ""):
        raise ToolError(
            message=f"{content_type!r} is not a plain mimetype.",
            hint=f"Use a bare type/subtype such as {DEFAULT_CONTENT_TYPE} or text/plain.",
        )

    try:
        data = content.encode("utf-8")
    except UnicodeEncodeError:
        raise ToolError(
            message="The content is not valid UTF-8 text.",
            hint="Send plain text; this tool does not upload binary content.",
        ) from None

    return await dav.put_new_file(clients.client, clients.creds, target, data, content_type)


async def upload_binary(
    clients: NcClients,
    path: str,
    content_base64: str,
    total_bytes: int,
    chunk_index: int = 1,
    upload_id: str = "",
    final: bool = False,
    content_type: str = "application/octet-stream",
) -> dict[str, Any]:
    """Upload one base64 chunk and optionally assemble a new binary file.

    Nextcloud stores the chunks in a temporary upload folder and assembles them only on the
    final call. The destination is always moved with ``Overwrite: F``, so a target that was
    created by somebody else is refused rather than replaced. The returned upload id and
    ``next_chunk`` let a caller continue after a transient connection failure without any
    state in this process.
    """
    if (path or "").strip().endswith("/"):
        raise ToolError(message=f"{path!r} names a folder, not a file.", hint=_FILE_TARGET_HINT)

    target = dav.safe_path(path)
    if target == config.files_root():
        raise ToolError(
            message="The upload target is the root folder, not a file.",
            hint=_FILE_TARGET_HINT,
        )
    if total_bytes < 0:
        raise ToolError(
            message="total_bytes must not be negative.",
            hint="Send the complete byte length of the file before uploading its chunks.",
        )
    if chunk_index < 1 or chunk_index > MAX_UPLOAD_CHUNKS:
        raise ToolError(
            message=f"chunk_index must be between 1 and {MAX_UPLOAD_CHUNKS}.",
            hint="Start at chunk 1 and follow next_chunk for each continuation.",
        )
    if not _CONTENT_TYPE_RE.fullmatch(content_type or ""):
        raise ToolError(
            message=f"{content_type!r} is not a plain mimetype.",
            hint="Use a bare type/subtype such as application/pdf.",
        )

    raw_id = (upload_id or "").strip()
    if raw_id and not _UPLOAD_ID_RE.fullmatch(raw_id):
        raise ToolError(
            message="upload_id contains unsupported characters.",
            hint="Reuse the upload_id returned by the previous chunk without changing it.",
        )
    if chunk_index == 1 and not raw_id:
        raw_id = uuid.uuid4().hex
    elif chunk_index != 1 and not raw_id:
        raise ToolError(
            message="upload_id is required after the first chunk.",
            hint="Pass the upload_id returned with the previous chunk.",
        )

    encoded = (content_base64 or "").strip()
    if len(encoded) > 4 * ((HARD_UPLOAD_CHUNK_BYTES + 2) // 3):
        raise ToolError(
            message="The encoded chunk exceeds the 8 MiB decoded limit.",
            hint="Split the file into smaller chunks before base64 encoding.",
        )
    if total_bytes > HARD_UPLOAD_CHUNK_BYTES * MAX_UPLOAD_CHUNKS:
        raise ToolError(
            message="The file exceeds the maximum supported upload size.",
            hint="Use at most 10,000 chunks of 8 MiB each.",
        )
    if not final and chunk_index == MAX_UPLOAD_CHUNKS:
        raise ToolError(
            message="The last supported chunk must finalize the upload.",
            hint="Set final=true on chunk 10,000.",
        )
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ToolError(
            message="content_base64 is not valid base64.",
            hint="Encode the raw file bytes as standard base64 before sending the chunk.",
        ) from None

    if len(data) > HARD_UPLOAD_CHUNK_BYTES:
        raise ToolError(
            message=f"This chunk is larger than {HARD_UPLOAD_CHUNK_BYTES} bytes.",
            hint="Send at most 8 MiB of decoded bytes per call.",
        )
    if total_bytes < len(data):
        raise ToolError(
            message="total_bytes is smaller than the supplied chunk.",
            hint="Use the byte length of the complete file, not the current chunk.",
        )
    minimum_sent = (chunk_index - 1) * MIN_UPLOAD_CHUNK_BYTES + len(data)
    if minimum_sent > total_bytes or (not final and minimum_sent >= total_bytes):
        raise ToolError(
            message="The chunk number and size are inconsistent with total_bytes.",
            hint="Check the total file size and set final=true on its last chunk.",
        )
    if not final and len(data) < MIN_UPLOAD_CHUNK_BYTES:
        raise ToolError(
            message="A non-final chunk must contain at least 5 MiB.",
            hint="Use final=true for the last, smaller chunk.",
        )
    if final and chunk_index == 1 and len(data) != total_bytes:
        raise ToolError(
            message="A one-chunk upload must contain exactly total_bytes.",
            hint="Set final=true only when this chunk contains the complete file.",
        )
    if total_bytes == 0 and (chunk_index != 1 or not final or data):
        raise ToolError(
            message="An empty file must be uploaded as one empty final chunk.",
            hint="Use chunk_index=1, final=true and an empty base64 value.",
        )
    if total_bytes == 0:
        result = await dav.put_new_file(clients.client, clients.creds, target, data, content_type)
        return {
            **result,
            "upload_id": raw_id,
            "chunk_index": 1,
            "bytes": 0,
            "total_bytes": 0,
            "completed": True,
        }

    if chunk_index == 1:
        await dav.start_chunked_upload(clients.client, clients.creds, target, raw_id)
    await dav.put_upload_chunk(
        clients.client,
        clients.creds,
        target,
        raw_id,
        chunk_index,
        data,
        total_bytes,
        content_type,
    )

    if not final:
        return {
            "path": target,
            "upload_id": raw_id,
            "chunk_index": chunk_index,
            "bytes": len(data),
            "total_bytes": total_bytes,
            "completed": False,
            "next_chunk": chunk_index + 1,
        }

    result = await dav.finish_chunked_upload(
        clients.client, clients.creds, target, raw_id, total_bytes
    )
    return {
        **result,
        "upload_id": raw_id,
        "chunk_index": chunk_index,
        "bytes": len(data),
        "total_bytes": total_bytes,
        "completed": True,
    }


def _is_text(content_type: str) -> bool:
    base = content_type.split(";", 1)[0].strip().lower()
    return (
        base.startswith("text/")
        or base in _TEXT_TYPES
        or any(base.endswith(suffix) for suffix in _TEXT_SUFFIXES)
    )


def _decode(data: bytes, path: str) -> tuple[str, int]:
    """Decode UTF-8, tolerating a multi byte character cut by the range boundary."""
    try:
        return data.decode("utf-8"), len(data)
    except UnicodeDecodeError as exc:
        tail_cut = exc.start > 0 and exc.start >= len(data) - 3
        if tail_cut:
            try:
                return data[: exc.start].decode("utf-8"), exc.start
            except UnicodeDecodeError:
                pass
        raise ToolError(
            message=f"{path} is not valid UTF-8 text.",
            hint="Nextcloud reports this file as text, but its bytes are not UTF-8.",
        ) from None

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

import asyncio
import base64
import re
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from .. import config, documents, ids, paging
from ..documents import detect as document_detect
from ..errors import REASON_GUARD_TRIPPED, ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import dav
from ..nextcloud.exclusion import TagScope
from . import withhold

DEFAULT_MAX_BYTES = 512 * 1024
HARD_MAX_BYTES = 2 * 1024 * 1024

#: Slices of files_read_as_markdown are counted in characters of the converted text, because
#: the source has no useful byte positions. Same two numbers as the byte slices above.
DEFAULT_MAX_CHARS = 524288
HARD_MAX_CHARS = 2097152

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

# ChatGPT file parameters carry a temporary HTTPS URL. OpenAI does not promise one
# fixed download hostname. ChatGPT can also hand out signed Azure Blob Storage URLs for
# attachments. Matching is suffix-aware (for example, ``blob.core.windows.net.evil.test``
# does not match the Azure suffix).
_OPENAI_FILE_HOST_SUFFIXES = (
    "oaiusercontent.com",
    "chatgpt.com",
    "openai.com",
    "blob.core.windows.net",
)
_OPENAI_FILE_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
MAX_ATTACHMENT_BYTES = HARD_UPLOAD_CHUNK_BYTES * MAX_UPLOAD_CHUNKS

_FILE_TARGET_HINT = (
    "Give the full path of the new file, for example /Docs/meeting-notes.md. "
    "To create a folder, call files_upload with only the new folder path."
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

    Hits tagged ``kein-ki`` or below a tagged folder are left out without a trace, and
    the offsets of the cursor count visible hits only, so ``truncated`` never turns into
    a counter of withheld ones (EXCL-01). When the tag check cannot be answered, the hit
    list is empty with one ``degraded`` entry (D-27-03).

    A tagged folder, or one below a tagged folder, given as ``folder`` does not exist as a
    search root (D-28-19): it answers with exactly the ``File not found`` of an invented
    folder, the same scope path included, instead of an empty hit list that would tell the
    two apart. No request is added for it; the one SEARCH is sent either way.
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

    search_scope = dav.search_scope(clients.creds, target_folder)
    # One more than the window, so "there is more" is an observation and not a guess.
    needed = offset + capped + 1
    tags, first = await asyncio.gather(
        clients.exclusion.scope(clients),
        dav.search(
            clients.client, clients.creds, search_scope, term, min(needed, MAX_SEARCH_FETCH)
        ),
        return_exceptions=True,
    )
    if isinstance(tags, BaseException):
        raise tags
    if tags.state == "unverifiable":
        return {
            "query": term,
            "folder": target_folder,
            "count": 0,
            "items": [],
            "note": SEARCH_NOTE,
            "degraded": [withhold.degraded_entry("source")],
        }
    # D-28-17: the error of the SEARCH answers first, so a 5xx or a timeout reads alike for
    # a tagged and an invented root (review WR-01 of phase 28). An invented root never gets
    # past this line, because SEARCH itself answers it with a 404; a tagged root exists and
    # arrives here with its 207.
    if isinstance(first, BaseException):
        raise first
    # D-28-19: a tagged folder does not exist as a search root. It answers with the 404 of
    # an invented root, from the same factory.
    if tags.excludes(path=target_folder):
        raise dav.not_found(search_scope)
    hits, at_ceiling = await _visible_hits(clients, tags, search_scope, term, needed, first)

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
    elif at_ceiling:
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

    Entries tagged ``kein-ki`` or below a tagged folder are left out without a trace, and
    a tagged target answers like a missing one (EXCL-01). When the tag check cannot be
    answered, the listing is empty with one ``degraded`` entry (D-27-03).
    """
    target = dav.safe_path(path)
    capped = min(max(limit, 1), MAX_LIST_LIMIT)

    offset = 0
    if cursor:
        state = paging.decode_cursor(cursor)
        paging.check_scope(state, "p", target, "listing")
        offset = paging.read_offset(state)

    scope, listing = await asyncio.gather(
        clients.exclusion.scope(clients),
        dav.propfind_children(clients.client, clients.creds, target),
        return_exceptions=True,
    )
    if isinstance(scope, BaseException):
        raise scope
    if scope.state == "unverifiable":
        # The PROPFIND outcome is not read at all, not even its 404: an existing and a
        # missing folder have to answer the same while the check cannot be answered.
        return {
            "path": target,
            "count": 0,
            "items": [],
            "degraded": [withhold.degraded_entry("source")],
        }
    if isinstance(listing, BaseException):
        raise listing
    itself, entries = listing
    # The target first and before its form: "is a file" would confirm a withheld file.
    if _withheld(scope, itself):
        raise dav.not_found(target)
    if not itself["is_collection"]:
        raise ToolError(
            message=f"{target} is a file, not a folder.",
            hint="Use files_read to read a file, or list the folder that contains it.",
        )

    # Filtered before the sort and the window, so count, truncated and next only ever
    # see what the caller may see (D-v1.7-02).
    children = [entry for entry in entries if not _withheld(scope, entry)]
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


def _withheld(scope: TagScope, entry: dict[str, Any]) -> bool:
    """Whether a dav entry (absolute home path, fileid) is tagged or below a tagged folder."""
    return scope.excludes(path=entry["path"], fileid=entry["fileid"] or None)


async def _visible_hits(
    clients: NcClients,
    scope: TagScope,
    search_scope: str,
    term: str,
    needed: int,
    first: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """The visible hits of a search, fetched until ``needed`` of them are known.

    ``first`` is the answer to the first SEARCH, which ran alongside the guard with the
    limit ``min(needed, MAX_SEARCH_FETCH)``. Filtering can leave fewer visible hits than
    the window plus its sentinel row needs; then the search is repeated with a doubled
    limit, until enough are visible, the server returned fewer than asked for (nothing
    more exists) or the limit reached :data:`MAX_SEARCH_FETCH`. Only then does
    ``truncated`` rest on an observation of a visible hit, never on a withheld one. The
    repeated searches share the scope, so they cost no REPORT; without a tag the first
    answer always suffices and exactly one SEARCH goes out, as before.

    The second value says whether the answer stopped at the ceiling with a full raw
    list, so more hits may exist than could be asked for (the ``SEARCH_CAP_NOTE`` case).
    """
    fetch = min(needed, MAX_SEARCH_FETCH)
    raw = first
    while True:
        visible = [hit for hit in raw if not _withheld(scope, hit)]
        if len(visible) >= needed or len(raw) < fetch or fetch >= MAX_SEARCH_FETCH:
            break
        fetch = min(fetch * 2, MAX_SEARCH_FETCH)
        raw = await dav.search(clients.client, clients.creds, search_scope, term, fetch)
    return visible, fetch >= MAX_SEARCH_FETCH and len(raw) >= MAX_SEARCH_FETCH


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
    *,
    known: Mapping[str, Any] | None = None,
) -> dict:
    """Read a text file and return stable fields: path, content, size, content_type.

    ``truncated`` is true when the answer stops before the end of the file; only then is
    ``next_offset`` present, so the caller never has to guess whether it saw everything.

    A file tagged ``kein-ki``, or below a tagged folder, answers exactly like a path that
    does not exist (EXCL-01); when the tag check cannot be answered, every path gets the
    same uniform refusal (D-27-03).

    ``known`` is for Python callers only and not on the wire (``files_read`` keeps its
    schema): the entry of a file id SEARCH that the same tool call just made inside the
    sandbox scope, which already carries what the stat PROPFIND would answer (plan 27-09,
    the wall clock gap of phase 27). It replaces that PROPFIND and nothing else: the guard
    is asked and applied exactly as on the stat route. An entry that does not describe
    ``path`` is ignored and the stat runs as always.
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
    info = await _visible_stat(clients, target, known)

    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to see what is inside a folder.",
        )

    content_type = info["content_type"] or "application/octet-stream"
    if not _is_text(content_type):
        if document_detect.supported_format(content_type, target) is not None:
            hint = "Use files_read_as_markdown to read this document as Markdown."
        else:
            hint = "Use files_download to retrieve binary files in chunks."
        raise ToolError(message=f"{target} is {content_type} and not text.", hint=hint)

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


def _source_too_large(target: str, size: int | None) -> ToolError:
    """The size-cap refusal. ``None`` means the body was cut at the cap, so no size is known."""
    shown = "larger than" if size is None else f"{size} bytes, above"
    return ToolError(
        message=f"{target} is {shown} the {documents.MAX_SOURCE_BYTES} byte cap.",
        hint="Use files_download to retrieve the raw file in chunks.",
        reason=REASON_GUARD_TRIPPED,
    )


async def read_as_markdown(
    clients: NcClients,
    path: str,
    offset: int = 0,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict:
    """Convert one DOCX, XLSX, PPTX or PDF file to Markdown and answer a slice of it.

    Same continuation contract as :func:`read`: ``truncated`` says whether the answer stops
    early and ``next_offset`` is present only then. Offsets count characters of the Markdown.
    The whole file is downloaded and converted on every call; the server holds nothing between
    calls (D-20), and the caps in :mod:`mcp_connector.documents` bound the work.

    The ``kein-ki`` guard is asked alongside the stat, exactly as in :func:`read`: a tagged
    document answers like a path that does not exist, before its type is looked at (EXCL-01).
    """
    if offset < 0:
        raise ToolError(
            message=f"offset must not be negative (got {offset}).",
            hint="Start at offset 0 and follow the next_offset from each answer.",
        )
    if max_chars < 1 or max_chars > HARD_MAX_CHARS:
        raise ToolError(
            message=f"max_chars must be between 1 and {HARD_MAX_CHARS} (got {max_chars}).",
            hint=_SLICE_HINT,
        )

    target = dav.safe_path(path)
    info = await _visible_stat(clients, target)
    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to see what is inside a folder.",
        )
    content_type = info["content_type"] or "application/octet-stream"
    if _is_text(content_type):
        raise ToolError(
            message=f"{target} is {content_type}, which is text already.",
            hint="Use files_read for text files.",
        )
    # Detect before download: an unsupported type costs one PROPFIND and no GET.
    document_detect.detect(content_type, target)
    size = int(info["size"])
    if size > documents.MAX_SOURCE_BYTES:
        raise _source_too_large(target, size)

    # The slot is taken before the GET: it bounds the worker processes and the bytes held
    # for them, so a burst of calls queues here instead of buffering a file per call.
    async with documents.slot():
        # The stat size is a claim, not a limit: the file can grow between PROPFIND and
        # GET. Ask for one byte more than the cap, so a body above it is visible and refused.
        data = await dav.get_range(
            clients.client, clients.creds, target, limit=documents.MAX_SOURCE_BYTES + 1
        )
        if len(data) > documents.MAX_SOURCE_BYTES:
            raise _source_too_large(target, None)
        converted = await documents.convert(data, content_type, target)
    markdown = converted.markdown
    length = len(markdown)
    if offset > 0 and offset >= length:
        raise ToolError(
            message=f"offset {offset} is at or past the end of the text ({length} characters).",
            hint="Read from a smaller offset, or stop: the document has no more content.",
        )
    content = markdown[offset : offset + max_chars]
    result: dict = {
        "path": target,
        "content": content,
        "content_type": content_type,
        "format": converted.format,
        "size": size,
        "markdown_length": length,
        "truncated": offset + len(content) < length,
    }
    if result["truncated"]:
        result["next_offset"] = offset + len(content)
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

    A file tagged ``kein-ki``, or below a tagged folder, answers exactly like a path that
    does not exist (EXCL-01); when the tag check cannot be answered, every path gets the
    same uniform refusal (D-27-03).
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
    info = await _visible_stat(clients, target)

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


async def create_folder(clients: NcClients, path: str) -> dict[str, Any]:
    """Create exactly one folder and never replace an existing entry.

    The parent must already exist. The same exclusion guard used by file uploads runs
    before MKCOL, so a folder cannot be created inside a ``kein-ki`` subtree.
    """
    target = dav.safe_path(path)
    if target == config.files_root():
        raise ToolError(
            message="The requested folder is the files root, which already exists.",
            hint="Give a new folder below the root, for example /AI.",
        )
    await _writable(clients, target)
    return await dav.create_folder(clients.client, clients.creds, target)


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

    A destination tagged ``kein-ki``, or below a tagged folder, is refused before any
    write with the sentence of a missing parent folder (D-27-01), also for a tagged file
    under a visible parent; when the tag check cannot be answered, nothing is written
    (D-27-02). The reasoning, including the residual oracle, sits in :func:`_writable`.
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

    await _writable(clients, target)
    return await dav.put_new_file(clients.client, clients.creds, target, data, content_type)


def _openai_download_url(value: str) -> str:
    """Validate a ChatGPT file-parameter URL before any network request is made."""
    raw = (value or "").strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        parsed = None
        port = None
    host = (parsed.hostname or "").lower() if parsed is not None else ""
    trusted_host = any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in _OPENAI_FILE_HOST_SUFFIXES
    )
    if (
        parsed is None
        or parsed.scheme != "https"
        or not trusted_host
        or parsed.username is not None
        or parsed.password is not None
        or (port is not None and port != 443)
        or bool(parsed.fragment)
    ):
        label = host or "<missing>"
        raise ToolError(
            message=f"The attachment download host {label!r} is not an allowed ChatGPT file host.",
            hint="Attach the file to the ChatGPT message and retry the upload.",
        )
    return raw


def _attachment_content_type(declared: str, response: httpx.Response) -> str:
    """Choose one bare MIME type without copying an unchecked header value to Nextcloud."""
    supplied = (declared or "").strip()
    if supplied:
        if not _CONTENT_TYPE_RE.fullmatch(supplied):
            raise ToolError(
                message=f"{supplied!r} is not a plain mimetype.",
                hint="Retry the attachment; ChatGPT should provide a bare type/subtype.",
            )
        return supplied
    header = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
    return header if _CONTENT_TYPE_RE.fullmatch(header) else "application/octet-stream"


async def upload_attachment(
    clients: NcClients,
    path: str,
    download_url: str,
    file_id: str,
    mime_type: str = "",
) -> dict[str, Any]:
    """Stream one ChatGPT file parameter into a create-only Nextcloud PUT.

    The temporary download URL is never returned, logged, or sent to Nextcloud. The file
    name supplied by ChatGPT is deliberately not used here either: ``path`` is the single
    destination authority, so a crafted attachment name cannot escape the folder chosen by
    the model and the path guard.
    """
    if (path or "").strip().endswith("/"):
        raise ToolError(message=f"{path!r} names a folder, not a file.", hint=_FILE_TARGET_HINT)
    target = dav.safe_path(path)
    if target == config.files_root():
        raise ToolError(
            message="The upload target is the root folder, not a file.",
            hint=_FILE_TARGET_HINT,
        )
    if not (file_id or "").strip():
        raise ToolError(
            message="The ChatGPT attachment has no file id.",
            hint="Attach the file to the ChatGPT message and retry the upload.",
        )
    source_url = _openai_download_url(download_url)
    await _writable(clients, target)

    # Do not follow redirects: the signed URL is the only origin ChatGPT authorized. A
    # redirect would need a fresh allowlist decision and could otherwise bypass the SSRF
    # boundary above. ``Accept-Encoding: identity`` keeps Content-Length and byte counts
    # about the original file rather than a transfer encoding.
    async with httpx.AsyncClient(
        follow_redirects=False, timeout=_OPENAI_FILE_TIMEOUT
    ) as source_client:
        async with source_client.stream(
            "GET", source_url, headers={"Accept-Encoding": "identity"}
        ) as source:
            if 300 <= source.status_code < 400:
                raise ToolError(
                    message="The ChatGPT attachment download redirected unexpectedly.",
                    hint=(
                        "Retry from the original attachment so ChatGPT can issue a fresh file URL."
                    ),
                )
            if source.status_code in (401, 403, 404):
                raise ToolError(
                    message="The ChatGPT attachment link is unavailable or expired.",
                    hint=(
                        "Retry from the original attachment so ChatGPT can issue a fresh file URL."
                    ),
                )
            if source.status_code != 200:
                raise ToolError(
                    message=(
                        "The ChatGPT attachment download failed with HTTP "
                        f"{source.status_code}."
                    ),
                    hint="Retry the upload from the original attachment.",
                )

            raw_length = source.headers.get("Content-Length", "").strip()
            content_length = (
                int(raw_length) if raw_length.isascii() and raw_length.isdigit() else None
            )
            if content_length is not None and content_length > MAX_ATTACHMENT_BYTES:
                raise ToolError(
                    message="The attachment exceeds the maximum supported upload size.",
                    hint="Upload a smaller file or split it before attaching it to ChatGPT.",
                )
            content_type = _attachment_content_type(mime_type, source)
            seen = 0

            async def body() -> AsyncIterator[bytes]:
                nonlocal seen
                async for chunk in source.aiter_raw():
                    seen += len(chunk)
                    if seen > MAX_ATTACHMENT_BYTES:
                        raise ToolError(
                            message="The attachment exceeds the maximum supported upload size.",
                            hint=(
                                "Upload a smaller file or split it before attaching it to ChatGPT."
                            ),
                        )
                    if content_length is not None and seen > content_length:
                        raise ToolError(
                            message="The attachment body is larger than its declared size.",
                            hint="Retry the upload from the original attachment.",
                        )
                    yield chunk
                if content_length is not None and seen != content_length:
                    raise ToolError(
                        message="The attachment download ended before its declared size.",
                        hint="Retry the upload from the original attachment.",
                    )

            result = await dav.put_new_file_stream(
                clients.client,
                clients.creds,
                target,
                body(),
                content_type,
                content_length=content_length,
            )
            return {**result, "bytes": seen, "content_type": content_type}


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

    Every write of every chunk call first checks the destination against ``kein-ki``: a
    tagged destination, or one below a tagged folder, gets the refusal of a missing parent
    folder (D-27-01, also for a tagged file under a visible parent), and a check that
    cannot be answered stops the call without any write (D-27-02). See :func:`_writable`.
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
        await _writable(clients, target)
        result = await dav.put_new_file(clients.client, clients.creds, target, data, content_type)
        return {
            **result,
            "upload_id": raw_id,
            "chunk_index": 1,
            "bytes": 0,
            "total_bytes": 0,
            "completed": True,
        }

    # The check guards every write of every chunk call, not only the first: a tag set
    # between two calls stops the upload at the next one. It is the destination that is
    # checked, never the temporary upload folder. One guard per tool call, so the checks
    # of one call share a single REPORT.
    if chunk_index == 1:
        await _writable(clients, target)
        await dav.start_chunked_upload(clients.client, clients.creds, target, raw_id)
    await _writable(clients, target)
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

    await _writable(clients, target)
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


async def _writable(clients: NcClients, target: str) -> None:
    """Refuse a write into what is tagged ``kein-ki`` like a write into a missing folder.

    D-27-01: a destination tagged itself or below a tagged folder gets exactly the refusal
    Nextcloud gives when the parent folder does not exist, from the same factory. That
    includes the edge case of a tagged file under a visible parent folder: "a file already
    exists" would confirm the file outright, while "the parent does not exist" next to a
    visible parent only tells that something is special there. Every refusal differs from
    the 201 a free name would get, so this residual oracle cannot be avoided without
    writing; one wording for all of them is the most consistent (documented in phase 29).

    D-27-02: when the check cannot be answered, nothing is written, fail-closed; an
    unchecked upload into a withheld subtree is never an option.

    No stat before the check: a PROPFIND would itself tell existing from missing.
    """
    scope = await clients.exclusion.scope(clients)
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if scope.excludes(path=target):
        raise dav.parent_missing(target)


async def _visible_stat(
    clients: NcClients, target: str, known: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """``dav.stat`` of ``target``, or the error a path that does not exist would get.

    The guard is asked alongside the PROPFIND, so a tagged path costs the same requests as
    a free one. The order of the decisions is fixed: a guard that could not answer wins
    over everything, even over a 404 of the PROPFIND, so an existing and a missing path
    read the same; then the error of the PROPFIND as it would be without any tag; then the
    tag, before any check of the entry's form (folder, type, offset), because each of
    those would tell a withheld entry from a missing one.

    With a ``known`` entry of exactly this path and a file id, the PROPFIND is skipped and
    the guard alone is awaited; the decisions keep their order, only the PROPFIND error
    step has nothing to decide (T-27-92).
    """
    fileid = str(known.get("fileid") or "") if known is not None else ""
    if known is not None and known.get("path") == target and fileid:
        scope = await clients.exclusion.scope(clients)
        if scope.state == "unverifiable":
            raise withhold.unavailable_error()
        if scope.excludes(path=target, fileid=fileid):
            raise dav.not_found(target)
        return {
            "path": target,
            "is_collection": bool(known.get("is_collection")),
            "content_type": str(known.get("content_type") or ""),
            "size": int(known.get("size") or 0),
            "fileid": fileid,
        }

    scope, info = await asyncio.gather(
        clients.exclusion.scope(clients),
        dav.stat(clients.client, clients.creds, target),
        return_exceptions=True,
    )
    if isinstance(scope, BaseException):
        raise scope
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if isinstance(info, BaseException):
        raise info
    if scope.excludes(path=target, fileid=str(info.get("fileid") or "") or None):
        raise dav.not_found(target)
    return info


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

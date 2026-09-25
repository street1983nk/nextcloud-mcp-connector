"""WebDAV client: SEARCH, PROPFIND, ranged GET, and create-only file uploads.

The ordinary file write is a PUT that carries ``If-None-Match: *``. Large binary uploads use
Nextcloud's private chunk directory and one final MOVE with ``Overwrite: F``; that MOVE only
assembles a new file and can never replace an existing target. No tool exposes delete, copy,
rename, property editing, or an overwrite mode. The precondition is evaluated by Nextcloud in
the same request, which is why this client does no PROPFIND probe before a create-only PUT.

Status handling follows two rules from the research: never repeat a failed
authentication (Nextcloud counts failures per source IP and slows down every user of the
server afterwards), and never let a redirect pass silently (the auth header would go to a
foreign host or vanish).
"""

import hashlib
import re
from collections.abc import Sequence
from posixpath import dirname
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from lxml import etree

from ... import config
from ...errors import (
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from ..credentials import Credentials
from . import xml

DAV_FILES_PREFIX = "/remote.php/dav/files/"
DAV_UPLOADS_PREFIX = "/remote.php/dav/uploads/"

#: Digits, and only ASCII ones. ``str.isdigit`` also accepts a superscript two and an
#: Arabic-Indic digit, and neither is a file id Nextcloud ever handed out. This is the
#: backstop behind ``provider_map._DIGITS`` (review finding WR-02): the one lookup that
#: takes an identifier straight from a model refuses the same set on both layers.
_DIGITS = re.compile(r"[0-9]+")

#: The search endpoint is the DAV root, not the files path: Nextcloud's search backend
#: reports an empty arbiter path, so every other target answers 405.
DAV_ROOT_PATH = "/remote.php/dav/"

_STAT_PROPS = (
    f"{{{xml.DAV}}}getcontentlength",
    f"{{{xml.DAV}}}getcontenttype",
    f"{{{xml.DAV}}}getlastmodified",
    f"{{{xml.DAV}}}getetag",
    f"{{{xml.DAV}}}resourcetype",
    f"{{{xml.OC}}}fileid",
    f"{{{xml.OC}}}permissions",
)

#: Selected for every search hit. Only queryable properties may appear in the comparison,
#: but any property may be selected, which is why the size and the type are in here.
_SEARCH_PROPS = (
    f"{{{xml.DAV}}}displayname",
    f"{{{xml.DAV}}}getcontenttype",
    f"{{{xml.DAV}}}getlastmodified",
    f"{{{xml.DAV}}}getcontentlength",
    f"{{{xml.DAV}}}resourcetype",
    f"{{{xml.OC}}}fileid",
)

#: A folder listing additionally reports the recursive folder size and the permission
#: string, so a caller sees what it may do with an entry before it tries.
_LIST_PROPS = (
    *_SEARCH_PROPS,
    f"{{{xml.OC}}}size",
    f"{{{xml.OC}}}permissions",
)

_PATH_HINT = (
    "Use an absolute path inside the user's own files, for example /Docs/notes.md. "
    "Parent references and backslashes are not accepted."
)

_TERM_HINT = "Give at least one word from the file or folder name, for example 'budget'."


def safe_path(path: str) -> str:
    """Return a normalised absolute path or raise (threat T-01-09, path traversal).

    Runs before any request is built, so an unsafe path never reaches Nextcloud.
    """
    raw = (path or "").strip()
    if not raw:
        raise ToolError(message="No path was given.", hint=_PATH_HINT)
    if "\\" in raw:
        raise ToolError(
            message=f"The path {raw!r} contains a backslash.",
            hint=_PATH_HINT,
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise ToolError(
            message="The path contains a control character.",
            hint=_PATH_HINT,
        )

    segments: list[str] = []
    for segment in raw.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise ToolError(
                message=f"The path {raw!r} points outside the user's files.",
                hint=_PATH_HINT,
            )
        segments.append(segment)
    requested = "/" + "/".join(segments)
    root = config.files_root()
    if root == "/":
        return requested
    # A configured root becomes the virtual `/` for agents: `/scan.pdf` means a file below
    # the bound directory, while its explicit absolute spelling remains accepted as well.
    if requested == root or requested.startswith(root + "/"):
        return requested
    return root if requested == "/" else f"{root}{requested}"


def files_url(creds: Credentials, path: str) -> str:
    """Build the WebDAV URL of a file in the user's own home."""
    user = quote(creds.user, safe="")
    return f"{creds.base_url}{DAV_FILES_PREFIX}{user}{quote(safe_path(path), safe='/')}"


def _stat_body() -> bytes:
    """Build the PROPFIND body with lxml; never with an f-string (threat T-01-11)."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in _STAT_PROPS:
        etree.SubElement(prop, name)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def stat(client: httpx.AsyncClient, creds: Credentials, path: str) -> dict:
    """Read the metadata of one entry: size, mimetype, etag, fileid, permissions."""
    target = safe_path(path)
    response = await client.request(
        "PROPFIND",
        files_url(creds, target),
        headers={"Depth": "0", "Content-Type": "application/xml"},
        content=_stat_body(),
        auth=creds.auth(),
    )
    _check(response, target)

    entries = xml.parse_multistatus(response.content)
    if not entries:
        raise ToolError(
            message=f"Nextcloud returned no properties for {target}.",
            hint="Check the path in the Nextcloud web interface and try again.",
        )
    props = entries[0][1]
    resourcetype = props.get(f"{{{xml.DAV}}}resourcetype", "")
    return {
        "path": target,
        "size": int(props.get(f"{{{xml.DAV}}}getcontentlength") or 0),
        "content_type": props.get(f"{{{xml.DAV}}}getcontenttype", ""),
        "last_modified": props.get(f"{{{xml.DAV}}}getlastmodified", ""),
        "etag": props.get(f"{{{xml.DAV}}}getetag", ""),
        "fileid": props.get(f"{{{xml.OC}}}fileid", ""),
        "permissions": props.get(f"{{{xml.OC}}}permissions", ""),
        "is_collection": f"{{{xml.DAV}}}collection" in resourcetype,
    }


async def get_range(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    offset: int = 0,
    limit: int | None = None,
) -> bytes:
    """GET a file, optionally only the byte window ``[offset, offset+limit)``.

    A server or proxy may ignore the Range header and answer 200 with the whole body.
    In that case the window is cut out locally: returning the full body would flood the
    context window and make the caller's ``truncated``/``next_offset`` bookkeeping lie
    about the slice it asked for (WR-05).
    """
    target = safe_path(path)
    headers: dict[str, str] = {}
    if offset > 0 or limit is not None:
        end = "" if limit is None else str(offset + limit - 1)
        headers["Range"] = f"bytes={offset}-{end}"

    # Bound memory even when a proxy ignores Range. Discard the prefix and stop reading
    # once the requested window has arrived rather than buffering the complete file.
    headers["Accept-Encoding"] = "identity"
    async with client.stream(
        "GET", files_url(creds, target), headers=headers, auth=creds.auth()
    ) as response:
        _check(response, target)
        content_range = response.headers.get("Content-Range")
        if response.status_code == 206 and content_range:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range)
            if (
                match is None
                or int(match[1]) != offset
                or int(match[2]) < offset
                or (limit is not None and int(match[2]) >= offset + limit)
            ):
                raise ToolError(
                    message="Nextcloud returned a different byte range than requested.",
                    hint="Retry the same offset; check the proxy if this repeats.",
                )
        skip = offset if response.status_code == 200 else 0
        result = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
            if skip:
                consumed = min(skip, len(chunk))
                skip -= consumed
                chunk = chunk[consumed:]
            remaining = None if limit is None else limit - len(result)
            result.extend(chunk if remaining is None else chunk[:remaining])
            if limit is not None and len(result) >= limit:
                break
        return bytes(result)


def search_scope(creds: Credentials, folder: str = "/") -> str:
    """Return the search scope: the configured sandbox, or one folder below it.

    The scope is never built from a parameter alone. The user segment comes from the auth
    channel and the folder part runs through :func:`safe_path` first, so a search cannot
    reach into another account or outside ``NC_MCP_FILES_ROOT`` (threat T-01-32).

    ``creds.user`` is quoted like everywhere else in this package (WR-10). This was the
    single place that wrote it into a path unquoted, which was harmless while the value
    came from the environment and stopped being harmless in the ExApp mode, where it comes
    out of ``AUTHORIZATION-APP-API``: a slash or a dot segment in the user id would have
    produced a scope outside the caller's own home. Nextcloud forbids a slash in a user
    id, so the chain hung on a promise of a foreign component; a space, which Nextcloud
    does allow, already produced two different spellings of the same path in one request.

    The XML text around it stays unescaped on purpose: the verified example in the
    Nextcloud documentation writes the plain path, and lxml escapes whatever XML needs.
    """
    target = safe_path(folder)
    suffix = "" if target == "/" else target
    return f"/files/{quote(creds.user, safe='')}{suffix}"


def build_search_body(
    scope: str,
    term: str,
    limit: int,
    props: Sequence[str] = _SEARCH_PROPS,
) -> bytes:
    """Build the basicsearch body of a name search; with lxml, never with a string.

    Two things in here are not cosmetic. The term becomes element *text*, so an ampersand
    or an angle bracket in a model generated query is escaped by lxml instead of closing a
    tag (threat T-01-30). And the limit is always written: without it Nextcloud silently
    caps at 100 results, which would make a truncated answer indistinguishable from a
    complete one.

    The query tree stays flat, one comparison, no matter how long the term is. Nextcloud
    refuses a query with more than 100 operators, and a tree built from user input is the
    only way to get near that number.
    """
    needle = (term or "").strip()
    if not needle:
        raise ToolError(message="The search term is empty.", hint=_TERM_HINT)
    if limit < 1:
        raise ToolError(
            message=f"The result limit must be at least 1 (got {limit}).",
            hint="Leave the limit out to use the default.",
        )

    root = etree.Element(
        f"{{{xml.DAV}}}searchrequest",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    basic = etree.SubElement(root, f"{{{xml.DAV}}}basicsearch")

    select = etree.SubElement(basic, f"{{{xml.DAV}}}select")
    prop = etree.SubElement(select, f"{{{xml.DAV}}}prop")
    for name in props:
        etree.SubElement(prop, name)

    from_element = etree.SubElement(basic, f"{{{xml.DAV}}}from")
    scope_element = etree.SubElement(from_element, f"{{{xml.DAV}}}scope")
    href = etree.SubElement(scope_element, f"{{{xml.DAV}}}href")
    href.text = scope
    depth = etree.SubElement(scope_element, f"{{{xml.DAV}}}depth")
    depth.text = "infinity"

    where = etree.SubElement(basic, f"{{{xml.DAV}}}where")
    like = etree.SubElement(where, f"{{{xml.DAV}}}like")
    like_prop = etree.SubElement(like, f"{{{xml.DAV}}}prop")
    etree.SubElement(like_prop, f"{{{xml.DAV}}}displayname")
    literal = etree.SubElement(like, f"{{{xml.DAV}}}literal")
    # The percent signs are the wildcards of the search itself. A term that contains one
    # widens the match; it cannot leave the comparison, because Nextcloud binds the
    # literal as a query parameter.
    literal.text = f"%{needle}%"

    etree.SubElement(basic, f"{{{xml.DAV}}}orderby")

    limit_element = etree.SubElement(basic, f"{{{xml.DAV}}}limit")
    nresults = etree.SubElement(limit_element, f"{{{xml.DAV}}}nresults")
    nresults.text = str(limit)

    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def build_fileid_body(scope: str, fileid: str, props: Sequence[str] = _SEARCH_PROPS) -> bytes:
    """Build the basicsearch body that turns a file id back into a path.

    ``oc:fileid`` is a queryable property of the Nextcloud search backend, verified against
    a running Nextcloud 34: one SEARCH answers what a recursive PROPFIND would need a walk
    of the whole home directory for.

    The id becomes element text, so lxml escapes it, and the caller has already refused
    anything that is not a number. Two guards for one value is cheap here: this is the one
    lookup that takes an identifier straight from a model.
    """
    number = (fileid or "").strip()
    if not _DIGITS.fullmatch(number):
        raise ToolError(
            message=f"{fileid!r} is not a numeric Nextcloud file id.",
            hint="Use an id from a search tool, for example file:4711.",
        )

    root = etree.Element(
        f"{{{xml.DAV}}}searchrequest",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    basic = etree.SubElement(root, f"{{{xml.DAV}}}basicsearch")

    select = etree.SubElement(basic, f"{{{xml.DAV}}}select")
    prop = etree.SubElement(select, f"{{{xml.DAV}}}prop")
    for name in props:
        etree.SubElement(prop, name)

    from_element = etree.SubElement(basic, f"{{{xml.DAV}}}from")
    scope_element = etree.SubElement(from_element, f"{{{xml.DAV}}}scope")
    href = etree.SubElement(scope_element, f"{{{xml.DAV}}}href")
    href.text = scope
    depth = etree.SubElement(scope_element, f"{{{xml.DAV}}}depth")
    depth.text = "infinity"

    where = etree.SubElement(basic, f"{{{xml.DAV}}}where")
    equals = etree.SubElement(where, f"{{{xml.DAV}}}eq")
    eq_prop = etree.SubElement(equals, f"{{{xml.DAV}}}prop")
    etree.SubElement(eq_prop, f"{{{xml.OC}}}fileid")
    literal = etree.SubElement(equals, f"{{{xml.DAV}}}literal")
    literal.text = number

    etree.SubElement(basic, f"{{{xml.DAV}}}orderby")

    limit_element = etree.SubElement(basic, f"{{{xml.DAV}}}limit")
    nresults = etree.SubElement(limit_element, f"{{{xml.DAV}}}nresults")
    nresults.text = "1"

    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def find_by_fileid(
    client: httpx.AsyncClient,
    creds: Credentials,
    fileid: str,
) -> dict[str, Any] | None:
    """Return the entry of one file id inside the user's own home, or ``None``.

    ``None`` and not an exception: a file id that belongs to no file is an ordinary
    outcome (the file was deleted, or it lives in a share this account lost), and the
    caller words that better than this layer could.

    The scope is the user's own home, so an id from another account resolves to nothing
    here even before Nextcloud applies its own permission check.
    """
    response = await client.request(
        "SEARCH",
        f"{creds.base_url}{DAV_ROOT_PATH}",
        headers={"Content-Type": "text/xml"},
        content=build_fileid_body(search_scope(creds), fileid),
        auth=creds.auth(),
    )
    _check(response, f"the file with id {fileid}")
    entries = parse_entries(response.content, creds)
    return entries[0] if entries else None


def _list_body() -> bytes:
    """Build the PROPFIND body of a folder listing; with lxml, never with a string."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in _LIST_PROPS:
        etree.SubElement(prop, name)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def search(
    client: httpx.AsyncClient,
    creds: Credentials,
    scope: str,
    term: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Search names below ``scope`` and return the stable entry shape, one request.

    ``text/xml`` and not ``application/xml``: that is the content type the Nextcloud
    documentation uses for SEARCH, and the search backend is the pickier of the two paths.
    """
    response = await client.request(
        "SEARCH",
        f"{creds.base_url}{DAV_ROOT_PATH}",
        headers={"Content-Type": "text/xml"},
        content=build_search_body(scope, term, limit),
        auth=creds.auth(),
    )
    _check(response, scope)
    return parse_entries(response.content, creds)


async def propfind_children(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """List one folder with Depth 1 and return ``(the folder itself, its children)``.

    Depth 1 answers with the collection *and* its direct children, so the entry of the
    folder itself has to be dropped from the listing. It is matched by path rather than by
    position: the answer is a set of responses, and relying on the first one being the
    parent is an assumption the protocol does not make.

    The folder entry is returned instead of being thrown away, because the caller needs it
    to tell a file from a folder without a second request: Depth 1 on a file answers with
    that file alone, which would otherwise look like an empty folder.
    """
    target = safe_path(path)
    response = await client.request(
        "PROPFIND",
        files_url(creds, target),
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=_list_body(),
        auth=creds.auth(),
    )
    _check(response, target)

    entries = parse_entries(response.content, creds)
    itself = next((entry for entry in entries if entry["path"] == target), None)
    if itself is None:
        raise ToolError(
            message=f"Nextcloud returned no properties for {target}.",
            hint="Check the path in the Nextcloud web interface and try again.",
        )
    children = [entry for entry in entries if entry["path"] != target]
    return itself, children


def parse_entries(body: str | bytes, creds: Credentials) -> list[dict[str, Any]]:
    """Map a Multi-Status onto file entries, dropping everything outside the user's home.

    A href that does not sit below this user's files directory is not an answer to any
    question this client asks, so it is skipped instead of turned into a path that would
    later be sent back to Nextcloud.
    """
    home = f"{urlsplit(creds.base_url).path.rstrip('/')}{DAV_FILES_PREFIX}{creds.user}"
    entries: list[dict[str, Any]] = []
    for href, props in xml.parse_multistatus(body):
        path = _home_path_of(href, home)
        if path is None or not in_files_root(path):
            continue
        entries.append(_entry(path, props))
    return entries


def in_files_root(path: str) -> bool:
    """Check a returned absolute path without remapping it into the virtual root."""
    if "\\" in path or any(ord(char) < 32 or ord(char) == 127 for char in path):
        return False
    if any(part in (".", "..") for part in path.split("/")):
        return False
    root = config.files_root()
    return root == "/" or path == root or path.startswith(root + "/")


def _home_path_of(href: str, home: str) -> str | None:
    """Return the path inside the user's home, or ``None`` if the href is somewhere else."""
    raw = unquote(urlsplit(href).path)
    if not raw.startswith(home):
        return None
    rest = raw[len(home) :]
    if rest and not rest.startswith("/"):
        # "alicexyz" starts with "alice" but is a different account.
        return None
    return rest.rstrip("/") or "/"


def _entry(path: str, props: dict[str, str]) -> dict[str, Any]:
    """One stable dict per file or folder. Missing properties become empty, never None."""
    resourcetype = props.get(f"{{{xml.DAV}}}resourcetype", "")
    raw_size = props.get(f"{{{xml.DAV}}}getcontentlength") or props.get(f"{{{xml.OC}}}size") or ""
    return {
        "path": path,
        "name": props.get(f"{{{xml.DAV}}}displayname") or path.rsplit("/", 1)[-1] or "/",
        "is_collection": f"{{{xml.DAV}}}collection" in resourcetype,
        "size": int(raw_size) if raw_size.isdigit() else 0,
        "content_type": props.get(f"{{{xml.DAV}}}getcontenttype", ""),
        "last_modified": props.get(f"{{{xml.DAV}}}getlastmodified", ""),
        "fileid": props.get(f"{{{xml.OC}}}fileid", ""),
        "permissions": props.get(f"{{{xml.OC}}}permissions", ""),
    }


async def put_new_file(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    data: bytes,
    content_type: str,
) -> dict:
    """PUT a file that must not exist yet and return path, etag and ``created``.

    ``X-NC-WebDAV-AutoMkcol`` is deliberately not set: creating a missing parent folder is
    a second write that is not part of the tool contract, and a silent one at that.
    """
    target = safe_path(path)
    response = await client.put(
        files_url(creds, target),
        content=data,
        headers={"If-None-Match": "*", "Content-Type": content_type},
        auth=creds.auth(),
    )
    _check_write(response, target)
    return {
        "path": target,
        "etag": response.headers.get("etag", ""),
        "created": True,
    }


def uploads_url(creds: Credentials, upload_id: str, part: str | None = None, *, path: str) -> str:
    """Isolate connector uploads by sandbox and destination, including on retries.

    Caller-controlled ids never name a browser's existing temporary upload directory.
    Changing the destination or configured root selects a different staging directory.
    """
    user = quote(creds.user, safe="")
    identity = "\x00".join((config.files_root(), safe_path(path), upload_id))
    folder = "nc-mcp-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    suffix = "" if part is None else f"/{quote(part, safe='')}"
    return f"{creds.base_url}{DAV_UPLOADS_PREFIX}{user}/{folder}{suffix}"


async def start_chunked_upload(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    upload_id: str,
) -> None:
    """Create the temporary folder used by Nextcloud's chunk-upload protocol."""
    target = safe_path(path)
    response = await client.request(
        "MKCOL",
        uploads_url(creds, upload_id, path=target),
        headers={"Destination": files_url(creds, target)},
        auth=creds.auth(),
    )
    if response.status_code == 405:
        # A retry after an uncertain first response may find the folder already present. The
        # upload id is random or caller-owned, and all actual writes remain create-only.
        return
    _check_chunk_response(response, target)


async def put_upload_chunk(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    upload_id: str,
    chunk_index: int,
    data: bytes,
    total_size: int,
    content_type: str,
) -> None:
    """Store one chunk in Nextcloud's temporary upload folder."""
    target = safe_path(path)
    response = await client.put(
        uploads_url(creds, upload_id, f"{chunk_index:05d}", path=target),
        content=data,
        headers={
            "Destination": files_url(creds, target),
            "OC-Total-Length": str(total_size),
            "Content-Type": content_type,
        },
        auth=creds.auth(),
    )
    _check_chunk_response(response, target)


async def finish_chunked_upload(
    client: httpx.AsyncClient,
    creds: Credentials,
    path: str,
    upload_id: str,
    total_size: int,
) -> dict:
    """Assemble the temporary chunks into a new file without allowing replacement."""
    target = safe_path(path)
    response = await client.request(
        "MOVE",
        f"{uploads_url(creds, upload_id, path=target)}/.file",
        headers={
            "Destination": files_url(creds, target),
            "OC-Total-Length": str(total_size),
            "Overwrite": "F",
        },
        auth=creds.auth(),
    )
    # As with a direct PUT, only 201 proves that this was a new destination. A 204
    # means the server ignored Overwrite: F and must not be reported as a safe create.
    if response.status_code in (200, 204):
        _check_write(response, target)
    _check_chunk_response(response, target)
    return {
        "path": target,
        "etag": response.headers.get("etag", ""),
        "created": True,
    }


def _check_chunk_response(response: httpx.Response, path: str) -> None:
    """Translate a chunk request response while preserving create-only semantics."""
    status = response.status_code
    if status in (200, 201, 204):
        return
    if status == 412:
        raise ConflictError(
            message=f"A file already exists at {path}.",
            hint="This server never overwrites files. Choose a different name.",
        )
    if status == 403:
        raise ToolError(
            message=f"No permission to write to {path}.",
            hint="Check the share permissions of the target folder in Nextcloud.",
            reason=REASON_PERMISSION_DENIED,
        )
    if status in (404, 409):
        parent = dirname(path) or "/"
        raise ToolError(
            message=f"The parent folder {parent} of {path} does not exist.",
            hint="Create the folder in Nextcloud first, or upload into a folder that exists.",
            reason=REASON_UNKNOWN_ID,
        )
    if status == 413:
        raise ToolError(
            message=f"Nextcloud refused the upload of {path} as too large.",
            hint="Upload smaller chunks or check the Nextcloud server's upload limits.",
        )
    if status == 423:
        raise ToolError(
            message=f"{path} is locked in Nextcloud.",
            hint="Wait until the other client releases the lock, or choose another name.",
        )
    if status == 507:
        raise ToolError(
            message=f"Not enough space in Nextcloud for {path}.",
            hint="Free up quota in Nextcloud and try again.",
        )
    _check(response, path)
    raise ToolError(
        message=(
            f"Nextcloud answered the chunk upload of {path} with an unexpected status {status}."
        ),
        hint="Check the Nextcloud log for that request; the file was not created.",
    )


def _check_write(response: httpx.Response, path: str) -> None:
    """Translate the answer to a create-only PUT. 412 is the expected refusal, not a bug."""
    status = response.status_code
    if status == 201:
        return
    if status in (200, 204):
        # sabre answers 204 when a PUT *replaced* an existing file. Reaching this line means
        # the instance ignored the precondition, so the no-overwrite promise does not hold
        # there. Say so loudly instead of reporting a successful create.
        raise ToolError(
            message=(
                f"Nextcloud reports that the upload replaced an existing file at {path} "
                f"(status {status})."
            ),
            hint=(
                "This server sends If-None-Match: * and expects a refusal instead. Report "
                "this instance: it does not honour the precondition."
            ),
        )
    if status == 412:
        raise ConflictError(
            message=f"A file already exists at {path}.",
            hint="This server never overwrites files. Choose a different name.",
        )
    if status == 403:
        raise ToolError(
            message=f"No permission to write to {path}.",
            hint="Check the share permissions of the target folder in Nextcloud.",
            # Why the identifier sits at the status branches only: see the docstring of
            # ``_status_error`` in ``ocs.py`` (D-17).
            reason=REASON_PERMISSION_DENIED,
        )
    if status in (404, 409):
        parent = dirname(path) or "/"
        raise ToolError(
            message=f"The parent folder {parent} of {path} does not exist.",
            hint="Create the folder in Nextcloud first, or upload into a folder that exists.",
            reason=REASON_UNKNOWN_ID,
        )
    if status == 405:
        raise ToolError(
            message=f"{path} cannot be written to; there is already a folder at that path.",
            hint="Choose a file name that is free, for example inside that folder.",
        )
    if status == 413:
        raise ToolError(
            message=f"Nextcloud refused the upload of {path} as too large.",
            hint="Split the content into smaller files.",
        )
    if status == 423:
        raise ToolError(
            message=f"{path} is locked in Nextcloud.",
            hint="Wait until the other client releases the lock, or choose another name.",
        )
    if status == 507:
        raise ToolError(
            message=f"Not enough space in Nextcloud for {path}.",
            hint="Free up quota in Nextcloud and try again.",
        )
    _check(response, path)
    raise ToolError(
        message=f"Nextcloud answered the upload of {path} with an unexpected status {status}.",
        hint="Check the Nextcloud log for that request; the file was probably not created.",
    )


def _check(response: httpx.Response, path: str) -> None:
    """Translate a Nextcloud status into message plus hint. No retry, ever."""
    status = response.status_code
    if status in (200, 206, 207):
        return
    if 300 <= status < 400:
        raise ToolError(
            message=f"Nextcloud answered the request for {path} with a redirect ({status}).",
            hint=config.REDIRECT_HINT,
        )
    if status == 401:
        raise ToolError(
            message="Nextcloud rejected the app password.",
            hint=(
                "Generate a new app password in Nextcloud under Settings, Security, "
                "Devices and sessions, then restart the MCP server."
            ),
        )
    if status == 403:
        raise ToolError(
            message=f"No permission to read {path}.",
            hint="Ask the owner of the share for read permission in Nextcloud.",
            reason=REASON_PERMISSION_DENIED,
        )
    if status == 404:
        raise ToolError(
            message=f"File not found: {path}.",
            hint="List the parent folder first to get the exact spelling of the path.",
            reason=REASON_UNKNOWN_ID,
        )
    if status == 416:
        raise ToolError(
            message=f"The requested byte range of {path} is not available.",
            hint="Read the file again from offset 0 and follow next_offset.",
        )
    if status == 429:
        raise ToolError(
            message="Nextcloud is rate limiting this server.",
            hint="Wait about a minute before the next call; do not repeat it immediately.",
        )
    if status >= 500:
        raise ToolError(
            message=f"Nextcloud reported a server error ({status}) for {path}.",
            hint="This is a problem on the Nextcloud side. Retry later or check its log.",
        )
    raise ToolError(
        message=f"Nextcloud answered with an unexpected status {status} for {path}.",
        hint="Retry once; if it persists, check the Nextcloud log for that request.",
    )

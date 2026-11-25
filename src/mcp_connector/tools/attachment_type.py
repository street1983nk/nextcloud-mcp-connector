"""The type of a ChatGPT attachment, decided by its bytes, for ``files_update``.

``files_update`` replaces an existing file with an attachment. The type that matters is the
one of the existing file, and what decides whether the attachment fits it is the content of
the attachment: the type an attachment declares is a claim of the caller (a generic
``application/octet-stream`` is common) and is not read here.

The expected type comes from the existing file: its ``getcontenttype`` from WebDAV, and for a
generic one its extension. The bytes must then carry the signature of that family:

- ``PK\\x03\\x04`` for OOXML (docx, xlsx, pptx) and ODF (odt, ods, odp, odg). A ZIP of the
  wrong kind passes the signature, so the archive is checked as well. Its end-of-directory
  record is read first and an archive with more than ``MAX_ZIP_ENTRIES`` entries or a central
  directory above ``MAX_CENTRAL_DIRECTORY`` bytes is refused before ``zipfile`` opens it. An
  OOXML archive must hold the main part of the expected type (``word/document.xml``,
  ``xl/workbook.xml``, ``ppt/presentation.xml``) and say so in ``[Content_Types].xml``, with
  the content type of a document, workbook or presentation (not a template, not a macro
  type). An ODF archive must have ``mimetype`` as its first member, stored without
  compression, holding exactly the expected type.
- ``%PDF-`` for PDF and the signatures of PNG, JPEG, GIF and WebP. These are compared on the
  first bytes only; the rest of the file is not parsed.
- UTF-8 without a NUL byte for the text types ``files_update`` already accepts as ``content``,
  and not starting with the signature of a binary format, so an ASCII-only PDF is no text.

The older Word, Excel and PowerPoint files (doc, xls, ppt) share one container signature and
cannot be told apart by their first bytes, so they are not replaceable. An existing type
outside the list has no signature to compare with, and the replacement is refused. Only the
standard library is used; the functions are synchronous and read a seekable binary file, so
the caller runs them in a thread.
"""

import codecs
import posixpath
import struct
import zipfile
from collections.abc import Callable
from typing import IO, Any
from xml.parsers import expat

_ZIP = b"PK\x03\x04"
_READ_BLOCK = 1024 * 1024

#: Limits of an archive that is opened. A real docx, xlsx or pptx has a few hundred entries
#: and a central directory of some tens of KiB; ``zipfile`` builds one object per entry
#: before anything can be checked, so the directory is walked and counted first.
MAX_ZIP_ENTRIES = 10_000
MAX_CENTRAL_DIRECTORY = 16 * 1024 * 1024
#: The largest XML part that is read whole (``[Content_Types].xml``, ``manifest.xml``). A
#: types list of some 140 bytes per entry for ``MAX_ZIP_ENTRIES`` entries fits, and a real
#: workbook with thousands of sheets has a list of about 1 MiB.
_MAX_XML_PART = 4 * 1024 * 1024
#: How much of the main part of an OOXML file is read to find its root element.
_MAX_ROOT_SCAN = 64 * 1024

_EOCD = b"PK\x05\x06"
_EOCD_SIZE = 22
_EOCD_SEARCH = _EOCD_SIZE + 0xFFFF  # the record plus the longest comment
_ZIP64_LOCATOR = b"PK\x06\x07"
_ZIP64_LOCATOR_SIZE = 20
_CENTRAL_HEADER = b"PK\x01\x02"
_CENTRAL_HEADER_SIZE = 46
_SENTINEL_16 = 0xFFFF
_SENTINEL_32 = 0xFFFFFFFF

#: The start of a binary format. A text file does not begin like this, and several of them
#: (PDF, GIF, ZIP) are valid UTF-8 for their first bytes.
_BINARY_SIGNATURES = (
    b"%PDF-",
    _ZIP,
    b"PK\x05\x06",
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
)

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

#: The marker member of each OOXML type.
_OOXML_MARKERS: dict[str, str] = {
    _DOCX: "word/document.xml",
    _XLSX: "xl/workbook.xml",
    _PPTX: "ppt/presentation.xml",
}

#: The content type the main part of each OOXML type has in ``[Content_Types].xml``. The
#: templates (``...template.main+xml``) and the macro types (``macroEnabled``) are others.
_OOXML_MAIN_TYPES: dict[str, str] = {
    _DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    _XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    _PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
}
_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_MANIFEST_NS = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"

#: The root element of the main part of each OOXML type, in the transitional namespace and
#: in the strict one.
_OOXML_ROOTS: dict[str, tuple[str, frozenset[str]]] = {
    _DOCX: (
        "document",
        frozenset(
            {
                "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                "http://purl.oclc.org/ooxml/wordprocessingml/main",
            }
        ),
    ),
    _XLSX: (
        "workbook",
        frozenset(
            {
                "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
                "http://purl.oclc.org/ooxml/spreadsheetml/main",
            }
        ),
    ),
    _PPTX: (
        "presentation",
        frozenset(
            {
                "http://schemas.openxmlformats.org/presentationml/2006/main",
                "http://purl.oclc.org/ooxml/presentationml/main",
            }
        ),
    ),
}

_ODF = frozenset(
    {
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.graphics",
    }
)

#: Types compared by a plain prefix of the file.
_PREFIXES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
}

#: The type name that stands for "UTF-8 text" in :func:`expected_type`.
TEXT = "text/plain"

#: Types a server reports when it does not know the file; the extension decides then.
_GENERIC = frozenset({"", "application/octet-stream", "binary/octet-stream"})

_BY_EXTENSION: dict[str, str] = {
    ".docx": _DOCX,
    ".xlsx": _XLSX,
    ".pptx": _PPTX,
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".odg": "application/vnd.oasis.opendocument.graphics",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    **dict.fromkeys(
        (".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".html"),
        TEXT,
    ),
}

#: What the error message names, so the sentence does not hold a long MIME type.
_LABELS: dict[str, str] = {
    _DOCX: "Word (docx)",
    _XLSX: "Excel (xlsx)",
    _PPTX: "PowerPoint (pptx)",
    "application/vnd.oasis.opendocument.text": "OpenDocument text (odt)",
    "application/vnd.oasis.opendocument.spreadsheet": "OpenDocument spreadsheet (ods)",
    "application/vnd.oasis.opendocument.presentation": "OpenDocument presentation (odp)",
    "application/vnd.oasis.opendocument.graphics": "OpenDocument drawing (odg)",
    "application/pdf": "PDF",
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/gif": "GIF",
    "image/webp": "WebP",
    TEXT: "UTF-8 text",
}

#: The sentence that tells a caller which existing files can be replaced.
SUPPORTED = (
    "Word, Excel and PowerPoint (docx, xlsx, pptx), OpenDocument (odt, ods, odp, odg), PDF, "
    "PNG, JPEG, GIF, WebP and UTF-8 text"
)


def _essence(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def expected_type(content_type: str, path: str, is_text: Callable[[str], bool]) -> str | None:
    """The type the attachment has to be, or None when the existing type has no signature.

    ``content_type`` is the one WebDAV reports for the existing file; a generic one falls
    back to the extension of ``path``. A text type (``is_text`` is the test ``files_update``
    applies to ``content``) expects UTF-8 text.
    """
    essence = _essence(content_type)
    if essence in _GENERIC:
        return _BY_EXTENSION.get(posixpath.splitext(path)[1].lower())
    if is_text(essence):
        return TEXT
    return essence if essence in _LABELS else None


def label(expected: str) -> str:
    """The short name of an expected type, for a message."""
    return _LABELS.get(expected, expected)


def mismatch(staged: IO[bytes], expected: str) -> str | None:
    """Why the bytes in ``staged`` are not of type ``expected``, or None when they are.

    The reason is a short phrase for the error message. The file is read from the start and
    left at an unspecified position.
    """
    staged.seek(0)
    if expected == TEXT:
        return _text_mismatch(staged)
    head = staged.read(16)
    if expected in _OOXML_MARKERS or expected in _ODF:
        if not head.startswith(_ZIP):
            return "do not start with a ZIP signature"
        return _zip_mismatch(staged, expected)
    if expected == "image/webp":
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return None
        return "do not start with a WebP signature"
    prefixes = _PREFIXES.get(expected)
    if prefixes is None:
        return "have no known signature"
    if head.startswith(prefixes):
        return None
    return f"do not start with a {label(expected)} signature"


def _starts_binary(block: bytes) -> bool:
    if block.startswith(_BINARY_SIGNATURES):
        return True
    return block[:4] == b"RIFF" and block[8:12] == b"WEBP"


def _text_mismatch(staged: IO[bytes]) -> str | None:
    decoder = codecs.getincrementaldecoder("utf-8")()
    first = True
    while True:
        block = staged.read(_READ_BLOCK)
        if first and _starts_binary(block):
            return "start with the signature of a binary file"
        first = False
        if b"\x00" in block:
            return "contain a NUL byte"
        try:
            decoder.decode(block, final=not block)
        except UnicodeDecodeError:
            return "are not valid UTF-8"
        if not block:
            return None


class _XmlRefused(Exception):
    """The XML is broken, or declares a DTD or an entity, which no document here needs."""


class _RootSeen(Exception):
    """Raised by the parser to stop at the first element."""


def _scan_xml(chunks: list[bytes], *, first_only: bool = False) -> list[tuple[str, dict[str, str]]]:
    """The start elements of an XML text, as ("namespace local", attributes) pairs.

    Parsed with expat from the standard library. A DOCTYPE or an entity declaration is
    refused by the parser itself, whatever the encoding of the text. With ``first_only`` the
    scan stops at the first element, which is what a root check needs.
    """
    elements: list[tuple[str, dict[str, str]]] = []

    def refuse(*_args: Any) -> None:
        raise _XmlRefused("DTD or entity")

    def start(name: str, attributes: dict[str, str]) -> None:
        elements.append((name, attributes))
        if first_only:
            raise _RootSeen

    parser = expat.ParserCreate(namespace_separator=" ")
    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    parser.StartElementHandler = start
    try:
        for chunk in chunks:
            parser.Parse(chunk, False)
        parser.Parse(b"", True)
    except _RootSeen:
        pass
    except expat.ExpatError as error:
        raise _XmlRefused(str(error)) from None
    return elements


def _read_xml(archive: zipfile.ZipFile, name: str) -> list[tuple[str, dict[str, str]]]:
    with archive.open(name) as member:
        raw = member.read(_MAX_XML_PART + 1)
    if len(raw) > _MAX_XML_PART:
        raise _XmlRefused("too large")
    return _scan_xml([raw])


def _zip_limit(staged: IO[bytes]) -> str | None:
    """Why the archive cannot be opened, or None.

    Only the end record and the headers of the central directory are read, and the entries
    are counted the way ``zipfile`` walks them (until ``size_cd`` is consumed), because the
    counters of the end record are not what ``zipfile`` uses. A ZIP64 archive is refused:
    a document below the size limit with at most ``MAX_ZIP_ENTRIES`` entries does not need
    it, and its second set of counters is one more place for a lie.
    """
    unreadable = "are not a readable ZIP archive"
    staged.seek(0, 2)
    size = staged.tell()
    tail_start = max(size - _EOCD_SEARCH, 0)
    staged.seek(tail_start)
    tail = staged.read(_EOCD_SEARCH)
    at = tail.rfind(_EOCD)
    if at < 0 or len(tail) - at < _EOCD_SIZE:
        return unreadable
    eocd_at = tail_start + at
    disk, cd_disk, disk_entries, entries, cd_size, cd_offset, _comment = struct.unpack(
        "<HHHHIIH", tail[at + 4 : at + _EOCD_SIZE]
    )
    locator_at = max(eocd_at - _ZIP64_LOCATOR_SIZE, 0)
    staged.seek(locator_at)
    locator = staged.read(eocd_at - locator_at)
    zip64 = "are a ZIP64 file, which a document of this size does not need"
    if locator.startswith(_ZIP64_LOCATOR):
        return zip64
    # Each field has its own sentinel: 65535 is an ordinary offset or size.
    if _SENTINEL_16 in (disk, cd_disk, disk_entries, entries):
        return zip64
    if _SENTINEL_32 in (cd_size, cd_offset):
        return zip64
    if cd_size > MAX_CENTRAL_DIRECTORY:
        return "are a ZIP archive too large to check"
    start = eocd_at - cd_size
    if start < 0:
        return unreadable
    staged.seek(start)
    walked = 0
    counted = 0
    while walked < cd_size:
        header = staged.read(_CENTRAL_HEADER_SIZE)
        if len(header) < _CENTRAL_HEADER_SIZE or not header.startswith(_CENTRAL_HEADER):
            return unreadable
        name, extra, comment = struct.unpack("<HHH", header[28:34])
        walked += _CENTRAL_HEADER_SIZE + name + extra + comment
        counted += 1
        if counted > MAX_ZIP_ENTRIES:
            return "are a ZIP archive too large to check"
        staged.seek(name + extra + comment, 1)
    if counted != disk_entries or counted != entries:
        return unreadable
    return None


def _zip_mismatch(staged: IO[bytes], expected: str) -> str | None:
    refused = _zip_limit(staged)
    if refused is not None:
        return refused
    staged.seek(0)
    try:
        with zipfile.ZipFile(staged) as archive:
            if expected in _ODF:
                return _odf_mismatch(archive, staged, expected)
            return _ooxml_mismatch(archive, expected)
    except (zipfile.BadZipFile, EOFError, OSError, ValueError, NotImplementedError, RuntimeError):
        return "are not a readable ZIP archive"


def _mimetype_is_first_and_plain(archive: zipfile.ZipFile, staged: IO[bytes]) -> bool:
    """Whether ``mimetype`` is the first member of the file, stored and without extra field."""
    members = archive.infolist()
    if not members or members[0].filename != "mimetype" or members[0].header_offset != 0:
        return False
    staged.seek(0)
    header = staged.read(30 + len(b"mimetype"))
    return (
        header.startswith(_ZIP)
        and struct.unpack("<H", header[8:10])[0] == zipfile.ZIP_STORED
        and struct.unpack("<HH", header[26:30]) == (len(b"mimetype"), 0)
        and header[30:] == b"mimetype"
    )


def _odf_mismatch(archive: zipfile.ZipFile, staged: IO[bytes], expected: str) -> str | None:
    names = set(archive.namelist())
    if "mimetype" not in names:
        return "are a ZIP archive without a mimetype member"
    if not _mimetype_is_first_and_plain(archive, staged):
        return (
            "are an OpenDocument file whose mimetype member is not the first one, "
            "stored and without extra field"
        )
    with archive.open("mimetype") as member:
        declared = member.read(len(expected) + 1)
    if declared != expected.encode("ascii"):
        return "are an OpenDocument file of another type"
    if "META-INF/manifest.xml" not in names:
        return "are an OpenDocument file without META-INF/manifest.xml"
    try:
        elements = _read_xml(archive, "META-INF/manifest.xml")
    except _XmlRefused:
        return "have an unreadable META-INF/manifest.xml"
    if not elements or elements[0][0] != f"{_MANIFEST_NS} manifest":
        return "have a META-INF/manifest.xml that is not an OpenDocument manifest"
    if not names & {"content.xml", "styles.xml"}:
        return "are an OpenDocument file without content.xml or styles.xml"
    for name, attributes in elements:
        if name != f"{_MANIFEST_NS} file-entry":
            continue
        path = attributes.get(f"{_MANIFEST_NS} full-path", attributes.get("full-path"))
        if path == "/":
            media = attributes.get(f"{_MANIFEST_NS} media-type", attributes.get("media-type"))
            if media == expected:
                return None
            break
    return "are an OpenDocument file whose manifest names another type"


def _ooxml_mismatch(archive: zipfile.ZipFile, expected: str) -> str | None:
    names = set(archive.namelist())
    marker = _OOXML_MARKERS[expected]
    if marker not in names or "[Content_Types].xml" not in names:
        return "are a ZIP archive of another type"
    others = {m for kind, m in _OOXML_MARKERS.items() if kind != expected}
    if names & others:
        return "are a ZIP archive that mixes Office types"
    try:
        elements = _read_xml(archive, "[Content_Types].xml")
    except _XmlRefused:
        return "have an unreadable [Content_Types].xml"
    if not elements or elements[0][0] != f"{_CONTENT_TYPES_NS} Types":
        return "have a [Content_Types].xml that is not an OPC types list"
    declared = False
    for name, attributes in elements:
        if name == f"{_CONTENT_TYPES_NS} Override" and attributes.get("PartName") == f"/{marker}":
            declared = attributes.get("ContentType") == _OOXML_MAIN_TYPES[expected]
            break
    if not declared:
        return "are a ZIP archive of another type"
    return _ooxml_root_mismatch(archive, marker, expected)


def _ooxml_root_mismatch(archive: zipfile.ZipFile, marker: str, expected: str) -> str | None:
    """Whether the main part is XML whose root element is the one of the expected type."""
    with archive.open(marker) as member:
        head = member.read(_MAX_ROOT_SCAN)
    chunks = [head[n : n + 4096] for n in range(0, len(head), 4096)]
    try:
        elements = _scan_xml(chunks, first_only=True)
    except _XmlRefused:
        elements = []
    local, namespaces = _OOXML_ROOTS[expected]
    if elements and elements[0][0] in {f"{ns} {local}" for ns in namespaces}:
        return None
    return f"have a {marker} that is not the XML of that type"

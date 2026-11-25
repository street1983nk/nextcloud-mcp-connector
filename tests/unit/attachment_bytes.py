"""Minimal files of the types ``files_update`` knows, made in the test and never committed.

A helper module of the tests, not a test: ``attachment_type`` decides by bytes, so the tests
need bytes of the right and of the wrong kind. Archives are made with ``zipfile``: an OOXML one
holds the ``[Content_Types].xml`` that names its main part and the part itself, an
OpenDocument one holds ``mimetype`` first and stored, as the format asks.
"""

import io
import zipfile

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
ODT = "application/vnd.oasis.opendocument.text"
ODS = "application/vnd.oasis.opendocument.spreadsheet"
ODP = "application/vnd.oasis.opendocument.presentation"

_OOXML_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_MAIN_DOCX = DOCX + ".main+xml"
_MAIN_XLSX = XLSX + ".main+xml"
_MAIN_PPTX = PPTX + ".main+xml"


def zip_bytes(
    members: dict[str, bytes | str],
    *,
    deflated: frozenset[str] = frozenset(),
    extras: dict[str, bytes] | None = None,
) -> bytes:
    """A ZIP archive of ``members`` in the order given, stored unless named in ``deflated``."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, data in members.items():
            kind = zipfile.ZIP_DEFLATED if name in deflated else zipfile.ZIP_STORED
            info = zipfile.ZipInfo(name)
            info.extra = (extras or {}).get(name, b"")
            archive.writestr(info, data, compress_type=kind)
    return buffer.getvalue()


def content_types(part: str, content_type: str) -> str:
    """A ``[Content_Types].xml`` that names ``part`` as ``content_type``."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_OOXML_NS}">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/{part}" ContentType="{content_type}"/>'
        "</Types>"
    )


def _ooxml(part: str, content_type: str, body: str | bytes) -> bytes:
    return zip_bytes(
        {
            "[Content_Types].xml": content_types(part, content_type),
            "_rels/.rels": "<Relationships/>",
            part: body,
        }
    )


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_NS_STRICT = "http://purl.oclc.org/ooxml/wordprocessingml/main"
MANIFEST_NS = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"


def word_body(text: str = "edited", namespace: str = WORD_NS) -> str:
    """The main part of a docx: a ``document`` root in ``namespace``."""
    return (
        f'<w:document xmlns:w="{namespace}">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )


def docx_bytes(text: str = "edited") -> bytes:
    return _ooxml("word/document.xml", _MAIN_DOCX, word_body(text))


def docx_with_main_part(body: str | bytes) -> bytes:
    """A docx whose types file is right and whose main part is ``body``."""
    return _ooxml("word/document.xml", _MAIN_DOCX, body)


def xlsx_bytes() -> bytes:
    return _ooxml(
        "xl/workbook.xml",
        _MAIN_XLSX,
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets/></workbook>',
    )


def pptx_bytes() -> bytes:
    return _ooxml(
        "ppt/presentation.xml",
        _MAIN_PPTX,
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
    )


def docx_marker_only_bytes() -> bytes:
    """The old test fixture: the marker member and an empty ``[Content_Types].xml``."""
    return zip_bytes({"[Content_Types].xml": "<Types/>", "word/document.xml": "<w:document/>"})


def docx_with_main_type(content_type: str) -> bytes:
    """A docx whose main part is declared as ``content_type`` (a template, a macro type)."""
    return _ooxml("word/document.xml", content_type, word_body())


def docm_bytes() -> bytes:
    """A macro-enabled Word file: the same parts, the macro content type."""
    return docx_with_main_type("application/vnd.ms-word.document.macroEnabled.main+xml")


def manifest_xml(media_type: str) -> str:
    """A ``META-INF/manifest.xml`` whose root file entry has ``media_type``."""
    return (
        f'<manifest:manifest xmlns:manifest="{MANIFEST_NS}" manifest:version="1.3">'
        f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{media_type}"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        "</manifest:manifest>"
    )


def odf_bytes(
    mimetype: str,
    *,
    deflated: bool = False,
    mimetype_first: bool = True,
    manifest: str | None = "",
    mimetype_extra: bytes = b"",
) -> bytes:
    """An OpenDocument file as the format asks: ``mimetype`` first, stored, without extra
    field, then a manifest naming the same type. ``manifest`` is the text of the manifest
    (None leaves it out, the default builds one for ``mimetype``)."""
    members: dict[str, bytes | str] = {"content.xml": "<office:document-content/>"}
    if manifest is not None:
        members["META-INF/manifest.xml"] = manifest or manifest_xml(mimetype)
    if mimetype_first:
        members = {"mimetype": mimetype, **members}
    else:
        members["mimetype"] = mimetype
    return zip_bytes(
        members,
        deflated=frozenset({"mimetype"}) if deflated else frozenset(),
        extras={"mimetype": mimetype_extra} if mimetype_extra else None,
    )


def plain_zip_bytes() -> bytes:
    """A valid ZIP of no document type at all."""
    return zip_bytes({"notes.txt": "hello", "data/list.csv": "a,b\n"})


def many_entries_zip_bytes(entries: int) -> bytes:
    """A real ZIP of ``entries`` empty members: a docx's marker first, then the rest."""
    members: dict[str, bytes | str] = {"word/document.xml": ""}
    members.update({f"f/{number}": "" for number in range(entries - 1)})
    return zip_bytes(members)


PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< >>\nendobj\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF_BYTES = b"GIF89a" + b"\x00" * 16
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16
TEXT_BYTES = "# Titel\nZeile mit Umlaut: äöü\n".encode()

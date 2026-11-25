"""The type of an attachment is decided by its bytes (``tools/attachment_type.py``).

One test per condition of the design of 0.10.0: the signature of the family the existing file
belongs to, and for a ZIP container the kind of the archive. The type the attachment declares
is not an input of these functions at all.
"""

import io
import re
import struct

import attachment_bytes as ab
import pytest

from mcp_connector.tools import attachment_type
from mcp_connector.tools.files import _is_text

_ODF_ORDER = (
    "are an OpenDocument file whose mimetype member is not the first one, "
    "stored and without extra field"
)


def _mismatch(data: bytes, expected: str) -> str | None:
    return attachment_type.mismatch(io.BytesIO(data), expected)


# --- the type to expect: from the existing file, then from its extension --------------------


@pytest.mark.parametrize(
    ("reported", "path", "expected"),
    [
        (ab.DOCX, "/a/report.docx", ab.DOCX),
        (ab.DOCX.upper(), "/a/report.docx", ab.DOCX),
        ("application/pdf; charset=binary", "/a/x.pdf", "application/pdf"),
        ("text/markdown", "/a/note.md", attachment_type.TEXT),
        ("application/json", "/a/data.json", attachment_type.TEXT),
        ("application/octet-stream", "/a/report.docx", ab.DOCX),
        ("", "/a/Sheet.XLSX", ab.XLSX),
        ("application/octet-stream", "/a/photo.jpeg", "image/jpeg"),
        ("application/octet-stream", "/a/notes.md", attachment_type.TEXT),
    ],
)
def test_the_expected_type_comes_from_the_existing_file(
    reported: str, path: str, expected: str
) -> None:
    assert attachment_type.expected_type(reported, path, _is_text) == expected


@pytest.mark.parametrize(
    ("reported", "path"),
    [
        ("application/zip", "/a/archive.zip"),
        ("application/x-sh", "/a/run.sh"),
        ("application/octet-stream", "/a/blob.bin"),
        ("application/octet-stream", "/a/no_extension"),
        ("", "/a/model.stl"),
        # A specific type that has no signature here is not rescued by the extension.
        ("application/vnd.ms-outlook", "/a/mail.docx"),
        # The older Office files share one signature, so they are not replaceable at all.
        ("application/msword", "/a/old.doc"),
        ("application/vnd.ms-excel", "/a/old.xls"),
        ("application/vnd.ms-powerpoint", "/a/old.ppt"),
        ("application/octet-stream", "/a/old.doc"),
        ("", "/a/old.xls"),
    ],
)
def test_an_existing_type_without_a_known_signature_has_no_expected_type(
    reported: str, path: str
) -> None:
    assert attachment_type.expected_type(reported, path, _is_text) is None


def test_the_supported_sentence_names_every_family() -> None:
    for word in ("docx", "xlsx", "pptx", "odt", "PDF", "PNG", "JPEG", "GIF", "WebP", "text"):
        assert word in attachment_type.SUPPORTED
    for old in ("doc", "xls", "ppt"):
        assert not re.search(rf"\b{old}\b", attachment_type.SUPPORTED)


# --- Office containers: the signature and then the kind of the archive ------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (ab.docx_bytes(), ab.DOCX),
        (ab.xlsx_bytes(), ab.XLSX),
        (ab.pptx_bytes(), ab.PPTX),
        (ab.odf_bytes(ab.ODT), ab.ODT),
        (ab.odf_bytes(ab.ODS), ab.ODS),
        (ab.odf_bytes(ab.ODP), ab.ODP),
    ],
)
def test_an_archive_of_the_expected_kind_passes(data: bytes, expected: str) -> None:
    assert _mismatch(data, expected) is None


def test_a_docx_over_a_docx_passes_whatever_the_attachment_declares() -> None:
    """The declared type is not an input: the same bytes pass for the same existing file."""
    assert _mismatch(ab.docx_bytes("new text"), ab.DOCX) is None


def test_an_archive_with_only_the_marker_name_is_not_a_docx() -> None:
    """A member called word/document.xml is not enough: the types file has to say so."""
    assert _mismatch(ab.docx_marker_only_bytes(), ab.DOCX) == (
        "have a [Content_Types].xml that is not an OPC types list"
    )
    assert _mismatch(ab.zip_bytes({"word/document.xml": "<d/>"}), ab.DOCX) == (
        "are a ZIP archive of another type"
    )


@pytest.mark.parametrize(
    "content_type",
    [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
        "application/vnd.ms-word.document.macroEnabled.main+xml",
        "text/xml",
    ],
)
def test_a_main_part_declared_as_another_content_type_is_refused(content_type: str) -> None:
    data = ab.docx_with_main_type(content_type)

    assert _mismatch(data, ab.DOCX) == "are a ZIP archive of another type"


def test_a_macro_enabled_word_file_is_not_a_docx() -> None:
    assert _mismatch(ab.docm_bytes(), ab.DOCX) == "are a ZIP archive of another type"


def test_unreadable_types_xml_is_refused() -> None:
    broken = ab.zip_bytes({"[Content_Types].xml": "<Types", "word/document.xml": "<d/>"})
    bomb = ab.zip_bytes(
        {
            "[Content_Types].xml": '<!DOCTYPE t [<!ENTITY a "aaaa">]><Types>&a;</Types>',
            "word/document.xml": "<d/>",
        }
    )

    assert _mismatch(broken, ab.DOCX) == "have an unreadable [Content_Types].xml"
    assert _mismatch(bomb, ab.DOCX) == "have an unreadable [Content_Types].xml"


def test_an_oversized_types_xml_is_refused_without_being_read_whole() -> None:
    padding = " " * (4 * 1024 * 1024 + 1)
    big = ab.zip_bytes(
        {"[Content_Types].xml": f"<Types>{padding}</Types>", "word/document.xml": "<d/>"},
        deflated=frozenset({"[Content_Types].xml"}),
    )

    assert _mismatch(big, ab.DOCX) == "have an unreadable [Content_Types].xml"


def test_a_types_list_of_a_workbook_with_thousands_of_sheets_is_read() -> None:
    """A real workbook of 7,500 sheets has a types list of about 1 MiB: the limit is above."""
    types = ab.content_types("word/document.xml", ab.DOCX + ".main+xml")
    padding = "<!--" + "x" * (2 * 1024 * 1024) + "-->"
    data = ab.zip_bytes(
        {
            "[Content_Types].xml": types.replace("</Types>", padding + "</Types>"),
            "word/document.xml": ab.word_body(),
        },
        deflated=frozenset({"[Content_Types].xml"}),
    )

    assert _mismatch(data, ab.DOCX) is None


def test_an_xlsx_over_a_docx_is_refused() -> None:
    assert _mismatch(ab.xlsx_bytes(), ab.DOCX) == "are a ZIP archive of another type"


def test_a_pptx_over_a_xlsx_is_refused() -> None:
    assert _mismatch(ab.pptx_bytes(), ab.XLSX) == "are a ZIP archive of another type"


def test_any_zip_over_a_docx_is_refused() -> None:
    assert _mismatch(ab.plain_zip_bytes(), ab.DOCX) == "are a ZIP archive of another type"


def test_an_archive_that_holds_two_office_kinds_is_refused() -> None:
    mixed = ab.zip_bytes(
        {
            "[Content_Types].xml": ab.content_types("word/document.xml", ab.DOCX + ".main+xml"),
            "word/document.xml": "<d/>",
            "xl/workbook.xml": "<w/>",
        }
    )

    assert _mismatch(mixed, ab.DOCX) == "are a ZIP archive that mixes Office types"


def test_a_pdf_over_a_docx_is_refused() -> None:
    assert _mismatch(ab.PDF_BYTES, ab.DOCX) == "do not start with a ZIP signature"


def test_text_bytes_over_a_docx_are_refused() -> None:
    assert _mismatch(ab.TEXT_BYTES, ab.DOCX) == "do not start with a ZIP signature"


def test_a_truncated_archive_with_the_zip_signature_is_refused() -> None:
    cut = ab.docx_bytes()[:40]

    assert _mismatch(cut, ab.DOCX) == "are not a readable ZIP archive"


def test_an_odt_whose_mimetype_member_says_ods_is_refused() -> None:
    assert _mismatch(ab.odf_bytes(ab.ODS), ab.ODT) == "are an OpenDocument file of another type"


def test_an_odt_template_over_an_odt_is_refused() -> None:
    """The type is compared whole, not by its prefix: .ott starts like .odt."""
    template = ab.odf_bytes(ab.ODT + "-template")

    assert _mismatch(template, ab.ODT) == "are an OpenDocument file of another type"


def test_an_odf_archive_with_a_compressed_mimetype_is_refused() -> None:
    data = ab.odf_bytes(ab.ODT, deflated=True)

    assert _mismatch(data, ab.ODT) == (_ODF_ORDER)


def test_an_odf_archive_whose_mimetype_is_not_the_first_member_is_refused() -> None:
    data = ab.odf_bytes(ab.ODT, mimetype_first=False)

    assert _mismatch(data, ab.ODT) == (_ODF_ORDER)


def test_an_odf_archive_without_a_mimetype_member_is_refused() -> None:
    assert _mismatch(ab.plain_zip_bytes(), ab.ODT) == "are a ZIP archive without a mimetype member"


def test_an_ooxml_archive_over_an_odt_is_refused() -> None:
    assert _mismatch(ab.docx_bytes(), ab.ODT) == "are a ZIP archive without a mimetype member"


def test_an_odt_over_a_docx_is_refused() -> None:
    assert _mismatch(ab.odf_bytes(ab.ODT), ab.DOCX) == "are a ZIP archive of another type"


# --- the other signatures ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (ab.PDF_BYTES, "application/pdf"),
        (ab.PNG_BYTES, "image/png"),
        (ab.JPEG_BYTES, "image/jpeg"),
        (ab.GIF_BYTES, "image/gif"),
        (b"GIF87a" + b"\x00" * 8, "image/gif"),
        (ab.WEBP_BYTES, "image/webp"),
    ],
)
def test_the_signature_of_the_expected_family_passes(data: bytes, expected: str) -> None:
    assert _mismatch(data, expected) is None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (ab.docx_bytes(), "application/pdf"),
        (ab.PNG_BYTES, "image/jpeg"),
        (ab.JPEG_BYTES, "image/png"),
        (ab.PDF_BYTES, "image/gif"),
        (b"RIFF\x24\x00\x00\x00WAVEfmt ", "image/webp"),
        (b"", "application/pdf"),
    ],
)
def test_bytes_of_another_family_are_refused(data: bytes, expected: str) -> None:
    reason = _mismatch(data, expected)

    assert reason is not None
    assert reason.startswith("do not start with")


# --- text ----------------------------------------------------------------------------------


def test_utf_8_text_passes_for_a_text_file() -> None:
    assert _mismatch(ab.TEXT_BYTES, attachment_type.TEXT) is None


def test_an_empty_attachment_passes_for_a_text_file() -> None:
    assert _mismatch(b"", attachment_type.TEXT) is None


def test_text_that_is_not_utf_8_is_refused_for_a_text_file() -> None:
    latin_1 = "Grüße".encode("latin-1")

    assert _mismatch(latin_1, attachment_type.TEXT) == "are not valid UTF-8"


def test_text_with_a_nul_byte_is_refused_for_a_text_file() -> None:
    assert _mismatch(b"line one\x00line two", attachment_type.TEXT) == "contain a NUL byte"


def test_a_multibyte_character_cut_at_the_end_is_refused_for_a_text_file() -> None:
    assert _mismatch("ä".encode()[:1], attachment_type.TEXT) == "are not valid UTF-8"


def test_a_multibyte_character_across_the_read_block_passes() -> None:
    """The decoder keeps its state between blocks, so a character on a boundary is whole."""
    data = b"a" * (1024 * 1024 - 1) + "ä".encode() + b"tail"

    assert _mismatch(data, attachment_type.TEXT) is None


def test_a_binary_file_is_refused_for_a_text_file() -> None:
    assert _mismatch(ab.docx_bytes(), attachment_type.TEXT) is not None
    assert _mismatch(ab.PDF_BYTES + b"\x00", attachment_type.TEXT) is not None


@pytest.mark.parametrize(
    "data",
    [
        ab.PDF_BYTES,
        b"PK\x03\x04 plain ascii after",
        b"GIF89a plain ascii",
        b"GIF87a",
        ab.WEBP_BYTES,
    ],
    ids=["pdf", "zip", "gif89", "gif87", "webp"],
)
def test_a_binary_file_that_is_valid_ascii_is_refused_for_a_text_file(data: bytes) -> None:
    """A PDF made only of ASCII is valid UTF-8 without a NUL byte, and is not text."""
    data.decode("utf-8")

    assert _mismatch(data, attachment_type.TEXT) == "start with the signature of a binary file"


def test_text_that_only_mentions_a_signature_passes() -> None:
    assert _mismatch(b"The header %PDF- opens a PDF.\n", attachment_type.TEXT) is None


def test_a_nul_byte_after_the_first_read_block_is_refused_for_a_text_file() -> None:
    data = b"a" * (attachment_type._READ_BLOCK + 10) + b"\x00" + b"tail"

    assert _mismatch(data, attachment_type.TEXT) == "contain a NUL byte"


def test_latin_1_after_the_first_read_block_is_refused_for_a_text_file() -> None:
    data = b"a" * (attachment_type._READ_BLOCK + 10) + "Grüße".encode("latin-1")

    assert _mismatch(data, attachment_type.TEXT) == "are not valid UTF-8"


# --- the size of the archive is bounded before it is opened -------------------------------


def test_a_zip_with_too_many_entries_is_refused_without_being_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def not_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("zipfile.ZipFile must not run for an archive over the limit")

    data = ab.many_entries_zip_bytes(attachment_type.MAX_ZIP_ENTRIES + 1)
    monkeypatch.setattr(attachment_type.zipfile, "ZipFile", not_opened)

    assert _mismatch(data, ab.DOCX) == "are a ZIP archive too large to check"
    assert _mismatch(data, ab.ODT) == "are a ZIP archive too large to check"


def test_a_zip_with_the_largest_allowed_number_of_entries_is_opened() -> None:
    data = ab.many_entries_zip_bytes(attachment_type.MAX_ZIP_ENTRIES)

    assert _mismatch(data, ab.DOCX) == "are a ZIP archive of another type"


def _end_record(entries: int, directory: int) -> bytes:
    return b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, entries, entries, directory, 0, 0)


def test_a_declared_central_directory_over_the_limit_is_refused_without_being_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def not_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("zipfile.ZipFile must not run for an archive over the limit")

    monkeypatch.setattr(attachment_type.zipfile, "ZipFile", not_opened)
    data = b"PK\x03\x04" + b"\x00" * 26 + _end_record(3, attachment_type.MAX_CENTRAL_DIRECTORY + 1)

    assert _mismatch(data, ab.DOCX) == "are a ZIP archive too large to check"


def _zip64_locator_before(end_record: bytes) -> bytes:
    return b"PK\x06\x07" + struct.pack("<IQI", 0, 0, 1) + end_record


def test_a_zip64_locator_without_sentinels_is_refused_without_being_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``zipfile`` reads a ZIP64 record whenever a locator precedes the end record, so the
    counters of the ordinary record prove nothing."""
    data = ab.docx_bytes()
    eocd_at = data.rindex(b"PK\x05\x06")
    data = data[:eocd_at] + _zip64_locator_before(data[eocd_at:])

    def not_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("zipfile.ZipFile must not run")

    monkeypatch.setattr(attachment_type.zipfile, "ZipFile", not_opened)

    assert _mismatch(data, ab.DOCX) == (
        "are a ZIP64 file, which a document of this size does not need"
    )


_ZIP64_REFUSED = "are a ZIP64 file, which a document of this size does not need"


def _end_record_with(**fields: int) -> bytes:
    values = {
        "disk": 0,
        "cd_disk": 0,
        "disk_entries": 1,
        "entries": 1,
        "cd_size": 46,
        "cd_offset": 0,
    } | fields
    return b"PK\x05\x06" + struct.pack(
        "<HHHHIIH",
        values["disk"],
        values["cd_disk"],
        values["disk_entries"],
        values["entries"],
        values["cd_size"],
        values["cd_offset"],
        0,
    )


@pytest.mark.parametrize(
    "field", ["disk", "cd_disk", "disk_entries", "entries"], ids=lambda f: f"16-bit-{f}"
)
def test_the_16_bit_sentinel_is_refused_in_each_16_bit_field(field: str) -> None:
    data = b"PK\x03\x04" + b"\x00" * 26 + _end_record_with(**{field: 0xFFFF})

    assert _mismatch(data, ab.DOCX) == _ZIP64_REFUSED


@pytest.mark.parametrize("field", ["cd_size", "cd_offset"], ids=lambda f: f"32-bit-{f}")
def test_the_32_bit_sentinel_is_refused_in_each_32_bit_field(field: str) -> None:
    data = b"PK\x03\x04" + b"\x00" * 26 + _end_record_with(**{field: 0xFFFFFFFF})

    assert _mismatch(data, ab.DOCX) == _ZIP64_REFUSED


def _docx_with_pad(pad_size: int, pad_name: str = "pad") -> bytes:
    members: dict[str, bytes | str] = {pad_name: b"x" * pad_size}
    members.update(
        {
            "[Content_Types].xml": ab.content_types("word/document.xml", ab.DOCX + ".main+xml"),
            "word/document.xml": ab.word_body(),
        }
    )
    return ab.zip_bytes(members)


def _end_fields(data: bytes) -> tuple[int, int]:
    eocd_at = data.rindex(b"PK\x05\x06")
    cd_size, cd_offset = struct.unpack("<II", data[eocd_at + 12 : eocd_at + 20])
    return cd_size, cd_offset


def test_a_valid_zip_whose_central_directory_starts_at_offset_65535_is_accepted() -> None:
    """A python-docx file really has this: 65535 is an offset like any other."""
    _, offset = _end_fields(_docx_with_pad(0))
    data = _docx_with_pad(65535 - offset)

    assert _end_fields(data)[1] == 65535
    assert _mismatch(data, ab.DOCX) is None


def test_a_valid_zip_whose_central_directory_is_65535_bytes_long_is_accepted() -> None:
    size, _ = _end_fields(_docx_with_pad(0, "p"))
    name = "p" * (1 + 65535 - size)
    data = _docx_with_pad(0, name)

    assert _end_fields(data)[0] == 65535
    assert _mismatch(data, ab.DOCX) is None


def test_a_zip64_sentinel_in_the_end_record_is_refused() -> None:
    data = b"PK\x03\x04" + b"\x00" * 26 + _end_record(0xFFFF, 0xFFFFFFFF)

    assert _mismatch(data, ab.DOCX) == (
        "are a ZIP64 file, which a document of this size does not need"
    )


def test_an_end_record_that_undercounts_the_entries_is_refused_without_being_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counter of the end record is not what ``zipfile`` goes by: 10.001 real entries
    behind a counter of 1 are still counted."""
    data = ab.many_entries_zip_bytes(attachment_type.MAX_ZIP_ENTRIES + 1)
    eocd_at = data.rindex(b"PK\x05\x06")
    liar = data[: eocd_at + 8] + struct.pack("<HH", 1, 1) + data[eocd_at + 12 :]

    def not_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("zipfile.ZipFile must not run for an archive over the limit")

    monkeypatch.setattr(attachment_type.zipfile, "ZipFile", not_opened)

    assert _mismatch(liar, ab.DOCX) == "are a ZIP archive too large to check"


def test_an_end_record_whose_counters_do_not_match_the_directory_is_refused() -> None:
    data = ab.docx_bytes()
    eocd_at = data.rindex(b"PK\x05\x06")
    liar = data[: eocd_at + 8] + struct.pack("<HH", 1, 1) + data[eocd_at + 12 :]

    assert _mismatch(liar, ab.DOCX) == "are not a readable ZIP archive"


def test_a_central_directory_header_with_a_broken_signature_is_refused_without_being_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = ab.docx_bytes()
    start = data.rindex(b"PK\x01\x02")
    broken = data[:start] + b"PX\x01\x02" + data[start + 4 :]

    def not_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("zipfile.ZipFile must not run for a broken directory")

    monkeypatch.setattr(attachment_type.zipfile, "ZipFile", not_opened)

    assert _mismatch(broken, ab.DOCX) == "are not a readable ZIP archive"


# --- XML: the parser refuses a DTD, whatever the encoding; the roots are the right ones ----


def _docx_with_types(types: bytes) -> bytes:
    return ab.zip_bytes({"[Content_Types].xml": types, "word/document.xml": ab.word_body()})


def test_a_dtd_and_an_entity_in_utf_16_are_refused() -> None:
    text = (
        '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE t [<!ENTITY a "aaaa">]>'
        f'<Types xmlns="{ab._OOXML_NS}">&a;</Types>'
    )

    assert _mismatch(_docx_with_types(text.encode("utf-16")), ab.DOCX) == (
        "have an unreadable [Content_Types].xml"
    )


def test_a_dtd_without_an_entity_is_refused() -> None:
    data = _docx_with_types(f'<!DOCTYPE Types><Types xmlns="{ab._OOXML_NS}"/>'.encode())

    assert _mismatch(data, ab.DOCX) == "have an unreadable [Content_Types].xml"


def test_a_types_file_whose_root_is_not_types_is_refused() -> None:
    data = _docx_with_types(f'<Other xmlns="{ab._OOXML_NS}"/>'.encode())

    assert _mismatch(data, ab.DOCX) == "have a [Content_Types].xml that is not an OPC types list"


# --- the main part of an OOXML file is XML of its type -------------------------------------


def test_a_main_part_that_is_not_xml_is_refused() -> None:
    assert _mismatch(ab.docx_with_main_part(b"not XML"), ab.DOCX) == (
        "have a word/document.xml that is not the XML of that type"
    )


def test_a_main_part_with_the_root_of_another_type_is_refused() -> None:
    workbook = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'

    assert _mismatch(ab.docx_with_main_part(workbook), ab.DOCX) == (
        "have a word/document.xml that is not the XML of that type"
    )


def test_a_main_part_with_a_dtd_is_refused() -> None:
    body = f"<!DOCTYPE d [<!ENTITY a 'b'>]>{ab.word_body()}"

    assert _mismatch(ab.docx_with_main_part(body), ab.DOCX) == (
        "have a word/document.xml that is not the XML of that type"
    )


def test_a_main_part_whose_root_is_beyond_the_scan_limit_is_refused() -> None:
    body = "<!--" + "x" * (64 * 1024) + "-->" + ab.word_body()

    assert _mismatch(ab.docx_with_main_part(body), ab.DOCX) is not None


def test_a_main_part_in_the_strict_namespace_passes() -> None:
    body = ab.word_body(namespace=ab.WORD_NS_STRICT)

    assert _mismatch(ab.docx_with_main_part(body), ab.DOCX) is None


# --- ODF: a manifest of the same type, and mimetype physically first -----------------------


def test_an_odf_file_without_a_manifest_is_refused() -> None:
    data = ab.odf_bytes(ab.ODT, manifest=None)

    assert _mismatch(data, ab.ODT) == "are an OpenDocument file without META-INF/manifest.xml"


def test_an_odf_manifest_that_names_another_root_type_is_refused() -> None:
    data = ab.odf_bytes(ab.ODT, manifest=ab.manifest_xml(ab.ODS))

    assert _mismatch(data, ab.ODT) == "are an OpenDocument file whose manifest names another type"


def test_an_odf_manifest_without_a_root_entry_is_refused() -> None:
    manifest = ab.manifest_xml(ab.ODT).replace('full-path="/"', 'full-path="/x"')

    assert _mismatch(ab.odf_bytes(ab.ODT, manifest=manifest), ab.ODT) == (
        "are an OpenDocument file whose manifest names another type"
    )


def test_an_odf_manifest_whose_root_is_not_manifest_is_refused() -> None:
    inner = ab.manifest_xml(ab.ODT)
    wrapped = f"<not-manifest>{inner.split('?>')[-1]}</not-manifest>"

    assert _mismatch(ab.odf_bytes(ab.ODT, manifest=wrapped), ab.ODT) == (
        "have a META-INF/manifest.xml that is not an OpenDocument manifest"
    )


def test_an_odf_file_with_only_mimetype_and_a_manifest_is_refused() -> None:
    data = ab.zip_bytes({"mimetype": ab.ODT, "META-INF/manifest.xml": ab.manifest_xml(ab.ODT)})

    assert _mismatch(data, ab.ODT) == "are an OpenDocument file without content.xml or styles.xml"


def test_an_odf_file_with_styles_xml_instead_of_content_xml_passes() -> None:
    data = ab.zip_bytes(
        {
            "mimetype": ab.ODT,
            "META-INF/manifest.xml": ab.manifest_xml(ab.ODT),
            "styles.xml": "<office:document-styles/>",
        }
    )

    assert _mismatch(data, ab.ODT) is None


def test_an_odf_manifest_with_a_dtd_is_refused() -> None:
    manifest = "<!DOCTYPE m>" + ab.manifest_xml(ab.ODT)

    assert _mismatch(ab.odf_bytes(ab.ODT, manifest=manifest), ab.ODT) == (
        "have an unreadable META-INF/manifest.xml"
    )


def test_an_odf_mimetype_with_an_extra_field_is_refused() -> None:
    data = ab.odf_bytes(ab.ODT, mimetype_extra=b"\x99\x99\x00\x00")

    assert _mismatch(data, ab.ODT) == _ODF_ORDER

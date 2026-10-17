"""Word to Markdown.

Body order is kept. Headers, footers, footnotes, comments and images are not.
The library is imported inside the function so the package imports without the extra.

Two library shortcuts are avoided on purpose. ``row.cells`` repeats a cell once per grid
column it spans, so a crafted ``gridSpan`` turns one cell into 100000; the converter reads
the real ``w:tc`` elements instead. ``paragraph.style`` resolves the style again for every
paragraph; the converter looks each style id up in a map that it builds once.
"""

import io
import re
from collections.abc import Iterable
from typing import Any

from .limits import Output

__all__ = ["MAX_TABLE_COLS", "MAX_TABLE_ROWS", "to_markdown"]

MAX_TABLE_COLS = 256
MAX_TABLE_ROWS = 10000

_HEADING_RE = re.compile(r"^Heading (\d+)$")


def _heading_prefix(style_name: str) -> str:
    if style_name == "Title":
        return "#"
    match = _HEADING_RE.match(style_name)
    if match is None:
        return ""
    return "#" * min(int(match.group(1)), 6)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _table_lines(rows: Iterable[Iterable[str]]) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows):
        cells = [_cell(value) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
    return lines


def _table_lines_capped(table: Any) -> list[str]:
    """Pipe-table lines from the real cells, with a note for each cap that cut something."""
    from docx.table import _Cell

    rows: list[list[str]] = []
    rows_cut = cols_cut = False
    for index, tr in enumerate(table._tbl.tr_lst):
        if index >= MAX_TABLE_ROWS:
            rows_cut = True
            break
        cells = tr.tc_lst
        cols_cut = cols_cut or len(cells) > MAX_TABLE_COLS
        rows.append([_Cell(tc, table).text for tc in cells[:MAX_TABLE_COLS]])
    lines = _table_lines(rows)
    if rows_cut:
        lines.append(f"(more than {MAX_TABLE_ROWS} rows; the rest of the table is omitted)")
    if cols_cut:
        lines.append(f"(more than {MAX_TABLE_COLS} columns; the rest of each row is omitted)")
    return lines


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _paragraph_text(paragraph) -> str:
    parts: list[str] = []

    for child in paragraph.iterchildren():
        if child.tag == _W_NS + "r":
            runs = (child,)
        elif child.tag == _W_NS + "hyperlink":
            runs = child.iterchildren(_W_NS + "r")
        else:
            continue

        for run in runs:
            for item in run.iterchildren():
                if item.tag == _W_NS + "t":
                    parts.append(item.text or "")
                elif item.tag == _W_NS + "tab":
                    parts.append("\t")
                elif item.tag in (_W_NS + "br", _W_NS + "cr"):
                    parts.append("\n")
                elif item.tag == _W_NS + "noBreakHyphen":
                    parts.append("\u2011")
                elif item.tag == _W_NS + "softHyphen":
                    parts.append("\u00ad")

    return "".join(parts)


def to_markdown(data: bytes) -> str:
    import docx
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table

    document = docx.Document(io.BytesIO(data))
    style_names = {style.style_id: style.name or "" for style in document.styles}
    out = Output()
    style_prefixes: dict[str, str] = {}
    for block in document.element.body.iterchildren():
        if out.full:
            break
        if isinstance(block, CT_P):
            text = _paragraph_text(block).strip()
            if not text:
                continue
            p_pr = block.pPr
            style_id = p_pr.style if p_pr is not None else None
            prefix = ""
            if style_id:
                if style_id not in style_prefixes:
                    style = style_names.get(style_id, "")
                    style_prefixes[style_id] = _heading_prefix(style) or (
                        "- " if style.startswith("List") else ""
                    )
                prefix = style_prefixes[style_id]
            if prefix == "- ":
                out.add(f"- {text}")
            elif prefix:
                out.add(f"{prefix} {text}")
            else:
                out.add(text)

            out.add("")
        elif isinstance(block, CT_Tbl):
            out.extend(_table_lines_capped(Table(block, document._body)))
            out.add("")
    return out.text()

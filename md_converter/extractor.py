from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import fitz


class BlockType(Enum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


@dataclass
class Block:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    page_num: int
    font_size: float
    is_bold: bool
    is_italic: bool
    block_type: BlockType = BlockType.TEXT
    column: int = 0  # 0 = left/single, 1 = right (for 2-col layouts)


def extract_page_blocks(page: fitz.Page) -> list[Block]:
    """Extract text blocks from a page with font metadata and reading order."""
    page_width = page.rect.width
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    blocks: list[Block] = []

    for raw_block in raw.get("blocks", []):
        block_type_code = raw_block.get("type")

        if block_type_code == 1:  # image block
            blocks.append(Block(
                text=f"[Image on page {page.number + 1}]",
                bbox=tuple(raw_block["bbox"]),
                page_num=page.number,
                font_size=0,
                is_bold=False,
                is_italic=False,
                block_type=BlockType.IMAGE,
            ))
            continue

        if block_type_code != 0:  # skip non-text, non-image
            continue

        # Aggregate spans within this block
        lines_text: list[str] = []
        font_sizes: list[float] = []
        bold_count = 0
        italic_count = 0
        span_count = 0

        for line in raw_block.get("lines", []):
            line_parts: list[str] = []
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                line_parts.append(text)
                font_sizes.append(span.get("size", 12))
                flags = span.get("flags", 0)
                if flags & 16:   # bold bit
                    bold_count += 1
                if flags & 2:    # italic bit
                    italic_count += 1
                span_count += 1
            if line_parts:
                lines_text.append("".join(line_parts))

        if not lines_text:
            continue

        text = "\n".join(lines_text)
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12
        is_bold = bold_count > span_count / 2 if span_count else False
        is_italic = italic_count > span_count / 2 if span_count else False

        bbox = tuple(raw_block["bbox"])
        # Column detection: if block center x < 55% of page width → left col
        center_x = (bbox[0] + bbox[2]) / 2
        column = 0 if center_x < page_width * 0.55 else 1

        blocks.append(Block(
            text=text,
            bbox=bbox,
            page_num=page.number,
            font_size=round(avg_font_size, 1),
            is_bold=is_bold,
            is_italic=is_italic,
            column=column,
        ))

    # Sort by reading order: column first, then top-to-bottom
    blocks.sort(key=lambda b: (b.column, b.bbox[1]))
    return blocks


def extract_tables(page: fitz.Page) -> list[dict]:
    """Extract tables from page using PyMuPDF table finder."""
    tables = []
    try:
        tab_finder = page.find_tables()
        for tab in tab_finder.tables:
            rows = []
            for row in tab.extract():
                rows.append([cell or "" for cell in row])
            if rows:
                tables.append({
                    "bbox": tab.bbox,
                    "rows": rows,
                })
    except Exception:
        pass  # table detection not available or failed — caller handles
    return tables

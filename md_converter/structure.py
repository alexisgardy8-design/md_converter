from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from md_converter.extractor import Block, BlockType

_BULLET_RE = re.compile(r"^[\u00B7\u2022\u2023\u25E6\u2043\u2219•◦▪▸·\-\*]\s+")
_ORDERED_RE = re.compile(r"^(\d+|[a-zA-Z])[.)]\s+")
_NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s{1,3}\S")


class ElementType(Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM_UNORDERED = "list_item_unordered"
    LIST_ITEM_ORDERED = "list_item_ordered"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    IMAGE = "image"
    FOOTNOTE = "footnote"
    PAGE_BREAK = "page_break"


@dataclass
class Element:
    text: str
    element_type: ElementType
    level: int = 0          # heading level (1-6), list nesting level
    page_num: int = 0
    table_rows: list[list[str]] = field(default_factory=list)
    low_confidence: bool = False


def _is_heading_candidate(block: Block, body_size: float) -> bool:
    size_ratio = block.font_size / body_size if body_size else 1
    if size_ratio >= 1.2:
        return True
    if block.is_bold and size_ratio >= 1.0 and len(block.text.strip()) < 120:
        return True
    stripped = block.text.strip()
    if stripped.isupper() and 3 <= len(stripped) <= 80:
        return True
    if _NUMBERED_HEADING_RE.match(stripped):
        return True
    return False


def assign_heading_levels(blocks: list[Block]) -> list[Element]:
    """Assign heading levels based on relative font sizes."""
    sizes = [b.font_size for b in blocks if b.font_size > 0]
    if not sizes:
        return [
            Element(text=b.text, element_type=ElementType.PARAGRAPH, page_num=b.page_num)
            for b in blocks
        ]

    # Body size = most common rounded size; on tie, prefer smallest (body text is smallest frequent)
    from collections import Counter
    size_counter = Counter(round(s) for s in sizes)
    most_common_count = size_counter.most_common(1)[0][1]
    most_common_sizes = [s for s, c in size_counter.items() if c == most_common_count]
    body_size = min(most_common_sizes)

    # Collect distinct heading sizes > body (rounded)
    heading_sizes = sorted(
        {round(b.font_size) for b in blocks if _is_heading_candidate(b, body_size)},
        reverse=True,
    )
    size_to_level: dict[int, int] = {s: i + 1 for i, s in enumerate(heading_sizes[:6])}

    elements: list[Element] = []
    for block in blocks:
        if block.block_type == BlockType.IMAGE:
            elements.append(Element(
                text=block.text,
                element_type=ElementType.IMAGE,
                page_num=block.page_num,
            ))
            continue

        stripped = block.text.strip()
        if not stripped:
            continue

        if _is_heading_candidate(block, body_size):
            level = size_to_level.get(round(block.font_size), 3)
            elements.append(Element(
                text=stripped,
                element_type=ElementType.HEADING,
                level=level,
                page_num=block.page_num,
            ))
        else:
            elements.append(Element(
                text=stripped,
                element_type=ElementType.PARAGRAPH,
                page_num=block.page_num,
            ))

    return elements


def detect_list_items(blocks: list[Block]) -> list[Element]:
    """Convert blocks that look like list items into LIST_ITEM elements."""
    elements: list[Element] = []
    for block in blocks:
        stripped = block.text.strip()
        if _BULLET_RE.match(stripped):
            text = _BULLET_RE.sub("", stripped)
            elements.append(Element(
                text=text,
                element_type=ElementType.LIST_ITEM_UNORDERED,
                page_num=block.page_num,
            ))
        elif _ORDERED_RE.match(stripped):
            text = _ORDERED_RE.sub("", stripped)
            elements.append(Element(
                text=text,
                element_type=ElementType.LIST_ITEM_ORDERED,
                page_num=block.page_num,
            ))
        else:
            elements.append(Element(
                text=stripped,
                element_type=ElementType.PARAGRAPH,
                page_num=block.page_num,
            ))
    return elements


def table_to_element(table_dict: dict, page_num: int) -> Element:
    """Convert a raw table dict from extractor to a TABLE Element."""
    return Element(
        text="",
        element_type=ElementType.TABLE,
        page_num=page_num,
        table_rows=table_dict["rows"],
    )


def reconstruct_structure(
    pages_blocks: list[list[Block]],
    tables_per_page: list[list[dict]],
    include_page_breaks: bool = False,
) -> list[Element]:
    """Full structure reconstruction: headings, lists, tables, paragraphs."""
    all_blocks_flat = [b for page in pages_blocks for b in page]

    # First pass: heading level assignment
    elements_with_headings = assign_heading_levels(all_blocks_flat)

    # Second pass: list detection on paragraph elements
    elements: list[Element] = []
    for elem in elements_with_headings:
        if elem.element_type == ElementType.PARAGRAPH:
            stripped = elem.text.strip()
            if _BULLET_RE.match(stripped):
                elem.element_type = ElementType.LIST_ITEM_UNORDERED
                elem.text = _BULLET_RE.sub("", stripped)
            elif _ORDERED_RE.match(stripped):
                elem.element_type = ElementType.LIST_ITEM_ORDERED
                elem.text = _ORDERED_RE.sub("", stripped)
        elements.append(elem)

    # Build index: page_num → elements from that page
    page_elements: dict[int, list[Element]] = {}
    for elem in elements:
        page_elements.setdefault(elem.page_num, []).append(elem)

    # Append table elements per page
    for page_num, tables in enumerate(tables_per_page):
        for t in tables:
            table_elem = table_to_element(t, page_num)
            page_elements.setdefault(page_num, []).append(table_elem)

    # Flatten back in page order
    final: list[Element] = []
    total_pages = max(
        (max(page_elements.keys()) + 1) if page_elements else 0,
        len(tables_per_page),
    )
    for page_num in range(total_pages):
        final.extend(page_elements.get(page_num, []))
        if include_page_breaks and page_num < total_pages - 1:
            final.append(Element(
                text="",
                element_type=ElementType.PAGE_BREAK,
                page_num=page_num,
            ))

    return final

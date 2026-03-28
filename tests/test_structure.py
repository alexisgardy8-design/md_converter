from md_converter.extractor import Block, BlockType
from md_converter.structure import (
    assign_heading_levels,
    detect_list_items,
    Element,
    ElementType,
    reconstruct_structure,
)


def _block(text: str, size: float, bold: bool = False, y: float = 100, page: int = 0) -> Block:
    return Block(
        text=text,
        bbox=(72, y, 500, y + size),
        page_num=page,
        font_size=size,
        is_bold=bold,
        is_italic=False,
    )


def test_heading_level_assignment():
    blocks = [
        _block("Big Title", size=24, bold=True, y=50),
        _block("Subtitle", size=18, bold=True, y=100),
        _block("Regular paragraph text here.", size=12, y=150),
        _block("Section Header", size=16, bold=True, y=200),
    ]
    elements = assign_heading_levels(blocks)
    heading_elements = [e for e in elements if e.element_type == ElementType.HEADING]
    assert len(heading_elements) >= 2
    # Big Title should have a lower level number (h1) than Subtitle (h2)
    h1 = next(e for e in heading_elements if "Big Title" in e.text)
    h2 = next(e for e in heading_elements if "Subtitle" in e.text)
    assert h1.level < h2.level


def test_paragraph_detected():
    blocks = [_block("Just a paragraph of text.", size=12, y=100)]
    elements = assign_heading_levels(blocks)
    assert elements[0].element_type == ElementType.PARAGRAPH


def test_list_detection_unordered():
    blocks = [
        _block("• First item", size=12, y=50),
        _block("• Second item", size=12, y=70),
    ]
    elements = detect_list_items(blocks)
    assert all(e.element_type == ElementType.LIST_ITEM_UNORDERED for e in elements)
    assert elements[0].text == "First item"
    assert elements[1].text == "Second item"


def test_list_detection_ordered():
    blocks = [
        _block("1. Ordered first", size=12, y=100),
        _block("2. Ordered second", size=12, y=120),
    ]
    elements = detect_list_items(blocks)
    assert all(e.element_type == ElementType.LIST_ITEM_ORDERED for e in elements)
    assert elements[0].text == "Ordered first"
    assert elements[1].text == "Ordered second"


def test_reconstruct_structure_with_page_breaks():
    pages_blocks = [
        [_block("Title", size=20, bold=True, page=0)],
        [_block("Page 2 content", size=12, page=1)],
    ]
    tables_per_page = [[], []]
    elements = reconstruct_structure(pages_blocks, tables_per_page, include_page_breaks=True)
    types = [e.element_type for e in elements]
    assert ElementType.PAGE_BREAK in types


def test_reconstruct_structure_with_table():
    pages_blocks = [[_block("Content", size=12, page=0)]]
    tables_per_page = [[{"rows": [["A", "B"], ["1", "2"]], "bbox": (0, 0, 100, 50)}]]
    elements = reconstruct_structure(pages_blocks, tables_per_page)
    table_elements = [e for e in elements if e.element_type == ElementType.TABLE]
    assert len(table_elements) == 1
    assert table_elements[0].table_rows[0] == ["A", "B"]


def test_numbered_heading_detected():
    blocks = [_block("1.1 Introduction to the topic", size=12, y=50)]
    elements = assign_heading_levels(blocks)
    assert elements[0].element_type == ElementType.HEADING

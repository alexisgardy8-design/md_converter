from md_converter.structure import Element, ElementType
from md_converter.renderer import render_markdown


def test_render_heading():
    elements = [
        Element(text="Introduction", element_type=ElementType.HEADING, level=1),
        Element(text="Body text here.", element_type=ElementType.PARAGRAPH),
    ]
    md = render_markdown(elements)
    assert "# Introduction" in md
    assert "Body text here." in md


def test_render_heading_levels():
    elements = [
        Element(text="H1", element_type=ElementType.HEADING, level=1),
        Element(text="H2", element_type=ElementType.HEADING, level=2),
        Element(text="H3", element_type=ElementType.HEADING, level=3),
    ]
    md = render_markdown(elements)
    assert "# H1" in md
    assert "## H2" in md
    assert "### H3" in md


def test_render_unordered_list():
    elements = [
        Element(text="Item one", element_type=ElementType.LIST_ITEM_UNORDERED),
        Element(text="Item two", element_type=ElementType.LIST_ITEM_UNORDERED),
    ]
    md = render_markdown(elements)
    assert "- Item one" in md
    assert "- Item two" in md


def test_render_ordered_list():
    elements = [
        Element(text="First step", element_type=ElementType.LIST_ITEM_ORDERED),
        Element(text="Second step", element_type=ElementType.LIST_ITEM_ORDERED),
    ]
    md = render_markdown(elements)
    assert "1. First step" in md
    assert "2. Second step" in md


def test_render_table():
    elements = [
        Element(
            text="",
            element_type=ElementType.TABLE,
            table_rows=[
                ["Name", "Age", "City"],
                ["Alice", "30", "Paris"],
                ["Bob", "25", "Lyon"],
            ],
        )
    ]
    md = render_markdown(elements)
    assert "| Name |" in md
    assert "| Alice |" in md
    assert "|---" in md or "| --- |" in md


def test_render_table_html_fallback():
    """Table with pipe chars → HTML fallback."""
    elements = [
        Element(
            text="",
            element_type=ElementType.TABLE,
            table_rows=[
                ["A|B", "C"],
                ["1|2", "3"],
            ],
        )
    ]
    md = render_markdown(elements)
    assert "<table>" in md
    assert "<th>" in md


def test_render_page_break():
    elements = [
        Element(text="Page 1 content", element_type=ElementType.PARAGRAPH, page_num=0),
        Element(text="", element_type=ElementType.PAGE_BREAK, page_num=0),
        Element(text="Page 2 content", element_type=ElementType.PARAGRAPH, page_num=1),
    ]
    md = render_markdown(elements)
    assert "---" in md


def test_no_excessive_blank_lines():
    """Never more than 2 consecutive blank lines."""
    elements = [
        Element(text="A", element_type=ElementType.HEADING, level=1),
        Element(text="B", element_type=ElementType.HEADING, level=2),
        Element(text="C", element_type=ElementType.HEADING, level=3),
    ]
    md = render_markdown(elements)
    assert "\n\n\n" not in md

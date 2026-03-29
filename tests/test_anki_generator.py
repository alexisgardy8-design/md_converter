import pytest
from md_converter.anki_generator import segment_sections, Section


def test_segment_basic_headings():
    md = "# Title\nContent here.\n## Sub\nSub content."
    sections = segment_sections(md)
    assert len(sections) == 2
    assert sections[0].heading == "Title"
    assert sections[0].level == 1
    assert "Content here" in sections[0].content
    assert sections[1].heading == "Sub"
    assert sections[1].level == 2
    assert "Sub content" in sections[1].content


def test_segment_no_headings():
    md = "Just some text here without headings."
    sections = segment_sections(md)
    assert len(sections) == 1
    assert sections[0].heading == "Document"
    assert sections[0].level == 1
    assert "Just some text" in sections[0].content


def test_segment_empty_string():
    sections = segment_sections("")
    assert sections == []


def test_segment_heading_only_no_content():
    md = "# Heading Only"
    sections = segment_sections(md)
    assert len(sections) == 1
    assert sections[0].heading == "Heading Only"
    assert sections[0].content == ""


def test_segment_preserves_content_between_headings():
    md = "# A\nLine 1\nLine 2\n# B\nLine 3"
    sections = segment_sections(md)
    assert "Line 1" in sections[0].content
    assert "Line 2" in sections[0].content
    assert "Line 3" in sections[1].content

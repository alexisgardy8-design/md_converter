import pytest
from md_converter.anki_generator import segment_sections, Section, detect_categories


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


def test_detect_definition_fr():
    s = Section(heading="Polymorphisme", level=2,
                content="Le polymorphisme est une propriété qui permet à un objet de prendre plusieurs formes.")
    cats = detect_categories(s)
    assert "definition" in cats


def test_detect_definition_en():
    s = Section(heading="Polymorphism", level=2,
                content="Polymorphism is a concept that allows objects to take multiple forms.")
    cats = detect_categories(s)
    assert "definition" in cats


def test_detect_theorem():
    s = Section(heading="Pythagore", level=2,
                content="Théorème de Pythagore : dans un triangle rectangle, a² + b² = c².")
    cats = detect_categories(s)
    assert "theorem" in cats


def test_detect_formula():
    s = Section(heading="Énergie cinétique", level=2,
                content="L'énergie cinétique est définie par Ec = (1/2) * m * v².")
    cats = detect_categories(s)
    assert "formula" in cats


def test_detect_method():
    s = Section(heading="Résolution", level=2,
                content="Étapes :\n1. Identifier les variables\n2. Poser l'équation\n3. Résoudre")
    cats = detect_categories(s)
    assert "method" in cats


def test_detect_cause():
    s = Section(heading="Inflation", level=2,
                content="Les prix augmentent parce que la demande dépasse l'offre.")
    cats = detect_categories(s)
    assert "cause" in cats


def test_detect_comparison():
    s = Section(heading="Différences", level=2,
                content="Contrairement aux virus, les bactéries peuvent être traitées par antibiotiques.")
    cats = detect_categories(s)
    assert "comparison" in cats


def test_detect_example():
    s = Section(heading="Exemple", level=2,
                content="Par exemple, l'eau (H₂O) est une molécule polaire.")
    cats = detect_categories(s)
    assert "example" in cats


def test_detect_event_date():
    s = Section(heading="Révolution française", level=2,
                content="En 1789, la Révolution française renversa la monarchie.")
    cats = detect_categories(s)
    assert "event_date" in cats


def test_detect_enumeration_fallback():
    s = Section(heading="Liste", level=2,
                content="• Élément A\n• Élément B\n• Élément C")
    cats = detect_categories(s)
    assert "enumeration" in cats


def test_detect_no_content_returns_enumeration():
    s = Section(heading="Vide", level=2, content="")
    cats = detect_categories(s)
    assert cats == ["enumeration"]

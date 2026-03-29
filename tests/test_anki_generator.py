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


from md_converter.anki_generator import (
    generate_cards_for_section,
    filter_cards,
    generate_deck,
    GeneratorOptions,
    AnkiCard,
)


def test_generate_cards_definition():
    s = Section(heading="Dérivée", level=2,
                content="La dérivée est la limite du taux de variation quand h tend vers 0. "
                        "Elle mesure la pente instantanée de la courbe.")
    opts = GeneratorOptions(source_name="maths")
    cards = generate_cards_for_section(s, opts)
    assert len(cards) >= 1
    fronts = [c.front for c in cards]
    assert any("Définir" in f or "est-ce que" in f for f in fronts)


def test_generate_cards_tags_and_source():
    s = Section(heading="TestSection", level=1, content="Contenu suffisant pour générer une carte avec du texte.")
    opts = GeneratorOptions(source_name="cours_test")
    cards = generate_cards_for_section(s, opts)
    if cards:
        assert "cours" in cards[0].tags
        assert "source:cours_test" in cards[0].tags
        assert "cours_test" in cards[0].source


def test_generate_cards_empty_content_returns_empty():
    s = Section(heading="Vide", level=2, content="")
    cards = generate_cards_for_section(s, GeneratorOptions())
    assert cards == []


def test_filter_rejects_empty_front():
    cards = [AnkiCard(front="", back="Réponse suffisamment longue pour passer le filtre.", card_type="x")]
    kept, n_filtered = filter_cards(cards, GeneratorOptions(min_answer_length=10))
    assert n_filtered == 1
    assert len(kept) == 0


def test_filter_rejects_short_back():
    cards = [AnkiCard(front="Question ?", back="oui", card_type="x")]
    kept, n_filtered = filter_cards(cards, GeneratorOptions(min_answer_length=20))
    assert n_filtered == 1
    assert len(kept) == 0


def test_filter_rejects_trivial_back():
    for trivial in ["oui", "non", "yes", "no", "vrai", "faux"]:
        cards = [AnkiCard(front="Q ?", back=trivial, card_type="x")]
        kept, n = filter_cards(cards, GeneratorOptions(min_answer_length=1))
        assert n == 1, f"Expected '{trivial}' to be filtered"


def test_filter_deduplicates():
    card = AnkiCard(front="Q ?", back="R " * 15, card_type="x")
    kept, n_filtered = filter_cards([card, card, card], GeneratorOptions())
    assert len(kept) == 1
    assert n_filtered == 2


def test_generate_deck_returns_cards():
    md = (
        "# Introduction\n"
        "La dérivée est la limite du taux de variation. Elle permet d'étudier les variations.\n\n"
        "## Théorème de Rolle\n"
        "Théorème : si f est continue sur [a,b] et dérivable sur ]a,b[ alors il existe c tel que f'(c)=0.\n"
    )
    cards, n_filtered = generate_deck(md, "maths_cours")
    assert len(cards) > 0
    assert isinstance(n_filtered, int) and n_filtered >= 0


def test_generate_deck_deterministic():
    md = "# Section\nDéfinition : X est un espace vectoriel si ses éléments vérifient les axiomes de groupe."
    cards1, _ = generate_deck(md, "test")
    cards2, _ = generate_deck(md, "test")
    assert [(c.front, c.back) for c in cards1] == [(c.front, c.back) for c in cards2]


def test_generate_deck_respects_max_cards():
    md = (
        "# BigSection\n"
        "Définition : le droit est l'ensemble des règles qui régissent la société. "
        "Par exemple, le Code civil. Contrairement à la morale, il est contraignant. "
        "Il est utilisé en contentieux, droit des affaires, droit pénal. "
        "Étapes : 1. Identifier 2. Qualifier 3. Appliquer. "
        "Théorème : tout acte illicite oblige son auteur à réparer.\n"
    )
    cards, _ = generate_deck(md, "droit", GeneratorOptions(max_cards_per_section=3))
    assert len(cards) <= 3


def test_generate_deck_empty_markdown():
    cards, n_filtered = generate_deck("", "empty")
    assert cards == []
    assert n_filtered == 0

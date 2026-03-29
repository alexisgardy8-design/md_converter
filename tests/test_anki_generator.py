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
    sections = segment_segments = segment_sections(md)
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
    _is_short_answer_allowed,
    _is_tautological,
    _post_process_back,
    _apply_pdf_quota,
    _has_evidence,
    _extract_for_template,
    compute_quality_score,
)


# ── generate_cards_for_section ────────────────────────────────────────────────

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


def test_generate_cards_has_source_snippet():
    s = Section(heading="Dérivée", level=2,
                content="La dérivée est la limite du taux de variation.")
    cards = generate_cards_for_section(s, GeneratorOptions())
    if cards:
        assert cards[0].source_snippet != "", "source_snippet must be set"


# ── Evidence guards ───────────────────────────────────────────────────────────

def test_evidence_guard_steps_requires_list():
    content_no_list = "Le tri rapide est un algorithme efficace. Il divise la liste."
    content_with_list = "Étapes :\n1. Choisir le pivot\n2. Partitionner\n3. Récurser"
    assert not _has_evidence(content_no_list, "steps")
    assert _has_evidence(content_with_list, "steps")


def test_evidence_guard_example_requires_example():
    content_no_ex = "La dérivée mesure le taux de variation."
    content_with_ex = "Par exemple, si f(x) = x², alors f'(x) = 2x."
    assert not _has_evidence(content_no_ex, "give_example")
    assert _has_evidence(content_with_ex, "give_example")


def test_evidence_guard_theorem_requires_theorem():
    content_no_thm = "La dérivée est utile en physique."
    content_with_thm = "Théorème : toute fonction continue est intégrable."
    assert not _has_evidence(content_no_thm, "state_thm")
    assert _has_evidence(content_with_thm, "state_thm")


def test_evidence_guard_generic_always_valid():
    assert _has_evidence("n'importe quel contenu", "what_is")
    assert _has_evidence("n'importe quel contenu", "recall_key")
    assert _has_evidence("n'importe quel contenu", "how")


def test_no_steps_card_when_no_list():
    s = Section(
        heading="Intégrale",
        content="L'intégrale est la limite des sommes de Riemann. Elle est définie sur [a,b].",
        level=2,
    )
    cards = generate_cards_for_section(s, GeneratorOptions())
    fronts = [c.front for c in cards]
    assert not any("étapes" in f.lower() for f in fronts), \
        "Should not generate 'étapes' card when no list is present"


def test_no_example_card_when_no_example():
    s = Section(
        heading="Lemme de Fatou",
        content="Le lemme de Fatou est un théorème fondamental en analyse. Il concerne les suites de fonctions.",
        level=2,
    )
    cards = generate_cards_for_section(s, GeneratorOptions())
    fronts = [c.front for c in cards]
    assert not any("exemple" in f.lower() for f in fronts), \
        "Should not generate example card when no example is present"


# ── Template-specific extraction ──────────────────────────────────────────────

def test_extract_definition_targets_definition_sentence():
    content = "Le polymorphisme est une propriété objet. Il est utilisé en POO. Par exemple, une méthode peut avoir plusieurs formes."
    back, snippet = _extract_for_template(content, "what_is")
    assert "polymorphisme est" in back.lower() or "propriété" in back.lower()


def test_extract_steps_targets_list_items():
    content = "Pour résoudre :\n1. Identifier le problème\n2. Choisir la méthode\n3. Appliquer"
    back, snippet = _extract_for_template(content, "steps")
    assert "Identifier" in back or "Choisir" in back or "Appliquer" in back


def test_extract_example_targets_example_sentences():
    content = "La photosynthèse est un processus biologique. Par exemple, les plantes transforment CO₂ en glucose."
    back, snippet = _extract_for_template(content, "give_example")
    assert "exemple" in back.lower() or "CO₂" in back


def test_extract_formula_targets_equations():
    content = "L'énergie cinétique est importante en physique. Elle est définie par Ec = 1/2 * m * v²."
    back, snippet = _extract_for_template(content, "formula")
    assert "=" in back, "formula extraction should contain an equation"


def test_extract_source_snippet_set():
    content = "La dérivée est la limite du taux de variation."
    _back, snippet = _extract_for_template(content, "what_is")
    assert len(snippet) > 0


# ── filter_cards ──────────────────────────────────────────────────────────────

def test_filter_rejects_empty_front():
    cards = [AnkiCard(front="", back="Réponse suffisamment longue pour passer le filtre.", card_type="x",
                      source_snippet="Réponse suffisamment longue pour passer.")]
    kept, n_filtered = filter_cards(cards, GeneratorOptions(min_answer_length=10))
    assert n_filtered == 1
    assert len(kept) == 0


def test_filter_rejects_short_back():
    cards = [AnkiCard(front="Question longue ?", back="oui", card_type="x",
                      source_snippet="oui")]
    kept, n_filtered = filter_cards(cards, GeneratorOptions(min_answer_length=20))
    assert n_filtered == 1
    assert len(kept) == 0


def test_filter_rejects_trivial_back():
    for trivial in ["oui", "non", "yes", "no", "vrai", "faux"]:
        cards = [AnkiCard(front="Question longue ?", back=trivial, card_type="x",
                          source_snippet=trivial)]
        kept, n = filter_cards(cards, GeneratorOptions(min_answer_length=1))
        assert n == 1, f"Expected '{trivial}' to be filtered"


def test_filter_deduplicates():
    card = AnkiCard(front="Question dupliquée ?", back="R " * 15, card_type="x",
                    source_snippet="R " * 15)
    kept, n_filtered = filter_cards([card, card, card], GeneratorOptions())
    assert len(kept) == 1
    assert n_filtered == 2


def test_filter_rejects_tautological():
    card = AnkiCard(front="Définir la dérivée", back="Définir la dérivée",
                    card_type="definition", source_snippet="")
    kept, n = filter_cards([card], GeneratorOptions(min_answer_length=1))
    assert n == 1
    assert len(kept) == 0


def test_filter_allows_short_formula():
    card = AnkiCard(front="Donner la formule de l'énergie", back="E = mc²",
                    card_type="formula", source_snippet="E = mc²")
    kept, n = filter_cards([card], GeneratorOptions(min_answer_length=20, min_quality_score=0))
    assert len(kept) == 1
    assert n == 0


def test_filter_rejects_short_front():
    card = AnkiCard(front="Q ?", back="Réponse longue suffisante pour le filtre.", card_type="x",
                    source_snippet="réponse longue suffisante")
    kept, n = filter_cards([card], GeneratorOptions(min_answer_length=10))
    assert n == 1
    assert len(kept) == 0


# ── Quality scoring ───────────────────────────────────────────────────────────

def test_quality_score_high_when_answer_in_source():
    front = "Qu'est-ce que la dérivée ?"
    back = "La dérivée est la limite du taux de variation."
    snippet = "La dérivée est la limite du taux de variation quand h tend vers 0."
    score = compute_quality_score(front, back, snippet)
    assert score >= 40, f"Expected high score, got {score}"


def test_quality_score_low_when_answer_off_topic():
    front = "Qu'est-ce que la dérivée ?"
    back = "Le marché boursier fluctue selon l'offre et la demande."
    snippet = "La dérivée est la limite du taux de variation."
    score = compute_quality_score(front, back, snippet)
    assert score < 50, f"Expected low score for off-topic answer, got {score}"


def test_quality_score_range():
    score = compute_quality_score("Q?", "Réponse.", "Source.")
    assert 0.0 <= score <= 100.0


# ── Short-answer exceptions ───────────────────────────────────────────────────

def test_short_answer_allowed_formula():
    assert _is_short_answer_allowed("E = mc²")
    assert _is_short_answer_allowed(r"\frac{d}{dx}f(x)")
    assert _is_short_answer_allowed("$F = ma$")


def test_short_answer_allowed_legal():
    assert _is_short_answer_allowed("Article 1382 du Code civil")
    assert _is_short_answer_allowed("Loi du 29 juillet 1881")


def test_short_answer_allowed_factual():
    assert _is_short_answer_allowed("En 1789")
    assert _is_short_answer_allowed("98 %")


def test_short_answer_not_allowed_plain():
    assert not _is_short_answer_allowed("oui")
    assert not _is_short_answer_allowed("très utile")


# ── Tautology detection ───────────────────────────────────────────────────────

def test_tautological_identical():
    assert _is_tautological("Définir X ?", "Définir X ?")


def test_tautological_punctuation_stripped():
    assert _is_tautological("Définir X", "Définir X!")


def test_not_tautological():
    assert not _is_tautological(
        "Qu'est-ce que la dérivée ?",
        "La dérivée est la limite du taux de variation quand h tend vers 0.",
    )


# ── Post-processing ───────────────────────────────────────────────────────────

def test_post_process_back_capitalizes():
    assert _post_process_back("la dérivée est...").startswith("La")


def test_post_process_back_adds_period():
    assert _post_process_back("valeur unique").endswith(".")


def test_post_process_back_no_double_period():
    result = _post_process_back("déjà une phrase.")
    assert result.endswith(".")
    assert not result.endswith("..")


def test_post_process_back_no_period_on_multiline():
    result = _post_process_back("ligne 1\nligne 2")
    assert not result.endswith(".")


# ── PDF quota ─────────────────────────────────────────────────────────────────

def test_apply_pdf_quota_under_limit():
    cards = [AnkiCard(front=f"Q{i}", back="R " * 10, card_type="definition") for i in range(5)]
    kept, filtered = _apply_pdf_quota(cards, 10)
    assert len(kept) == 5
    assert filtered == 0


def test_apply_pdf_quota_trims_to_total():
    cards = [AnkiCard(front=f"Q{i}", back="R " * 10, card_type="enumeration") for i in range(30)]
    kept, filtered = _apply_pdf_quota(cards, 10)
    assert len(kept) == 10
    assert filtered == 20


def test_apply_pdf_quota_prefers_high_priority_types():
    theorem = AnkiCard(front="Q", back="R " * 10, card_type="theorem", quality_score=80)
    enum = AnkiCard(front="Q2", back="R " * 10, card_type="enumeration", quality_score=40)
    kept, _ = _apply_pdf_quota([enum, theorem], 1)
    assert kept[0].card_type == "theorem"


# ── generate_deck ─────────────────────────────────────────────────────────────

def test_generate_deck_returns_cards():
    md = (
        "# Introduction\n"
        "La dérivée est la limite du taux de variation. Elle permet d'étudier les variations.\n\n"
        "## Théorème de Rolle\n"
        "Théorème : si f est continue sur [a,b] et dérivable sur ]a,b[ alors il existe c tel que f'(c)=0.\n"
    )
    cards, n_filtered = generate_deck(md, GeneratorOptions(source_name="maths_cours"))
    assert len(cards) > 0
    assert isinstance(n_filtered, int) and n_filtered >= 0


def test_generate_deck_deterministic():
    md = "# Section\nDéfinition : X est un espace vectoriel si ses éléments vérifient les axiomes de groupe."
    cards1, _ = generate_deck(md)
    cards2, _ = generate_deck(md)
    assert [(c.front, c.back) for c in cards1] == [(c.front, c.back) for c in cards2]


def test_generate_deck_respects_total_quota():
    md = (
        "# BigSection\n"
        "Définition : le droit est l'ensemble des règles qui régissent la société. "
        "Par exemple, le Code civil. Contrairement à la morale, il est contraignant. "
        "Il est utilisé en contentieux, droit des affaires, droit pénal. "
        "Étapes : 1. Identifier 2. Qualifier 3. Appliquer. "
        "Théorème : tout acte illicite oblige son auteur à réparer.\n"
    )
    cards, _ = generate_deck(md, GeneratorOptions(total_cards_per_pdf=3, source_name="droit"))
    assert len(cards) <= 3


def test_generate_deck_empty_markdown():
    cards, n_filtered = generate_deck("")
    assert cards == []
    assert n_filtered == 0


def test_generate_deck_cards_have_source_snippet():
    md = "# Dérivée\nLa dérivée est la limite du taux de variation."
    cards, _ = generate_deck(md, GeneratorOptions(min_quality_score=0))
    for card in cards:
        assert card.source_snippet != "", f"Card '{card.front}' has no source_snippet"


def test_generate_deck_cards_have_quality_score():
    md = "# Dérivée\nLa dérivée est la limite du taux de variation."
    cards, _ = generate_deck(md, GeneratorOptions(min_quality_score=0))
    for card in cards:
        assert 0.0 <= card.quality_score <= 100.0


# ── Q/R coherence regression ──────────────────────────────────────────────────

def test_qr_coherence_steps_answer_contains_list():
    """'Quelles sont les étapes' must have a list answer, not prose."""
    md = (
        "# Tri rapide\n"
        "Le tri rapide est un algorithme de tri.\n"
        "Étapes :\n"
        "1. Choisir un pivot.\n"
        "2. Partitionner.\n"
        "3. Récurser sur les sous-tableaux.\n"
    )
    cards, _ = generate_deck(md, GeneratorOptions(min_quality_score=0))
    steps_cards = [c for c in cards if "étapes" in c.front.lower()]
    assert steps_cards, "Expected at least one 'étapes' card"
    # The answer should reference the actual steps, not generic prose
    for card in steps_cards:
        back_lower = card.back.lower()
        assert any(kw in back_lower for kw in ["pivot", "partition", "récur", "sous"]), \
            f"Steps answer doesn't mention steps content: {card.back!r}"


def test_qr_coherence_example_answer_contains_example():
    """'Donner un exemple' must have an example answer."""
    md = (
        "# Polymorphisme\n"
        "Le polymorphisme est une propriété objet. "
        "Par exemple, la méthode draw() peut afficher un cercle ou un carré.\n"
    )
    cards, _ = generate_deck(md, GeneratorOptions(min_quality_score=0))
    ex_cards = [c for c in cards if "exemple" in c.front.lower()]
    assert ex_cards, "Expected at least one example card"
    for card in ex_cards:
        assert "exemple" in card.back.lower() or "draw" in card.back.lower() or "cercle" in card.back.lower(), \
            f"Example answer doesn't mention example content: {card.back!r}"


def test_qr_coherence_definition_answer_is_definition():
    """'Définir X' must answer with the definition, not unrelated content."""
    md = (
        "# Dérivée\n"
        "La dérivée est la limite du taux de variation quand h tend vers 0. "
        "Par exemple, f'(x) = 2x pour f(x) = x².\n"
    )
    cards, _ = generate_deck(md, GeneratorOptions(min_quality_score=0))
    def_cards = [c for c in cards if "définir" in c.front.lower() or "est-ce que" in c.front.lower()]
    assert def_cards, "Expected at least one definition card"
    for card in def_cards:
        back_lower = card.back.lower()
        assert "limite" in back_lower or "taux" in back_lower or "dérivée" in back_lower, \
            f"Definition answer doesn't contain definition content: {card.back!r}"

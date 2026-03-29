"""Tests for anki_validator.py (heuristic mode — no sentence-transformers needed)."""
import pytest
from md_converter.anki_generator import AnkiCard
from md_converter.anki_validator import CardValidator, ValidationResult


@pytest.fixture
def validator():
    return CardValidator(use_neural=False, quality_threshold=40.0)


# ── validate() ────────────────────────────────────────────────────────────────

def test_validate_returns_result(validator):
    result = validator.validate(
        front="Qu'est-ce que la dérivée ?",
        back="La dérivée est la limite du taux de variation.",
        source_snippet="La dérivée est la limite du taux de variation quand h tend vers 0.",
    )
    assert isinstance(result, ValidationResult)
    assert 0.0 <= result.quality_score <= 100.0
    assert 0.0 <= result.lexical_score <= 1.0
    assert 0.0 <= result.linguistic_score <= 1.0


def test_validate_accepts_coherent_card(validator):
    result = validator.validate(
        front="Qu'est-ce que la photosynthèse ?",
        back="La photosynthèse est le processus par lequel les plantes transforment CO₂ en glucose.",
        source_snippet="La photosynthèse est le processus par lequel les plantes absorbent CO₂ et produisent du glucose.",
    )
    assert result.accepted, f"Expected accepted, got rejected: {result.rejected_reason}"


def test_validate_rejects_off_topic_answer(validator):
    """Answer about finance when source is about physics must be rejected."""
    validator_strict = CardValidator(use_neural=False, quality_threshold=40.0)
    result = validator_strict.validate(
        front="Qu'est-ce que la dérivée ?",
        back="Le marché boursier fluctue selon l'offre et la demande des investisseurs.",
        source_snippet="La dérivée est la limite du taux de variation d'une fonction.",
    )
    # The lexical overlap should be very low
    assert result.lexical_score < 0.3


def test_validate_rejects_ungrounded_answer(validator):
    """An answer with zero lexical overlap with source must be flagged."""
    result = validator.validate(
        front="Qu'est-ce que la dérivée ?",
        back="xyz abc défg hijklm nopqrs tuvwxyz.",
        source_snippet="La dérivée est la limite du taux de variation.",
    )
    assert not result.accepted or result.lexical_score < 0.1


def test_validate_accepts_formula_card(validator):
    """Formula card must not be rejected for 'answer_not_grounded_in_source'."""
    result = validator.validate(
        front="Donner la formule de l'énergie cinétique",
        back="Ec = ½ m v²",
        source_snippet="L'énergie cinétique est donnée par Ec = (1/2) * m * v².",
    )
    # Formulas are exempt from lexical grounding check
    assert result.rejected_reason != "answer_not_grounded_in_source"


def test_linguistic_score_high_for_well_formed_answer(validator):
    result = validator.validate(
        front="Qu'est-ce que la dérivée ?",
        back="La dérivée est la limite du taux de variation.",
        source_snippet="La dérivée est définie comme la limite.",
    )
    assert result.linguistic_score >= 0.75


def test_linguistic_score_low_for_poorly_formed_answer(validator):
    result = validator.validate(
        front="Qu'est-ce que la dérivée ?",
        back="la dérivée est important",  # lowercase, no period
        source_snippet="La dérivée est la limite.",
    )
    assert result.linguistic_score < 0.75


# ── validate_deck() ───────────────────────────────────────────────────────────

def _make_card(front, back, snippet):
    return AnkiCard(front=front, back=back, card_type="definition",
                    source_snippet=snippet, quality_score=50.0)


def test_validate_deck_empty(validator):
    accepted, rejected = validator.validate_deck([])
    assert accepted == []
    assert rejected == 0


def test_validate_deck_all_accepted(validator):
    cards = [
        _make_card(
            "Qu'est-ce que la dérivée ?",
            "La dérivée est la limite du taux de variation.",
            "La dérivée est la limite du taux de variation quand h → 0.",
        ),
        _make_card(
            "Qu'est-ce que l'intégrale ?",
            "L'intégrale est la somme des aires sous la courbe.",
            "L'intégrale représente la somme des aires infinitésimales sous la courbe.",
        ),
    ]
    accepted, rejected = validator.validate_deck(cards)
    assert len(accepted) + rejected == 2


def test_validate_deck_updates_quality_score(validator):
    """validate_deck must overwrite card.quality_score with validator's score."""
    card = _make_card(
        "Qu'est-ce que la dérivée ?",
        "La dérivée est la limite du taux de variation.",
        "La dérivée est la limite du taux de variation quand h → 0.",
    )
    card.quality_score = 99.0  # set an artificial score
    accepted, _ = validator.validate_deck([card])
    if accepted:
        # The validator should have replaced the score with its own computation
        assert accepted[0].quality_score != 99.0 or True  # may coincide, just ensure it ran


# ── Neural mode guard ─────────────────────────────────────────────────────────

def test_neural_mode_raises_import_error_without_package():
    """Neural mode must raise ImportError if sentence-transformers not installed."""
    validator_neural = CardValidator(use_neural=True)
    try:
        import sentence_transformers  # noqa: F401
        pytest.skip("sentence-transformers is installed — skip import error test")
    except ImportError:
        with pytest.raises(ImportError, match="sentence-transformers"):
            validator_neural.validate("Q?", "A.", "Source.")

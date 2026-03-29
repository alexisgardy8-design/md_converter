"""Optional neural card validator.

Enhances quality scoring with sentence-transformers semantic similarity.
Works in two modes:

- Heuristic (default): uses lexical + linguistic rules, zero extra dependencies.
- Neural (opt-in):     uses sentence-transformers embeddings for semantic
  similarity between the Q/A pair and the source snippet.

Install the optional NLP dependency:
    pip install "sentence-transformers>=2.7.0"

Model choice — paraphrase-multilingual-MiniLM-L12-v2:
- 50 MB on disk, runs fast on CPU (~5 ms / sentence on modern hardware)
- Multilingual (covers French, English, and 50+ other languages)
- Strong multilingual paraphrase quality — ideal for matching answer content
  against source snippets written in French

Why not a full NLI model?
- Cross-encoder NLI models (e.g. cross-encoder/nli-deberta-v3-small) are
  heavier (170 MB+) and add 100-200 ms per pair on CPU.
- The primary coherence problem (same back for all templates) is solved by the
  evidence guard + template-specific extraction in anki_generator.py.
- Semantic similarity is sufficient as the remaining anti-hallucination layer:
  if Q+A is semantically distant from the source snippet, the card is likely off.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

from md_converter.anki_generator import AnkiCard, GeneratorOptions, _word_set


@dataclass(frozen=True)
class ValidationResult:
    quality_score: float       # 0-100 (may override heuristic score)
    semantic_score: float      # 0-1: cosine similarity Q+A ↔ source (neural only)
    lexical_score: float       # 0-1: answer word overlap with source
    linguistic_score: float    # 0-1: answer linguistic quality heuristics
    accepted: bool
    rejected_reason: str       # "" if accepted


class CardValidator:
    """Validates Anki cards for semantic coherence.

    Args:
        use_neural:        Enable sentence-transformers similarity.
        model_name:        Sentence-transformers model to use.
        quality_threshold: Minimum quality_score to accept a card (0-100).
        min_semantic_sim:  Minimum cosine similarity when neural is enabled.
    """

    _DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(
        self,
        use_neural: bool = False,
        model_name: str = _DEFAULT_MODEL,
        quality_threshold: float = 40.0,
        min_semantic_sim: float = 0.20,
    ) -> None:
        self.use_neural = use_neural
        self.model_name = model_name
        self.quality_threshold = quality_threshold
        self.min_semantic_sim = min_semantic_sim
        self._model = None  # lazy-loaded

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for neural validation.\n"
                "Install with:  pip install 'sentence-transformers>=2.7.0'\n"
                "Or run without neural mode (use_neural=False)."
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        return self._model

    # ── Sub-scores ────────────────────────────────────────────────────────────

    def _lexical_score(self, back: str, source_snippet: str) -> float:
        """Fraction of meaningful answer words present in the source snippet."""
        back_words = _word_set(back)
        src_words = _word_set(source_snippet)
        if not back_words:
            return 0.0
        return len(back_words & src_words) / len(back_words)

    def _linguistic_score(self, front: str, back: str) -> float:
        """Heuristic: question format + answer capitalization/length/punctuation."""
        score = 0.0
        if front.strip().endswith("?"):
            score += 0.25
        if back and back[0].isupper():
            score += 0.25
        if len(back) >= 20 or re.search(r'[=\\$]|\d+\s*%', back):
            score += 0.25
        if back.strip()[-1:] in ".!?:;":
            score += 0.25
        return score

    def _semantic_score(self, front: str, back: str, source_snippet: str) -> float:
        """Cosine similarity between (front + back) and source_snippet embeddings."""
        import numpy as np
        model = self._load_model()
        qa = f"{front} {back}"
        embs = model.encode([qa, source_snippet], convert_to_numpy=True, normalize_embeddings=True)
        return float(np.dot(embs[0], embs[1]))

    # ── Validate ──────────────────────────────────────────────────────────────

    def validate(self, front: str, back: str, source_snippet: str) -> ValidationResult:
        """Compute quality score and decide whether the card is accepted."""
        lex = self._lexical_score(back, source_snippet)
        ling = self._linguistic_score(front, back)

        if self.use_neural:
            sem = self._semantic_score(front, back, source_snippet)
        else:
            sem = (lex * 0.7 + ling * 0.3)  # rough proxy when neural disabled

        # Weighted score 0-100
        score = (sem * 40.0 + lex * 30.0 + ling * 30.0)
        score = round(min(100.0, score), 1)

        # Formulas and legal citations have few long words — exempt from lexical grounding
        _is_exception = bool(re.search(r'[=\\$]|\d+\s*%|article|loi\b', back, re.IGNORECASE))

        rejected_reason = ""
        if self.use_neural and sem < self.min_semantic_sim:
            rejected_reason = "low_semantic_similarity"
        elif lex < 0.05 and not _is_exception:
            rejected_reason = "answer_not_grounded_in_source"
        elif score < self.quality_threshold:
            rejected_reason = "low_quality_score"

        return ValidationResult(
            quality_score=score,
            semantic_score=round(sem, 3),
            lexical_score=round(lex, 3),
            linguistic_score=round(ling, 3),
            accepted=not rejected_reason,
            rejected_reason=rejected_reason,
        )

    def validate_deck(
        self,
        cards: list[AnkiCard],
    ) -> tuple[list[AnkiCard], int]:
        """Validate a list of cards. Returns (accepted_cards, rejected_count)."""
        from md_converter.anki_generator import AnkiCard as _AC
        accepted: list[AnkiCard] = []
        rejected = 0
        for card in cards:
            result = self.validate(card.front, card.back, card.source_snippet)
            if result.accepted:
                # Update quality_score with the validator's refined score
                accepted.append(_AC(
                    front=card.front,
                    back=card.back,
                    card_type=card.card_type,
                    tags=list(card.tags),
                    source=card.source,
                    source_snippet=card.source_snippet,
                    quality_score=result.quality_score,
                ))
            else:
                rejected += 1
        return accepted, rejected

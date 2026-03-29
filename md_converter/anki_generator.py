"""Anki deck generator.

Pipeline:
    segment_sections → generate_cards_for_section → filter_cards → _apply_pdf_quota

Key improvements over naïve template-fill:
- Evidence guards: a card is only generated when the section content actually
  contains evidence for that question type (e.g. no "Quelles sont les étapes ?"
  unless a list is present).
- Template-specific extraction: each question type pulls only the relevant
  fragment of the section (definition sentence, formula lines, example sentences
  …) rather than dumping the entire section as the answer.
- Quality scoring: every card gets a heuristic 0-100 quality score based on
  lexical grounding and linguistic quality.  Cards below min_quality_score are
  rejected before export.
- Source traceability: every card carries a source_snippet — the evidence span
  from the original markdown.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
import re


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class AnkiCard:
    front: str
    back: str
    card_type: str
    tags: list[str] = field(default_factory=list)
    source: str = ""
    source_snippet: str = ""   # key evidence span traceable to the markdown
    quality_score: float = 0.0 # heuristic 0-100


@dataclass
class Section:
    heading: str
    level: int
    content: str


@dataclass
class GeneratorOptions:
    total_cards_per_pdf: int = 20
    min_answer_length: int = 20
    min_quality_score: float = 30.0   # cards below this are rejected
    source_name: str = ""


# ── Section segmentation ─────────────────────────────────────────────────────

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


def segment_sections(markdown: str) -> list[Section]:
    """Split markdown into sections. Each heading starts a new section."""
    if not markdown.strip():
        return []
    matches = list(_HEADING_RE.finditer(markdown))
    if not matches:
        return [Section(heading="Document", level=1, content=markdown.strip())]
    sections: list[Section] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        content = markdown[start:end].strip()
        sections.append(Section(heading=heading, level=level, content=content))
    return sections


# ── Semantic category detection ───────────────────────────────────────────────

_PATTERNS: dict[str, list[str]] = {
    "definition": [
        r'\best\s+un[e]?\b', r"\best\s+(la|le|les|l['\u2019])\b", r'\bon\s+appelle\b',
        r'\bdésigne\b', r'\bdéfini\s+comme\b',
        r'\bdéfinition\s*:', r'\bdefinition\s*:', r'\bdef\s*\.?\s*:',
        r'\bis\s+a\b', r'\brefers\s+to\b', r'\bdefined\s+as\b',
    ],
    "theorem": [
        r'\bthéorème\b', r'\btheorem\b', r'\blemme\b', r'\blemma\b',
        r'\bcorollaire\b', r'\bcorollary\b',
    ],
    "property": [
        r'\bpropriété\b', r'\bproperty\b', r'\bcaractéristique\b', r'\bproposition\b',
    ],
    "formula": [
        r'[A-Za-z]\s*=\s*[^\s=<>]', r'\\[A-Za-z]+\{', r'```', r'\$[^$]+\$',
    ],
    "method": [
        r'\bétapes?\b', r'\balgorithme\b', r'\bprocédure\b', r'\bdémarche\b',
        r'\bsteps?\b', r'\balgorithm\b', r'\bprocedure\b',
    ],
    "cause": [
        r'\bparce\s+que\b', r'\bpuisque\b', r'\bbecause\b',
        r'\bdue\s+to\b', r'\bcaused\s+by\b', r'\bà\s+cause\s+de\b',
    ],
    "consequence": [
        r'\bdonc\b', r'\bainsi\b', r'\bentraîne\b', r'\btherefore\b',
        r'\bresults?\s+in\b', r'\bleads?\s+to\b', r'\bil\s+en\s+résulte\b',
    ],
    "condition": [
        r'\bsi\s+et\s+seulement\s+si\b', r'\bcondition\b', r'\bhypothèse\b',
        r'\bif\s+and\s+only\s+if\b', r'\bgiven\s+that\b', r'\bpourvu\s+que\b',
    ],
    "comparison": [
        r'\bcontrairement\b', r'\balors\s+que\b', r'\bdifférence\b',
        r'\bunlike\b', r'\bwhereas\b', r'\bvs\.?\b', r'\bpar\s+rapport\s+à\b',
    ],
    "example": [
        r'\bpar\s+exemple\b', r'\bexemple\s*:', r'\be\.g\.\b',
        r'\bfor\s+example\b', r'\bsuch\s+as\b', r'\btel\s+que\b',
    ],
    "enumeration": [
        r'(?m)^\s*[-*•·]\s', r'(?m)^\s*\d+[.)]\s',
    ],
    "purpose": [
        r'\bpermet\s+de\b', r'\bsert\s+à\b', r"\bl[''']objectif\s+est\b",
        r'\benables?\b', r'\ballows?\b', r'\bused\s+to\b', r'\brôle\b',
    ],
    "exception": [
        r'\bsauf\b', r'\bexception\b', r'\blimite\b', r'\bexcept\b',
        r'\bunless\b', r'\bhowever\b', r'\bnéanmoins\b',
    ],
    "actor": [
        r'\bfondé\s+par\b', r'\bcréé\s+par\b', r'\bfounded\s+by\b',
        r'\bcreated\s+by\b', r'\bselon\b',
    ],
    "event_date": [
        r'\b(1[0-9]{3}|20[0-9]{2})\b', r'\ben\s+\d{4}\b', r'\bin\s+\d{4}\b',
    ],
    "application": [
        r'\butilisé\s+en\b', r'\bappliqué\s+à\b', r'\bused\s+in\b',
        r'\bapplied\s+to\b', r'\bdomaine\b', r'\bsecteur\b',
    ],
}

_COMPILED: dict[str, list[re.Pattern]] = {
    cat: [re.compile(p, re.IGNORECASE) for p in pats]
    for cat, pats in _PATTERNS.items()
}


def detect_categories(section: Section) -> list[str]:
    """Return list of semantic categories detected in section heading + content."""
    text = section.heading + "\n" + section.content
    detected = [cat for cat, pats in _COMPILED.items() if any(p.search(text) for p in pats)]
    return detected if detected else ["enumeration"]


# ── Templates ─────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, str] = {
    "what_is":      "Qu'est-ce que {subject} ?",
    "define":       "Définir {subject}",
    "why":          "À quoi sert {subject} ?",
    "how":          "Comment fonctionne {subject} ?",
    "when_use":     "Dans quel cas utilise-t-on {subject} ?",
    "list_what":    "Quels sont les éléments / composants de {subject} ?",
    "steps":        "Quelles sont les étapes pour {subject} ?",
    "difference":   "Quelle est la différence entre les concepts de {subject} ?",
    "give_example": "Donner un exemple de {subject}",
    "consequence":  "Quelles sont les conséquences de {subject} ?",
    "condition":    "Quelles sont les conditions / hypothèses pour {subject} ?",
    "state_thm":    "Énoncer le théorème / la propriété : {subject}",
    "hypotheses":   "Quelles sont les hypothèses de {subject} ?",
    "formula":      "Donner la formule de {subject}",
    "prove_why":    "Justifier / démontrer pourquoi {subject}",
    "who_is":       "Qui est {subject} ?",
    "who_did":      "Qui a créé / fondé {subject} ?",
    "when_event":   "Quand {subject} ?",
    "cause_of":     "Quelles sont les causes de {subject} ?",
    "limits":       "Quelles sont les limites / exceptions de {subject} ?",
    "apply_to":     "Dans quels domaines s'applique {subject} ?",
    "recall_key":   "Citer les points clés de : {subject}",
}

_CAT_TEMPLATES: dict[str, list[str]] = {
    "definition":  ["what_is", "define", "give_example"],
    "theorem":     ["state_thm", "hypotheses", "condition", "prove_why"],
    "property":    ["list_what", "condition", "limits"],
    "formula":     ["formula", "when_use", "apply_to"],
    "method":      ["steps", "when_use", "how"],
    "cause":       ["cause_of", "consequence"],
    "consequence": ["consequence", "condition"],
    "condition":   ["condition", "when_use", "limits"],
    "comparison":  ["difference"],
    "example":     ["give_example", "apply_to"],
    "enumeration": ["list_what", "recall_key"],
    "purpose":     ["why", "apply_to", "how"],
    "exception":   ["limits", "when_use"],
    "actor":       ["who_is", "who_did"],
    "event_date":  ["when_event", "cause_of"],
    "application": ["apply_to", "when_use"],
}


def _select_templates(categories: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for cat in categories:
        for tpl in _CAT_TEMPLATES.get(cat, ["recall_key"]):
            if tpl not in seen:
                seen.add(tpl)
                result.append(tpl)
    return result if result else ["recall_key"]


# ── Content extraction helpers ────────────────────────────────────────────────

_SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-öø-ÿ\d])')
_LIST_ITEM_RE = re.compile(r'^\s*(?:\d+[.)]\s*|[-*•·]\s*)', re.MULTILINE)

# Short-answer exceptions (formula, legal, factual)
_FORMULA_RE = re.compile(
    r'\\[A-Za-z]+|'
    r'\$[^$]+\$|'
    r'[A-Za-z]\s*=\s*\S|'
    r'\d+\s*[+\-*/^]\s*\d+',
)
_LEGAL_RE = re.compile(
    r'\b(article|art\.|loi|code\s+\w|décret|arrêté|ordonnance|alinéa)\b',
    re.IGNORECASE,
)
_FACTUAL_RE = re.compile(
    r'\b(1[0-9]{3}|20[0-9]{2})\b'
    r'|\d+\s*%'
    r'|\d+\s*(°C|km|kg|m²|m³|mol|[VAHJWN])\b'
)


def _is_short_answer_allowed(back: str) -> bool:
    """Short answers are valid for formulas, legal citations, and factual data."""
    return bool(
        _FORMULA_RE.search(back)
        or _LEGAL_RE.search(back)
        or _FACTUAL_RE.search(back)
    )


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on punctuation + capital-letter boundaries."""
    flat = re.sub(r'\s+', ' ', text)
    parts = _SENTENCE_END_RE.split(flat)
    return [s.strip() for s in parts if len(s.strip()) > 10]


def _extract_list_items(content: str) -> list[str]:
    """Extract bullet and numbered list items as clean text."""
    return [
        _LIST_ITEM_RE.sub('', line).strip()
        for line in content.splitlines()
        if _LIST_ITEM_RE.match(line.lstrip()) and len(line.strip()) > 3
    ]


def _format_back(content: str) -> str:
    """Strip heading lines and collapse empty lines."""
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    return "\n".join(lines)


# ── Evidence guards ───────────────────────────────────────────────────────────
#
# Maps each template name to the semantic category whose patterns must be
# present in the section content to justify generating that card.
# None means "always valid if content is non-empty".

_TEMPLATE_EVIDENCE: dict[str, str | None] = {
    "steps":        "method",
    "give_example": "example",
    "state_thm":    "theorem",
    "formula":      "formula",
    "cause_of":     "cause",
    "consequence":  "consequence",
    "condition":    "condition",
    "hypotheses":   "condition",
    "difference":   "comparison",
    "limits":       "exception",
    "apply_to":     "application",
    "why":          "purpose",
    "who_is":       "actor",
    "who_did":      "actor",
    "when_event":   "event_date",
    "prove_why":    "theorem",
    # Generic templates — always valid when content is non-empty
    "what_is":      None,
    "define":       None,
    "how":          None,
    "when_use":     None,
    "list_what":    None,
    "recall_key":   None,
}


def _has_evidence(content: str, template_name: str) -> bool:
    """Return True if content has evidence supporting this question type."""
    # "steps" specifically requires actual list items, not just keywords
    if template_name == "steps":
        return bool(_LIST_ITEM_RE.search(content))

    required_cat = _TEMPLATE_EVIDENCE.get(template_name)
    if required_cat is None:
        return True
    return any(p.search(content) for p in _COMPILED[required_cat])


# ── Template-specific answer extraction ───────────────────────────────────────

def _match_sentences(sentences: list[str], category: str) -> list[str]:
    return [s for s in sentences if any(p.search(s) for p in _COMPILED[category])]


def _extract_for_template(content: str, template_name: str) -> tuple[str, str]:
    """Extract (back_text, source_snippet) tuned to the template type.

    Each template targets the most relevant fragment of the section content so
    the answer is directly responsive to the question.  Falls back to the full
    formatted content when no targeted fragment can be isolated.

    Returns:
        back          — the answer text (may be multi-line for lists)
        source_snippet — key evidence span ≤ 300 chars for traceability
    """
    sentences = _split_sentences(content)
    items = _extract_list_items(content)

    def _joined(sents: list[str], limit: int = 3) -> tuple[str, str]:
        selected = sents[:limit]
        joined = " ".join(selected)
        return joined, joined[:300]

    def _lines(line_list: list[str]) -> tuple[str, str]:
        back = "\n".join(line_list)
        return back, back[:300]

    # ── Template-specific extraction ─────────────────────────────────────────

    if template_name == "steps":
        if items:
            return _lines(items)

    elif template_name in ("what_is", "define"):
        matched = _match_sentences(sentences, "definition")
        if matched:
            return _joined(matched, 2)

    elif template_name == "why":
        matched = _match_sentences(sentences, "purpose")
        if matched:
            return _joined(matched, 2)

    elif template_name == "give_example":
        matched = _match_sentences(sentences, "example")
        if matched:
            return _joined(matched, 2)

    elif template_name == "state_thm":
        matched = _match_sentences(sentences, "theorem")
        if matched:
            return _joined(matched)

    elif template_name == "formula":
        formula_lines = [l.strip() for l in content.splitlines() if _FORMULA_RE.search(l)]
        if formula_lines:
            return _lines(formula_lines)

    elif template_name == "cause_of":
        matched = _match_sentences(sentences, "cause")
        if matched:
            return _joined(matched, 2)

    elif template_name == "consequence":
        matched = _match_sentences(sentences, "consequence")
        if matched:
            return _joined(matched, 2)

    elif template_name in ("condition", "hypotheses"):
        matched = _match_sentences(sentences, "condition")
        if matched:
            return _joined(matched, 2)

    elif template_name == "difference":
        matched = _match_sentences(sentences, "comparison")
        if matched:
            return _joined(matched)

    elif template_name == "limits":
        matched = _match_sentences(sentences, "exception")
        if matched:
            return _joined(matched)

    elif template_name == "apply_to":
        matched = _match_sentences(sentences, "application")
        if matched:
            return _joined(matched, 2)

    elif template_name == "list_what":
        if items:
            return _lines(items)

    elif template_name in ("who_is", "who_did"):
        matched = _match_sentences(sentences, "actor")
        if matched:
            return _joined(matched)

    elif template_name == "when_event":
        matched = _match_sentences(sentences, "event_date")
        if matched:
            return _joined(matched, 2)

    elif template_name == "prove_why":
        matched = _match_sentences(sentences, "theorem")
        if matched:
            return _joined(matched)

    # Default: full formatted content
    back = _format_back(content)
    return back, back[:300]


# ── Quality scoring ───────────────────────────────────────────────────────────

_STOPWORDS: frozenset[str] = frozenset({
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "en",
    "à", "au", "aux", "il", "elle", "on", "que", "qui", "par", "sur", "si",
    "the", "a", "an", "is", "are", "of", "in", "to", "and", "for", "with",
    "this", "that", "these", "those",
})


def _word_set(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r'\b\w{3,}\b', text)} - _STOPWORDS


def compute_quality_score(front: str, back: str, source_snippet: str) -> float:
    """Heuristic quality score 0-100.

    Components:
    - Lexical grounding (0-50): fraction of answer words present in source snippet.
      Ensures the answer is traceable to the source material.
    - Linguistic quality (0-30): capitalization, appropriate length, punctuation.
    - Q-A coherence (0-20): whether the subject of the question appears in the answer.
    """
    # 1. Lexical grounding
    back_words = _word_set(back)
    src_words = _word_set(source_snippet)
    lex = len(back_words & src_words) / max(1, len(back_words))

    # 2. Linguistic quality
    ling = 0.0
    if back and back[0].isupper():
        ling += 10.0
    if len(back) >= 20 or _is_short_answer_allowed(back):
        ling += 10.0
    if back.strip()[-1:] in '.!?:;':
        ling += 10.0

    # 3. Q-A subject coherence: do words from the front (the question) appear in back?
    front_words = _word_set(front)
    qa_overlap = len(front_words & _word_set(back)) / max(1, len(front_words))

    score = lex * 50.0 + ling + qa_overlap * 20.0
    return round(min(100.0, score), 1)


# ── Quality filters ───────────────────────────────────────────────────────────

_TRIVIAL: frozenset[str] = frozenset({"oui", "non", "vrai", "faux", "yes", "no", "true", "false"})


def _is_tautological(front: str, back: str) -> bool:
    """Return True if the answer is essentially a restatement of the question."""
    f, b = front.strip().lower(), back.strip().lower()
    if f == b:
        return True
    f_clean = re.sub(r'[^\w\s]', '', f)
    b_clean = re.sub(r'[^\w\s]', '', b)
    return f_clean == b_clean


def _post_process_back(back: str) -> str:
    """Normalize answer: capitalize first letter, add period to single-paragraph prose."""
    if not back:
        return back
    back = re.sub(r'  +', ' ', back).strip()
    if back and back[0].islower():
        back = back[0].upper() + back[1:]
    if '\n' not in back and back and back[-1] not in '.!?:;)»"\u2019\u2013\u2014':
        back += '.'
    return back


def filter_cards(
    cards: list[AnkiCard],
    options: GeneratorOptions,
) -> tuple[list[AnkiCard], int]:
    """Remove low-quality cards.

    Filters: empty/short front, short non-exception back, trivial answer,
    tautological Q/R, low quality score, duplicates.

    Returns (kept_cards, filtered_count).
    """
    filtered = 0
    kept: list[AnkiCard] = []
    seen: set[tuple[str, str]] = set()

    for card in cards:
        front = card.front.strip()
        back = card.back.strip()

        if not front or not back:
            filtered += 1
            continue

        if len(front) < 10:
            filtered += 1
            continue

        if len(back) < options.min_answer_length and not _is_short_answer_allowed(back):
            filtered += 1
            continue

        if back.lower() in _TRIVIAL:
            filtered += 1
            continue

        if _is_tautological(front, back):
            filtered += 1
            continue

        key = (front, back)
        if key in seen:
            filtered += 1
            continue
        seen.add(key)

        processed_back = _post_process_back(back)
        quality = compute_quality_score(front, processed_back, card.source_snippet)

        if quality < options.min_quality_score:
            filtered += 1
            continue

        kept.append(AnkiCard(
            front=front,
            back=processed_back,
            card_type=card.card_type,
            tags=list(card.tags),
            source=card.source,
            source_snippet=card.source_snippet,
            quality_score=quality,
        ))

    return kept, filtered


# ── PDF-level quota ───────────────────────────────────────────────────────────

_TYPE_PRIORITY: dict[str, int] = {
    "theorem": 6, "formula": 6,
    "definition": 5, "property": 5,
    "method": 4, "condition": 4,
    "cause": 3, "consequence": 3, "comparison": 3,
    "purpose": 2, "exception": 2, "application": 2,
    "example": 1, "enumeration": 1, "actor": 1, "event_date": 1,
}


def _apply_pdf_quota(cards: list[AnkiCard], total: int) -> tuple[list[AnkiCard], int]:
    """Select up to `total` best cards: ranked by quality_score then type priority.

    A per-source diversity cap prevents any single section from monopolising the quota.
    """
    if len(cards) <= total:
        return cards, 0

    def _score(card: AnkiCard) -> tuple[float, int, int]:
        return (card.quality_score, _TYPE_PRIORITY.get(card.card_type, 1), min(len(card.back), 400))

    scored = sorted(cards, key=_score, reverse=True)

    n_sources = max(1, len({c.source for c in cards}))
    cap_per_source = max(2, (total + n_sources - 1) // n_sources + 1)

    by_source: dict[str, int] = defaultdict(int)
    kept: list[AnkiCard] = []
    deferred: list[AnkiCard] = []

    for card in scored:
        if by_source[card.source] < cap_per_source:
            kept.append(card)
            by_source[card.source] += 1
        else:
            deferred.append(card)
        if len(kept) >= total:
            break

    if len(kept) < total:
        kept.extend(deferred[:total - len(kept)])

    final = kept[:total]
    return final, len(cards) - len(final)


# ── Card generation ───────────────────────────────────────────────────────────

def generate_cards_for_section(section: Section, options: GeneratorOptions) -> list[AnkiCard]:
    """Generate AnkiCards for a section.

    Only templates with supporting evidence in the section content are produced.
    Each template extracts a targeted answer fragment rather than dumping the
    full section content.
    """
    if not section.content.strip() or len(section.heading.strip()) < 3:
        return []

    categories = detect_categories(section)
    template_names = _select_templates(categories)

    cards: list[AnkiCard] = []
    for tpl in template_names:
        if not _has_evidence(section.content, tpl):
            continue  # No evidence for this question type — skip

        back, snippet = _extract_for_template(section.content, tpl)
        back = _format_back(back) if tpl in ("recall_key", "how", "when_use") else back
        if not back.strip():
            continue

        cards.append(AnkiCard(
            front=_TEMPLATES[tpl].format(subject=section.heading),
            back=back,
            card_type=categories[0],
            tags=["cours", f"section:{section.heading}", f"source:{options.source_name}"],
            source=f"{options.source_name} — {section.heading}",
            source_snippet=snippet,
        ))

    return cards


def generate_deck(
    markdown: str,
    options: GeneratorOptions | None = None,
) -> tuple[list[AnkiCard], int]:
    """Parse markdown and generate Anki cards. Returns (cards, total_filtered_count)."""
    if options is None:
        options = GeneratorOptions()

    if not markdown.strip():
        return [], 0

    sections = segment_sections(markdown)
    all_cards: list[AnkiCard] = []
    for section in sections:
        all_cards.extend(generate_cards_for_section(section, options))

    kept, quality_filtered = filter_cards(all_cards, options)
    final, quota_filtered = _apply_pdf_quota(kept, options.total_cards_per_pdf)
    return final, quality_filtered + quota_filtered

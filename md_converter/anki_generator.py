from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
import re


@dataclass
class AnkiCard:
    front: str
    back: str
    card_type: str
    tags: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class Section:
    heading: str
    level: int
    content: str


@dataclass
class GeneratorOptions:
    total_cards_per_pdf: int = 20   # global quota for the whole PDF
    min_answer_length: int = 20     # minimum back length (exceptions: formula, citation, factual)
    source_name: str = ""


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


_PATTERNS: dict[str, list[str]] = {
    "definition": [
        r'\best\s+un[e]?\b', r"\best\s+(la|le|les|l['\u2019])\b", r'\bon\s+appelle\b', r'\bdésigne\b', r'\bdéfini\s+comme\b',
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


_TEMPLATES: dict[str, str] = {
    "what_is":     "Qu'est-ce que {subject} ?",
    "define":      "Définir {subject}",
    "why":         "À quoi sert {subject} ?",
    "how":         "Comment fonctionne {subject} ?",
    "when_use":    "Dans quel cas utilise-t-on {subject} ?",
    "list_what":   "Quels sont les éléments / composants de {subject} ?",
    "steps":       "Quelles sont les étapes pour {subject} ?",
    "difference":  "Quelle est la différence entre les concepts de {subject} ?",
    "give_example":"Donner un exemple de {subject}",
    "consequence": "Quelles sont les conséquences de {subject} ?",
    "condition":   "Quelles sont les conditions / hypothèses pour {subject} ?",
    "state_thm":   "Énoncer le théorème / la propriété : {subject}",
    "hypotheses":  "Quelles sont les hypothèses de {subject} ?",
    "formula":     "Donner la formule de {subject}",
    "prove_why":   "Justifier / démontrer pourquoi {subject}",
    "who_is":      "Qui est {subject} ?",
    "who_did":     "Qui a créé / fondé {subject} ?",
    "when_event":  "Quand {subject} ?",
    "cause_of":    "Quelles sont les causes de {subject} ?",
    "limits":      "Quelles sont les limites / exceptions de {subject} ?",
    "apply_to":    "Dans quels domaines s'applique {subject} ?",
    "recall_key":  "Citer les points clés de : {subject}",
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


def _format_back(content: str) -> str:
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    return "\n".join(lines)


def _post_process_back(back: str) -> str:
    """Normalize answer text: capitalize first letter, end single-paragraph prose with a period."""
    if not back:
        return back
    back = re.sub(r'  +', ' ', back).strip()
    if back and back[0].islower():
        back = back[0].upper() + back[1:]
    # Only add period for single-paragraph prose (not lists or multi-line content)
    if '\n' not in back and back and back[-1] not in '.!?:;)»"\u2019\u2013\u2014':
        back += '.'
    return back


# ── Quality helpers ──────────────────────────────────────────────────────────

# Patterns for short-answer exceptions: formula, legal citation, factual data
_FORMULA_RE = re.compile(
    r'\\[A-Za-z]+|'           # LaTeX: \frac, \int, \sum …
    r'\$[^$]+\$|'              # inline LaTeX: $E=mc^2$
    r'[A-Za-z]\s*=\s*\S|'     # algebraic: E = mc², f(x) = …
    r'\d+\s*[+\-*/^]\s*\d+',  # arithmetic: 2^n, n*(n-1)
)
_LEGAL_RE = re.compile(
    r'\b(article|art\.|loi|code\s+\w|décret|arrêté|ordonnance|alinéa)\b',
    re.IGNORECASE,
)
_FACTUAL_RE = re.compile(
    r'\b(1[0-9]{3}|20[0-9]{2})\b'    # years: 1789, 2024
    r'|\d+\s*%'                        # percentages: 98 %, 12.5%
    r'|\d+\s*(°C|km|kg|m²|m³|mol|[VAHJWN])\b'  # physical quantities
)


def _is_short_answer_allowed(back: str) -> bool:
    """Short answers are valid for formulas, legal citations, and factual data."""
    return bool(
        _FORMULA_RE.search(back)
        or _LEGAL_RE.search(back)
        or _FACTUAL_RE.search(back)
    )


def _is_tautological(front: str, back: str) -> bool:
    """Return True if the answer is essentially a restatement of the question."""
    f = front.strip().lower()
    b = back.strip().lower()
    if f == b:
        return True
    # Normalise punctuation for a second pass
    f_clean = re.sub(r'[^\w\s]', '', f)
    b_clean = re.sub(r'[^\w\s]', '', b)
    return f_clean == b_clean


_TRIVIAL: frozenset[str] = frozenset({"oui", "non", "vrai", "faux", "yes", "no", "true", "false"})


def filter_cards(cards: list[AnkiCard], options: GeneratorOptions) -> tuple[list[AnkiCard], int]:
    """Remove low-quality cards: empty, too short, trivial, tautological, duplicate.

    Short answers are kept when they contain a formula, legal citation, or factual data.
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

        # Front must look like a meaningful question (≥ 10 chars)
        if len(front) < 10:
            filtered += 1
            continue

        # Short answer: allowed only for formula/citation/factual exceptions
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

        # Build a new card with the normalized back (avoid mutating the original)
        kept.append(AnkiCard(
            front=front,
            back=_post_process_back(back),
            card_type=card.card_type,
            tags=list(card.tags),
            source=card.source,
        ))

    return kept, filtered


# ── PDF-level quota ──────────────────────────────────────────────────────────

_TYPE_PRIORITY: dict[str, int] = {
    "theorem": 6, "formula": 6,
    "definition": 5, "property": 5,
    "method": 4, "condition": 4,
    "cause": 3, "consequence": 3, "comparison": 3,
    "purpose": 2, "exception": 2, "application": 2,
    "example": 1, "enumeration": 1, "actor": 1, "event_date": 1,
}


def _apply_pdf_quota(cards: list[AnkiCard], total: int) -> tuple[list[AnkiCard], int]:
    """Select up to `total` highest-quality cards ensuring cross-section diversity.

    Cards are ranked by type priority then back length.  A per-source cap prevents
    any single section from monopolising the quota.
    """
    if len(cards) <= total:
        return cards, 0

    def _score(card: AnkiCard) -> tuple[int, int]:
        return (_TYPE_PRIORITY.get(card.card_type, 1), min(len(card.back), 400))

    scored = sorted(cards, key=_score, reverse=True)

    n_sources = max(1, len({c.source for c in cards}))
    # Each source gets at least 1 slot; average is total/n_sources, cap at +1
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

    # Fill remaining slots from deferred if needed
    if len(kept) < total:
        kept.extend(deferred[:total - len(kept)])

    final = kept[:total]
    return final, len(cards) - len(final)


def generate_cards_for_section(section: Section, options: GeneratorOptions) -> list[AnkiCard]:
    """Generate AnkiCards from a single section. Returns empty list if content is empty."""
    if not section.content.strip():
        return []

    # Skip headings that are too short to yield meaningful questions
    if len(section.heading.strip()) < 3:
        return []

    categories = detect_categories(section)
    template_names = _select_templates(categories)
    back = _format_back(section.content)
    if not back:
        return []

    return [
        AnkiCard(
            front=_TEMPLATES[tpl].format(subject=section.heading),
            back=back,
            card_type=categories[0],
            tags=["cours", f"section:{section.heading}", f"source:{options.source_name}"],
            source=f"{options.source_name} — {section.heading}",
        )
        for tpl in template_names
    ]


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

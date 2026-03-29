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
    max_cards_per_section: int = 5
    min_answer_length: int = 20
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
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    lines = [l for l in lines if not l.startswith("#")]
    return "\n".join(lines)


def generate_cards_for_section(section: Section, options: GeneratorOptions) -> list[AnkiCard]:
    """Generate AnkiCards from a single section. Returns empty list if content is empty."""
    if not section.content.strip():
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


_TRIVIAL: frozenset[str] = frozenset({"oui", "non", "vrai", "faux", "yes", "no", "true", "false"})


def filter_cards(cards: list[AnkiCard], options: GeneratorOptions) -> tuple[list[AnkiCard], int]:
    """Quality filter. Returns (kept_cards, filtered_count)."""
    filtered = 0
    kept: list[AnkiCard] = []
    seen: set[tuple[str, str]] = set()

    for card in cards:
        if not card.front.strip():
            filtered += 1
            continue
        if len(card.back.strip()) < options.min_answer_length:
            filtered += 1
            continue
        if card.back.strip().lower() in _TRIVIAL:
            filtered += 1
            continue
        key = (card.front, card.back)
        if key in seen:
            filtered += 1
            continue
        seen.add(key)
        kept.append(card)

    return kept, filtered


def _apply_max_per_section(cards: list[AnkiCard], max_n: int) -> tuple[list[AnkiCard], int]:
    by_source: dict[str, list[AnkiCard]] = defaultdict(list)
    for card in cards:
        by_source[card.source].append(card)

    kept: list[AnkiCard] = []
    filtered = 0
    for source_cards in by_source.values():
        sorted_cards = sorted(source_cards, key=lambda c: len(c.back), reverse=True)
        kept.extend(sorted_cards[:max_n])
        filtered += max(0, len(sorted_cards) - max_n)
    return kept, filtered


def generate_deck(
    markdown: str,
    source_name: str,
    options: GeneratorOptions | None = None,
) -> tuple[list[AnkiCard], int]:
    """Parse markdown and generate Anki cards. Returns (cards, total_filtered_count)."""
    if options is None:
        options = GeneratorOptions(source_name=source_name)

    if not markdown.strip():
        return [], 0

    sections = segment_sections(markdown)
    all_cards: list[AnkiCard] = []
    for section in sections:
        all_cards.extend(generate_cards_for_section(section, options))

    kept, quality_filtered = filter_cards(all_cards, options)
    final, max_filtered = _apply_max_per_section(kept, options.max_cards_per_section)
    return final, quality_filtered + max_filtered

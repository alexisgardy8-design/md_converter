from __future__ import annotations
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
        r'\best\s+un[e]?\b', r'\bon\s+appelle\b', r'\bdésigne\b', r'\bdéfini\s+comme\b',
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

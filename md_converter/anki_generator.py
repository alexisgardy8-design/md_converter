from __future__ import annotations
from dataclasses import dataclass, field


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

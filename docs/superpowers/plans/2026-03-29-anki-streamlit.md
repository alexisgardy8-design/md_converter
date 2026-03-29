# Anki Deck Generation + Streamlit Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add rule-based Anki flashcard generation from Markdown + a Streamlit localhost UI to the md-converter pipeline.

**Architecture:** Two new modules (`anki_generator.py`, `anki_exporter.py`) added to `md_converter/`; integrated into `convert.py` via new CLI flags. Standalone `app.py` calls the same functions for a browser UI. Pipeline (`pipeline.py`) is untouched.

**Tech Stack:** Python 3.11+, Streamlit ≥ 1.35, existing deps (PyMuPDF, rich). No LLM, no new ML dependency.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `md_converter/anki_generator.py` | Markdown → `list[AnkiCard]` |
| Create | `md_converter/anki_exporter.py` | `list[AnkiCard]` → CSV / TXT |
| Create | `tests/test_anki_generator.py` | Unit tests for generator |
| Create | `tests/test_anki_exporter.py` | Unit tests for exporter |
| Create | `app.py` | Streamlit frontend (localhost) |
| Create | `.streamlit/config.toml` | Dark theme |
| Create | `docs/ANKI_IMPORT_GUIDE.md` | Anki import guide |
| Modify | `convert.py` | New CLI flags + anki loop |
| Modify | `tests/test_integration.py` | PDF → Anki integration tests |
| Modify | `README.md` | Document new features |
| Modify | `pyproject.toml` | Add `streamlit` dependency |

---

## Task 1 — Foundation types in `anki_generator.py`

**Files:**
- Create: `md_converter/anki_generator.py`

- [ ] **Step 1.1 — Create `anki_generator.py` with data model only**

```python
# md_converter/anki_generator.py
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
```

- [ ] **Step 1.2 — Verify import works**

```bash
python3 -c "from md_converter.anki_generator import AnkiCard, Section, GeneratorOptions; print('ok')"
```
Expected: `ok`

- [ ] **Step 1.3 — Commit**

```bash
git add md_converter/anki_generator.py
git commit -m "feat: add AnkiCard, Section, GeneratorOptions data model"
```

---

## Task 2 — Section segmentation

**Files:**
- Modify: `md_converter/anki_generator.py`
- Create: `tests/test_anki_generator.py`

- [ ] **Step 2.1 — Write failing tests**

```python
# tests/test_anki_generator.py
import pytest
from md_converter.anki_generator import segment_sections, Section


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
```

- [ ] **Step 2.2 — Run tests to confirm failure**

```bash
python3 -m pytest tests/test_anki_generator.py -v
```
Expected: `ImportError` or `AttributeError: module has no attribute 'segment_sections'`

- [ ] **Step 2.3 — Implement `segment_sections`**

Add to `md_converter/anki_generator.py` after the dataclasses:

```python
import re

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
```

- [ ] **Step 2.4 — Run tests to confirm pass**

```bash
python3 -m pytest tests/test_anki_generator.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 2.5 — Commit**

```bash
git add md_converter/anki_generator.py tests/test_anki_generator.py
git commit -m "feat: add segment_sections + unit tests"
```

---

## Task 3 — Category detection

**Files:**
- Modify: `md_converter/anki_generator.py`
- Modify: `tests/test_anki_generator.py`

- [ ] **Step 3.1 — Write failing tests**

Append to `tests/test_anki_generator.py`:

```python
from md_converter.anki_generator import detect_categories


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
```

- [ ] **Step 3.2 — Run tests to confirm failure**

```bash
python3 -m pytest tests/test_anki_generator.py::test_detect_definition_fr -v
```
Expected: `ImportError` — `detect_categories` not defined yet

- [ ] **Step 3.3 — Implement `detect_categories`**

Add to `md_converter/anki_generator.py`:

```python
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
        r'\bcontrairement\s+à\b', r'\balors\s+que\b', r'\bdifférence\b',
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
```

- [ ] **Step 3.4 — Run all tests**

```bash
python3 -m pytest tests/test_anki_generator.py -v
```
Expected: all tests PASS

- [ ] **Step 3.5 — Commit**

```bash
git add md_converter/anki_generator.py tests/test_anki_generator.py
git commit -m "feat: add detect_categories with 16 semantic patterns"
```

---

## Task 4 — Card generation + quality filter

**Files:**
- Modify: `md_converter/anki_generator.py`
- Modify: `tests/test_anki_generator.py`

- [ ] **Step 4.1 — Write failing tests**

Append to `tests/test_anki_generator.py`:

```python
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
    # Should contain at least one definition-type question
    assert any("Définir" in f or "est-ce que" in f for f in fronts)


def test_generate_cards_tags_and_source():
    s = Section(heading="TestSection", level=1, content="Contenu suffisant pour générer une carte.")
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
    # Section with many possible templates
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
```

- [ ] **Step 4.2 — Run tests to confirm failure**

```bash
python3 -m pytest tests/test_anki_generator.py -k "generate_cards or filter_cards or generate_deck" -v
```
Expected: `ImportError` — functions not defined yet

- [ ] **Step 4.3 — Implement templates, card generation, filter and `generate_deck`**

Add to `md_converter/anki_generator.py`:

```python
from collections import defaultdict

_TEMPLATES: dict[str, str] = {
    "what_is":    "Qu'est-ce que {subject} ?",
    "define":     "Définir {subject}",
    "why":        "À quoi sert {subject} ?",
    "how":        "Comment fonctionne {subject} ?",
    "when_use":   "Dans quel cas utilise-t-on {subject} ?",
    "list_what":  "Quels sont les éléments / composants de {subject} ?",
    "steps":      "Quelles sont les étapes pour {subject} ?",
    "difference": "Quelle est la différence entre les concepts de {subject} ?",
    "give_example": "Donner un exemple de {subject}",
    "consequence": "Quelles sont les conséquences de {subject} ?",
    "condition":  "Quelles sont les conditions / hypothèses pour {subject} ?",
    "state_thm":  "Énoncer le théorème / la propriété : {subject}",
    "hypotheses": "Quelles sont les hypothèses de {subject} ?",
    "formula":    "Donner la formule de {subject}",
    "prove_why":  "Justifier / démontrer pourquoi {subject}",
    "who_is":     "Qui est {subject} ?",
    "who_did":    "Qui a créé / fondé {subject} ?",
    "when_event": "Quand {subject} ?",
    "cause_of":   "Quelles sont les causes de {subject} ?",
    "limits":     "Quelles sont les limites / exceptions de {subject} ?",
    "apply_to":   "Dans quels domaines s'applique {subject} ?",
    "recall_key": "Citer les points clés de : {subject}",
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
```

- [ ] **Step 4.4 — Run all generator tests**

```bash
python3 -m pytest tests/test_anki_generator.py -v
```
Expected: all tests PASS

- [ ] **Step 4.5 — Commit**

```bash
git add md_converter/anki_generator.py tests/test_anki_generator.py
git commit -m "feat: add card generation, quality filter, generate_deck"
```

---

## Task 5 — CSV/TXT export (`anki_exporter.py`)

**Files:**
- Create: `md_converter/anki_exporter.py`
- Create: `tests/test_anki_exporter.py`

- [ ] **Step 5.1 — Write failing tests**

```python
# tests/test_anki_exporter.py
import pytest
from pathlib import Path
from md_converter.anki_generator import AnkiCard
from md_converter.anki_exporter import cards_to_csv, cards_to_txt, export_deck, ExportOptions

SAMPLE_CARDS = [
    AnkiCard(
        front="Définir la dérivée",
        back="La dérivée est la limite du taux de variation.",
        card_type="definition",
        tags=["cours", "section:Calcul", "source:maths"],
        source="maths — Calcul",
    ),
    AnkiCard(
        front='Question avec "guillemets"',
        back="Réponse normale.",
        card_type="example",
        tags=["cours"],
        source="maths — Exemples",
    ),
]


def test_csv_default_separator():
    csv_str = cards_to_csv(SAMPLE_CARDS, separator=";")
    lines = csv_str.strip().splitlines()
    assert lines[0].startswith("front;back;")
    assert len(lines) == 3  # header + 2 data rows


def test_csv_comma_separator():
    csv_str = cards_to_csv(SAMPLE_CARDS, separator=",")
    lines = csv_str.strip().splitlines()
    assert "," in lines[0]
    assert ";" not in lines[0]


def test_csv_quotes_escaped():
    csv_str = cards_to_csv(SAMPLE_CARDS, separator=";")
    # The card with "guillemets" in front must have doubled quotes
    assert '""guillemets""' in csv_str or '"question avec ""guillemets"""' in csv_str.lower()


def test_csv_utf8_accents():
    cards = [AnkiCard(front="Définir énergie", back="L'énergie est une capacité à produire du travail.", card_type="definition", tags=[], source="")]
    csv_bytes = cards_to_csv(cards).encode("utf-8")
    assert "Définir".encode("utf-8") in csv_bytes


def test_csv_contains_all_fields():
    csv_str = cards_to_csv(SAMPLE_CARDS[:1])
    assert "dérivée" in csv_str.lower() or "derivee" in csv_str.lower()
    assert "cours" in csv_str
    assert "definition" in csv_str


def test_txt_tab_separator():
    txt_str = cards_to_txt(SAMPLE_CARDS, separator="\t")
    assert "\t" in txt_str
    lines = txt_str.strip().splitlines()
    assert len(lines) == 3  # header + 2 rows


def test_txt_custom_separator():
    txt_str = cards_to_txt(SAMPLE_CARDS, separator="|")
    assert "|" in txt_str


def test_txt_newlines_in_back_removed():
    cards = [AnkiCard(front="Q?", back="Line1\nLine2\nLine3", card_type="x", tags=[], source="")]
    txt_str = cards_to_txt(cards)
    data_line = txt_str.strip().splitlines()[1]
    assert "\n" not in data_line


def test_export_deck_csv_creates_file(tmp_path):
    base = tmp_path / "test"
    opts = ExportOptions(format="csv", separator=";")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    assert len(paths) == 1
    csv_file = tmp_path / "test.anki.csv"
    assert csv_file.exists()
    assert csv_file.stat().st_size > 0


def test_export_deck_txt_creates_file(tmp_path):
    base = tmp_path / "test"
    opts = ExportOptions(format="txt")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    assert len(paths) == 1
    txt_file = tmp_path / "test.anki.txt"
    assert txt_file.exists()


def test_export_deck_both_creates_two_files(tmp_path):
    base = tmp_path / "test"
    opts = ExportOptions(format="both")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    assert len(paths) == 2
    assert (tmp_path / "test.anki.csv").exists()
    assert (tmp_path / "test.anki.txt").exists()


def test_export_deck_empty_cards_no_error(tmp_path):
    base = tmp_path / "empty"
    paths = export_deck([], base, ExportOptions(format="csv"))
    assert len(paths) == 1
    assert (tmp_path / "empty.anki.csv").exists()


def test_export_deck_returns_correct_paths(tmp_path):
    base = tmp_path / "subdir" / "myfile"
    opts = ExportOptions(format="both")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    names = {p.name for p in paths}
    assert "myfile.anki.csv" in names
    assert "myfile.anki.txt" in names
```

- [ ] **Step 5.2 — Run tests to confirm failure**

```bash
python3 -m pytest tests/test_anki_exporter.py -v
```
Expected: `ImportError` — module not found

- [ ] **Step 5.3 — Create `anki_exporter.py`**

```python
# md_converter/anki_exporter.py
from __future__ import annotations
import csv
import io
from dataclasses import dataclass
from pathlib import Path

from md_converter.anki_generator import AnkiCard


@dataclass
class ExportOptions:
    format: str = "csv"     # "csv" | "txt" | "both"
    separator: str = ";"


_COLUMNS = ["front", "back", "tags", "source", "card_type"]


def _tags_str(tags: list[str]) -> str:
    return " ".join(tags)


def cards_to_csv(cards: list[AnkiCard], separator: str = ";") -> str:
    """Render cards to a UTF-8 CSV string, properly escaped."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=separator, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_COLUMNS)
    for card in cards:
        writer.writerow([card.front, card.back, _tags_str(card.tags), card.source, card.card_type])
    return buf.getvalue()


def cards_to_txt(cards: list[AnkiCard], separator: str = "\t") -> str:
    """Render cards to a TXT string. Newlines inside fields are replaced by spaces."""
    buf = io.StringIO()
    buf.write(separator.join(_COLUMNS) + "\n")
    for card in cards:
        row = [
            card.front.replace("\n", " "),
            card.back.replace("\n", " "),
            _tags_str(card.tags),
            card.source,
            card.card_type,
        ]
        buf.write(separator.join(row) + "\n")
    return buf.getvalue()


def export_deck(
    cards: list[AnkiCard],
    base_path: Path,
    options: ExportOptions | None = None,
) -> list[Path]:
    """Write deck files from base_path stem. Returns list of created paths.

    base_path is the file stem (no extension).
    Creates <base_path>.anki.csv and/or <base_path>.anki.txt.
    """
    if options is None:
        options = ExportOptions()

    base_path = Path(base_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []

    if options.format in ("csv", "both"):
        csv_path = base_path.parent / (base_path.name + ".anki.csv")
        csv_path.write_text(cards_to_csv(cards, separator=options.separator), encoding="utf-8")
        created.append(csv_path)

    if options.format in ("txt", "both"):
        txt_path = base_path.parent / (base_path.name + ".anki.txt")
        txt_path.write_text(cards_to_txt(cards), encoding="utf-8")
        created.append(txt_path)

    return created
```

- [ ] **Step 5.4 — Run all exporter tests**

```bash
python3 -m pytest tests/test_anki_exporter.py -v
```
Expected: all tests PASS

- [ ] **Step 5.5 — Run full test suite (no regression)**

```bash
python3 -m pytest tests/ -v
```
Expected: all tests PASS

- [ ] **Step 5.6 — Commit**

```bash
git add md_converter/anki_exporter.py tests/test_anki_exporter.py
git commit -m "feat: add anki_exporter — CSV/TXT export with quality escaping"
```

---

## Task 6 — Integrate Anki into `convert.py`

**Files:**
- Modify: `convert.py`

- [ ] **Step 6.1 — Add `streamlit` to `pyproject.toml`**

In `pyproject.toml`, add `"streamlit>=1.35"` to `dependencies`:

```toml
dependencies = [
    "PyMuPDF>=1.23.0",
    "pytesseract>=0.3.10",
    "Pillow>=10.0",
    "tiktoken>=0.7.0",
    "click>=8.1",
    "rich>=13.7",
    "streamlit>=1.35",
]
```

Then reinstall:

```bash
pip install -e .
```

- [ ] **Step 6.2 — Add helpers to `convert.py`**

After the existing `_is_already_converted` function, add:

```python
def _output_anki_base_path(pdf_path: Path) -> Path:
    """Map input/a/b/doc.pdf → output/a/b/doc (no extension, for Anki files)."""
    relative = pdf_path.relative_to(INPUT_DIR)
    return OUTPUT_DIR / relative.with_suffix("")


def _anki_already_exists(base_path: Path, fmt: str) -> bool:
    """Return True if requested Anki output file(s) exist and are non-empty."""
    csv_path = base_path.parent / (base_path.name + ".anki.csv")
    txt_path = base_path.parent / (base_path.name + ".anki.txt")
    if fmt == "csv":
        return csv_path.exists() and csv_path.stat().st_size > 0
    if fmt == "txt":
        return txt_path.exists() and txt_path.stat().st_size > 0
    return (csv_path.exists() and csv_path.stat().st_size > 0
            and txt_path.exists() and txt_path.stat().st_size > 0)


def _generate_anki_for_pdf(
    pdf_path: Path,
    md_was_skipped: bool,
    args,
    verbose: bool,
) -> tuple[str, int, int]:
    """Generate Anki deck for one PDF. Returns (status, cards_count, filtered_count).

    status: 'ok' | 'skip'
    """
    from md_converter.anki_generator import generate_deck, GeneratorOptions
    from md_converter.anki_exporter import export_deck, ExportOptions

    base_path = _output_anki_base_path(pdf_path)
    md_path = _output_md_path(pdf_path)

    if md_was_skipped and not args.anki_regenerate:
        return "skip", 0, 0
    if not args.force and not args.anki_regenerate and _anki_already_exists(base_path, args.anki_format):
        return "skip", 0, 0

    markdown = md_path.read_text(encoding="utf-8")
    gen_opts = GeneratorOptions(
        max_cards_per_section=args.anki_max_cards,
        min_answer_length=args.anki_min_length,
        source_name=pdf_path.stem,
    )
    cards, n_filtered = generate_deck(markdown, pdf_path.stem, gen_opts)

    export_opts = ExportOptions(format=args.anki_format, separator=args.anki_separator)
    created = export_deck(cards, base_path, export_opts)

    if verbose:
        for p in created:
            console.print(f"    anki → {p.relative_to(OUTPUT_DIR)}")

    return "ok", len(cards), n_filtered
```

- [ ] **Step 6.3 — Add CLI flags to `main()`**

In `main()`, after the existing `parser.add_argument("--verbose"...)` block, add:

```python
anki = parser.add_argument_group("Anki deck generation")
anki.add_argument(
    "--anki", action="store_true",
    help="Generate an Anki deck from each converted Markdown file.",
)
anki.add_argument(
    "--anki-format", choices=["csv", "txt", "both"], default="csv",
    dest="anki_format",
    help="Anki export format (default: csv).",
)
anki.add_argument(
    "--anki-separator", default=";", dest="anki_separator", metavar="SEP",
    help="Field separator for CSV/TXT (default: ;).",
)
anki.add_argument(
    "--anki-regenerate", action="store_true", dest="anki_regenerate",
    help="Regenerate deck even if Markdown was skipped (already converted).",
)
anki.add_argument(
    "--anki-max-cards", type=int, default=5, dest="anki_max_cards", metavar="N",
    help="Maximum cards per section (default: 5).",
)
anki.add_argument(
    "--anki-min-length", type=int, default=20, dest="anki_min_length", metavar="N",
    help="Minimum answer length in characters (default: 20).",
)
```

- [ ] **Step 6.4 — Update main loop**

Replace the per-PDF loop body in `main()` with:

```python
    counts = {"ok": 0, "skip": 0, "error": 0}
    anki_counts = {"ok": 0, "skip": 0, "error": 0}

    for pdf_path in pdfs:
        rel = pdf_path.relative_to(INPUT_DIR)
        md_path = _output_md_path(pdf_path)

        try:
            result = _convert_one(pdf_path, mode=mode, force=args.force, verbose=args.verbose)
        except Exception as exc:
            console.print(f"  [red][ERROR][/red] {rel}  →  {exc}")
            counts["error"] += 1
            continue

        if result == "skip":
            console.print(f"  [dim][SKIP][/dim]  {rel}  (already converted: {md_path})")
            counts["skip"] += 1
        else:
            ratio_pct = ""
            try:
                import json
                data = json.loads(md_path.with_suffix(".report.json").read_text())
                reduction = round((1 - data["compression_ratio"]) * 100, 1)
                ratio_pct = f"  ({data['tokens_before']}→{data['tokens_after']} tokens, {reduction:+.1f}%)"
            except Exception:
                pass
            console.print(f"  [green][OK][/green]    {rel}  →  {md_path.relative_to(OUTPUT_DIR)}{ratio_pct}")
            counts["ok"] += 1

        if args.anki:
            try:
                anki_status, n_cards, n_filtered = _generate_anki_for_pdf(
                    pdf_path, md_was_skipped=(result == "skip"), args=args, verbose=args.verbose,
                )
            except Exception as exc:
                console.print(f"  [red][ANKI ERROR][/red] {rel}  →  {exc}")
                anki_counts["error"] += 1
                continue

            if anki_status == "skip":
                console.print(f"  [dim][ANKI SKIP][/dim] {rel}")
                anki_counts["skip"] += 1
            else:
                console.print(
                    f"  [cyan][ANKI][/cyan]   {rel}  →  "
                    f"{n_cards} cards, {n_filtered} filtered"
                )
                anki_counts["ok"] += 1
```

- [ ] **Step 6.5 — Update summary table**

Replace the summary table block with:

```python
    console.print()
    t = Table(title="Conversion Summary")
    t.add_column("Status", style="bold")
    t.add_column("MD")
    if args.anki:
        t.add_column("Anki")
    t.add_row("[green]Converted / Generated[/green]", str(counts["ok"]),
              *(([str(anki_counts["ok"])]) if args.anki else []))
    t.add_row("[dim]Skipped[/dim]", str(counts["skip"]),
              *(([str(anki_counts["skip"])]) if args.anki else []))
    t.add_row("[red]Errors[/red]", str(counts["error"]),
              *(([str(anki_counts["error"])]) if args.anki else []))
    console.print(t)

    return 1 if (counts["error"] > 0 or anki_counts["error"] > 0) else 0
```

- [ ] **Step 6.6 — Smoke-test the CLI**

```bash
python3 convert.py --help
```
Expected: `--anki`, `--anki-format`, `--anki-separator`, `--anki-regenerate`, `--anki-max-cards`, `--anki-min-length` all appear.

```bash
python3 convert.py --anki --anki-format both --verbose
```
Expected: runs without error, `[ANKI]` lines appear, `.anki.csv` and `.anki.txt` created under `output/`.

```bash
python3 convert.py --anki
```
Expected: all `[ANKI SKIP]` lines (idempotence).

```bash
python3 convert.py --anki --anki-regenerate
```
Expected: `[ANKI]` lines again (regenerated from existing `.md`).

- [ ] **Step 6.7 — Commit**

```bash
git add convert.py pyproject.toml
git commit -m "feat: integrate Anki generation into convert.py with CLI flags"
```

---

## Task 7 — Integration tests

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 7.1 — Add integration tests**

Append to `tests/test_integration.py`:

```python
from md_converter.anki_generator import generate_deck, GeneratorOptions
from md_converter.anki_exporter import export_deck, ExportOptions


def test_pdf_to_anki_produces_cards(native_pdf_path):
    """Full pipeline: PDF → Markdown → Anki cards (non-empty)."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    cards, n_filtered = generate_deck(md, "native_test")
    assert len(cards) > 0, "Expected at least one card from a real PDF"
    assert isinstance(n_filtered, int)
    for card in cards:
        assert card.front.strip(), "Card front must not be empty"
        assert len(card.back.strip()) >= 20, "Card back too short"


def test_anki_export_csv_importable(native_pdf_path, tmp_path):
    """CSV export must be parseable with csv.reader using default separator."""
    import csv as csv_mod
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    cards, _ = generate_deck(md, "test")
    base = tmp_path / "export"
    paths = export_deck(cards, base, ExportOptions(format="csv", separator=";"))
    assert len(paths) == 1
    content = paths[0].read_text(encoding="utf-8")
    rows = list(csv_mod.reader(content.splitlines(), delimiter=";"))
    assert rows[0] == ["front", "back", "tags", "source", "card_type"]
    assert len(rows) > 1


def test_anki_cards_deterministic(native_pdf_path):
    """Two generate_deck calls on the same markdown must return identical results."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    cards1, _ = generate_deck(md, "test")
    cards2, _ = generate_deck(md, "test")
    assert [(c.front, c.back) for c in cards1] == [(c.front, c.back) for c in cards2]


def test_anki_respects_max_cards_per_section(native_pdf_path):
    """max_cards_per_section=1 must yield at most 1 card per section."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    opts = GeneratorOptions(max_cards_per_section=1, source_name="test")
    cards, _ = generate_deck(md, "test", opts)
    from collections import Counter
    counts = Counter(c.source for c in cards)
    for src, count in counts.items():
        assert count <= 1, f"Section '{src}' has {count} cards, expected ≤ 1"
```

- [ ] **Step 7.2 — Run integration tests**

```bash
python3 -m pytest tests/test_integration.py -v
```
Expected: all PASS (including new 4 tests)

- [ ] **Step 7.3 — Run full suite**

```bash
python3 -m pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 7.4 — Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add PDF→Anki integration tests"
```

---

## Task 8 — Streamlit frontend

**Files:**
- Create: `app.py`
- Create: `.streamlit/config.toml`

- [ ] **Step 8.1 — Create `.streamlit/config.toml`**

```toml
[theme]
base = "dark"
backgroundColor = "#0f0f14"
secondaryBackgroundColor = "#1a1a24"
textColor = "#e8e6e0"
primaryColor = "#f0a500"
font = "sans serif"

[server]
headless = true
port = 8501
```

- [ ] **Step 8.2 — Create `app.py`**

```python
#!/usr/bin/env python3
"""app.py — Streamlit frontend: PDF → Markdown + Anki deck (localhost).

Run with: streamlit run app.py
"""
from __future__ import annotations

import time
import tempfile
from pathlib import Path

import streamlit as st

from md_converter.pipeline import convert_pdf
from md_converter.optimizer import Mode
from md_converter.anki_generator import generate_deck, GeneratorOptions
from md_converter.anki_exporter import cards_to_csv, cards_to_txt, ExportOptions

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PDF → Anki",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS injection ─────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }

[data-testid="stApp"],
[data-testid="stAppViewContainer"],
.main .block-container {
    background-color: #0f0f14 !important;
    color: #e8e6e0 !important;
    font-family: 'IBM Plex Sans', sans-serif;
    max-width: 1400px;
}

.page-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 700;
    color: #f0a500;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}

.page-subtitle {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.82rem;
    font-weight: 300;
    color: #5a5a6a;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #2a2a38;
}

.section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #5a5a6a;
    margin-bottom: 0.75rem;
}

.stButton > button {
    background: linear-gradient(135deg, #f0a500 0%, #d09000 100%) !important;
    color: #0f0f14 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 3px !important;
    padding: 0.7rem 2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 16px rgba(240,165,0,0.2) !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 28px rgba(240,165,0,0.4) !important;
}

[data-testid="stFileUploader"] {
    background: #1a1a24;
    border: 1px dashed #3a3a4a;
    border-radius: 8px;
    padding: 1rem;
    transition: border-color 0.25s;
}
[data-testid="stFileUploader"]:hover { border-color: #f0a500; }

.stats-row {
    display: flex;
    gap: 1px;
    border: 1px solid #2a2a38;
    border-radius: 6px;
    overflow: hidden;
    background: #2a2a38;
    margin: 1.5rem 0;
}
.stat-block {
    flex: 1;
    background: #1a1a24;
    padding: 1.1rem 0.75rem;
    text-align: center;
}
.stat-number {
    font-family: 'Playfair Display', serif;
    font-size: 1.8rem;
    color: #f0a500;
    line-height: 1;
    margin-bottom: 0.25rem;
}
.stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #4a4a5a;
    text-transform: uppercase;
    letter-spacing: 0.13em;
}

.markdown-box {
    background: #0c0c11;
    border: 1px solid #2a2a38;
    border-radius: 6px;
    padding: 1.25rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    line-height: 1.75;
    color: #9a9890;
    max-height: 460px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

.anki-card {
    background: #1a1a24;
    border: 1px solid #252530;
    border-left: 3px solid #2a2a38;
    border-radius: 4px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.55rem;
    transition: all 0.18s ease;
}
.anki-card:hover {
    border-color: #353545;
    border-left-color: #f0a500;
    transform: translateX(3px);
}
.card-front {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 500;
    font-size: 0.88rem;
    color: #dddbd5;
    margin-bottom: 0.4rem;
}
.card-back {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #6a6a7a;
    line-height: 1.6;
    border-top: 1px solid #252530;
    padding-top: 0.45rem;
    margin-top: 0.2rem;
}

.badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    padding: 0.1rem 0.45rem;
    border-radius: 2px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-right: 0.5rem;
    vertical-align: middle;
}
.badge-definition  { background: #0a2040; color: #4a9eff; border: 1px solid #1a4070; }
.badge-theorem     { background: #300a18; color: #ff5070; border: 1px solid #601828; }
.badge-property    { background: #300a18; color: #ff5070; border: 1px solid #601828; }
.badge-formula     { background: #1a0830; color: #c040ff; border: 1px solid #400860; }
.badge-method      { background: #082018; color: #40df80; border: 1px solid #185030; }
.badge-enumeration { background: #281500; color: #f0a500; border: 1px solid #503000; }
.badge-default     { background: #181820; color: #707080; border: 1px solid #282838; }

[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    border: 1px solid #2a2a38 !important;
    color: #9a9890 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.78rem !important;
    padding: 0.45rem 1rem !important;
    border-radius: 3px !important;
    transition: all 0.18s ease !important;
    width: 100% !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #f0a500 !important;
    color: #f0a500 !important;
}

[data-testid="stRadio"] label,
[data-testid="stSlider"] label {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    color: #5a5a6a !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

div[data-testid="stProgress"] > div { background: #1a1a24 !important; }
div[data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #f0a500, #ffb830) !important; }
"""

st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown('<h1 class="page-title">PDF → Anki</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="page-subtitle">Conversion PDF · Génération de cartes de révision</p>',
    unsafe_allow_html=True,
)

# ── Upload + Options ──────────────────────────────────────────────────────────

col_upload, col_opts = st.columns([1.3, 1])

with col_upload:
    st.markdown('<p class="section-label">Fichier PDF</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Déposer un fichier PDF",
        type=["pdf"],
        label_visibility="collapsed",
    )

with col_opts:
    st.markdown('<p class="section-label">Options</p>', unsafe_allow_html=True)
    mode_choice = st.radio("Mode de conversion", ["Fidelity", "Compact"], horizontal=True)
    format_choice = st.radio("Format export Anki", ["CSV", "TXT", "Les deux"], horizontal=True)
    max_cards = st.slider("Max cartes / section", min_value=1, max_value=15, value=5)
    min_length = st.slider("Longueur min. réponse (caractères)", min_value=5, max_value=100, value=20)
    st.markdown("<br>", unsafe_allow_html=True)
    convert_btn = st.button("Convertir", use_container_width=True)

# ── Conversion ────────────────────────────────────────────────────────────────

_TYPE_BADGE: dict[str, str] = {
    "definition": "badge-definition",
    "theorem": "badge-theorem",
    "property": "badge-property",
    "formula": "badge-formula",
    "method": "badge-method",
    "enumeration": "badge-enumeration",
}

if uploaded_file and convert_btn:
    t_start = time.time()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    progress = st.progress(0, text="Détection du type de PDF…")

    try:
        md_mode = Mode.FIDELITY if mode_choice == "Fidelity" else Mode.COMPACT
        progress.progress(15, text="Extraction du contenu…")
        markdown, report = convert_pdf(tmp_path, mode=md_mode)

        progress.progress(55, text="Nettoyage et structuration…")
        source_name = Path(uploaded_file.name).stem
        gen_opts = GeneratorOptions(
            max_cards_per_section=max_cards,
            min_answer_length=min_length,
            source_name=source_name,
        )

        progress.progress(70, text="Génération des cartes Anki…")
        cards, filtered_count = generate_deck(markdown, source_name, gen_opts)

        progress.progress(90, text="Préparation des exports…")
        fmt_map = {"CSV": "csv", "TXT": "txt", "Les deux": "both"}
        fmt = fmt_map[format_choice]
        csv_str = cards_to_csv(cards) if fmt in ("csv", "both") else ""
        txt_str = cards_to_txt(cards) if fmt in ("txt", "both") else ""

        elapsed = time.time() - t_start
        progress.progress(100, text="Terminé !")
        time.sleep(0.35)
        progress.empty()

    except Exception as exc:
        progress.empty()
        st.error(f"Erreur de conversion : {exc}")
        st.stop()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # ── Stats ──────────────────────────────────────────────────────────────────

    st.markdown(f"""
<div class="stats-row">
  <div class="stat-block">
    <div class="stat-number">{report.total_pages}</div>
    <div class="stat-label">Pages</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{report.sections_detected}</div>
    <div class="stat-label">Sections</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{report.tokens_after}</div>
    <div class="stat-label">Tokens</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{len(cards)}</div>
    <div class="stat-label">Cartes</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{filtered_count}</div>
    <div class="stat-label">Filtrées</div>
  </div>
  <div class="stat-block">
    <div class="stat-number">{elapsed:.1f}s</div>
    <div class="stat-label">Durée</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Results ───────────────────────────────────────────────────────────────

    col_md, col_anki = st.columns([1, 1])

    with col_md:
        st.markdown('<p class="section-label">Aperçu Markdown</p>', unsafe_allow_html=True)
        preview = markdown[:3000]
        if len(markdown) > 3000:
            preview += "\n\n[… tronqué pour l'aperçu]"
        st.markdown(f'<div class="markdown-box">{preview}</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            "↓ Télécharger .md",
            data=markdown.encode("utf-8"),
            file_name=f"{source_name}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col_anki:
        st.markdown(
            f'<p class="section-label">Cartes Anki — {len(cards)} générées, {filtered_count} filtrées</p>',
            unsafe_allow_html=True,
        )

        cards_html = ""
        display_cards = cards[:12]
        for card in display_cards:
            badge_cls = _TYPE_BADGE.get(card.card_type, "badge-default")
            back_preview = card.back[:160].replace("\n", " ")
            if len(card.back) > 160:
                back_preview += "…"
            cards_html += f"""<div class="anki-card">
  <span class="badge {badge_cls}">{card.card_type}</span>
  <div class="card-front">{card.front}</div>
  <div class="card-back">{back_preview}</div>
</div>"""

        if len(cards) > 12:
            cards_html += (
                f'<p style="color:#3a3a4a;font-size:0.72rem;text-align:center;'
                f'font-family:JetBrains Mono,monospace;padding-top:0.5rem;">'
                f'+{len(cards) - 12} cartes supplémentaires dans le fichier</p>'
            )

        st.markdown(cards_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        dl1, dl2 = st.columns(2)
        if csv_str:
            with dl1:
                st.download_button(
                    "↓ .anki.csv",
                    data=csv_str.encode("utf-8"),
                    file_name=f"{source_name}.anki.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        if txt_str:
            with dl2:
                st.download_button(
                    "↓ .anki.txt",
                    data=txt_str.encode("utf-8"),
                    file_name=f"{source_name}.anki.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
```

- [ ] **Step 8.3 — Launch and manually verify**

```bash
streamlit run app.py
```

Open `http://localhost:8501`. Verify:
- Dark background `#0f0f14`, gold title in Playfair Display
- File upload zone visible
- Upload a PDF from `input/`, click "Convertir"
- Progress bar appears with named steps
- Stats row appears (pages, sections, tokens, cards, filtered, durée)
- Left column: Markdown preview in monospace dark box + download button
- Right column: cards with colored type badges + download buttons
- Download `.md` → opens in editor, valid Markdown
- Download `.anki.csv` → opens in spreadsheet, `front;back;tags;source;card_type` columns

- [ ] **Step 8.4 — Commit**

```bash
git add app.py .streamlit/config.toml
git commit -m "feat: add Streamlit frontend with editorial dark theme"
```

---

## Task 9 — Documentation

**Files:**
- Create: `docs/ANKI_IMPORT_GUIDE.md`
- Modify: `README.md`

- [ ] **Step 9.1 — Create `docs/ANKI_IMPORT_GUIDE.md`**

```markdown
# Guide d'import Anki

Ce guide explique comment importer les fichiers `.anki.csv` ou `.anki.txt`
générés par md-converter dans Anki Desktop.

## Prérequis

- [Anki Desktop](https://apps.ankiweb.net/) installé (version 2.1+)

## Import d'un fichier CSV

1. Ouvrir Anki Desktop
2. Menu **Fichier → Importer…** (ou `Ctrl+I` / `Cmd+I`)
3. Sélectionner votre fichier `.anki.csv`
4. Dans la fenêtre d'import :
   - **Type de note** : Basic
   - **Deck** : choisir ou créer un deck (ex: `Cours > Maths`)
   - **Séparateur de champs** : Point-virgule (`;`)
   - **Encodage** : UTF-8
   - Cocher **Autoriser le HTML dans les champs**
5. Vérifier le mapping des colonnes :
   - Colonne 1 (`front`) → **Recto**
   - Colonne 2 (`back`) → **Verso**
   - Colonnes 3-5 (tags, source, card_type) → **Ignorer** ou mapper vers Tag
6. Cliquer **Importer**

## Import d'un fichier TXT

Même procédure, avec **Séparateur de champs** : Tabulation.

## Conseils

- Créez un deck par matière pour mieux organiser vos révisions.
- Les tags `section:*` et `source:*` permettent de filtrer par chapitre dans le navigateur Anki.
- Après import, utilisez **Outils → Vérifier la base de données** si vous constatez des anomalies.

## Réglages recommandés pour les nouveaux decks

| Paramètre | Valeur recommandée |
|---|---|
| Nouvelles cartes / jour | 20 |
| Révisions maximales / jour | 200 |
| Intervalle de graduation | 1 jour |
| Multiplicateur d'intervalle | 2.5 |
```

- [ ] **Step 9.2 — Update `README.md`**

Add a new section **Anki Deck Generation** after the existing **Options** table, and a section **Streamlit UI** after it:

```markdown
---

## Anki Deck Generation

Generate Anki-importable flashcards from converted Markdown:

```bash
# Convert PDF → Markdown + Anki deck (CSV by default)
python3 convert.py --anki

# Both CSV and TXT
python3 convert.py --anki --anki-format both

# Force regeneration on already-converted files
python3 convert.py --anki --anki-regenerate

# Tune card quality
python3 convert.py --anki --anki-max-cards 7 --anki-min-length 30
```

### Anki options

| Option | Default | Description |
|---|---|---|
| `--anki` | off | Enable Anki deck generation |
| `--anki-format csv\|txt\|both` | `csv` | Export format |
| `--anki-separator SEP` | `;` | Field separator |
| `--anki-regenerate` | off | Regenerate deck even if MD was skipped |
| `--anki-max-cards N` | `5` | Max cards per section |
| `--anki-min-length N` | `20` | Min answer length (chars) |

Output files:
```
output/<subpath>/<filename>.anki.csv
output/<subpath>/<filename>.anki.txt
```

See [docs/ANKI_IMPORT_GUIDE.md](docs/ANKI_IMPORT_GUIDE.md) for step-by-step Anki import instructions.

---

## Streamlit UI (localhost)

A browser interface for one-off conversions:

```bash
streamlit run app.py
# → http://localhost:8501
```

Upload a PDF, choose options, click **Convertir**. Download the `.md` and `.anki.csv`/`.anki.txt` directly from the browser.
```

- [ ] **Step 9.3 — Run full test suite one last time**

```bash
python3 -m pytest tests/ -v
```
Expected: all tests PASS

- [ ] **Step 9.4 — Idempotence check**

```bash
python3 convert.py --anki
# Expected: all [SKIP] / [ANKI SKIP]
python3 convert.py --anki --force
# Expected: all [OK] / [ANKI] (reconverted)
python3 convert.py --anki
# Expected: all [SKIP] / [ANKI SKIP] again
```

- [ ] **Step 9.5 — Commit**

```bash
git add docs/ANKI_IMPORT_GUIDE.md README.md
git commit -m "docs: add ANKI_IMPORT_GUIDE and update README with Anki + Streamlit sections"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| PDF → MD + Anki in one run | Tasks 4, 6 |
| Skip MD but regenerate Anki (`--anki-regenerate`) | Task 6, `_generate_anki_for_pdf` |
| `output/<subpath>/<filename>.anki.csv/.txt` | Task 5, `export_deck` |
| 15+ semantic categories | Task 3, `_PATTERNS` |
| 20+ question templates | Task 4, `_TEMPLATES` |
| Multi-angle cards per section | Task 4, `_select_templates` |
| Quality filters (empty, short, trivial, dedup) | Task 4, `filter_cards` |
| Max cards per section | Task 4, `_apply_max_per_section` |
| CSV + TXT export with configurable separator | Task 5 |
| All 6 CLI flags | Task 6 |
| Idempotence rules (all 4 rows of spec table) | Task 6, `_anki_already_exists` |
| Unit tests: generator | Task 2, 3, 4 |
| Unit tests: exporter | Task 5 |
| Integration tests | Task 7 |
| Streamlit frontend | Task 8 |
| Editorial dark theme (Playfair + IBM Plex + JetBrains Mono) | Task 8 |
| Stats bar, type badges, download buttons | Task 8 |
| `docs/ANKI_IMPORT_GUIDE.md` | Task 9 |
| README update | Task 9 |
| `streamlit` added to `pyproject.toml` | Task 6 step 6.1 |
| No pipeline regression | Task 5 step 5.5, Task 7 step 7.3 |

**Placeholder scan:** No TBD, no TODO, no incomplete code blocks.

**Type consistency:**
- `AnkiCard` defined in Task 1, used in Tasks 4, 5, 7, 8 — consistent field names throughout.
- `GeneratorOptions` defined in Task 1, used in Tasks 4, 6, 7 — consistent.
- `ExportOptions` defined in Task 5, used in Tasks 6, 7, 8 — consistent.
- `segment_sections` → `detect_categories` → `generate_cards_for_section` → `filter_cards` → `generate_deck` chain matches across all tasks.
- `export_deck(cards, base_path, options)` signature consistent in Tasks 5, 6, 7.

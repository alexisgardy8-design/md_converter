from __future__ import annotations
import re
from collections import Counter
from md_converter.extractor import Block

_PAGE_NUMBER_RE = re.compile(
    r"^[\s\-–—]*"
    r"(?:page\s*)?"
    r"\d{1,4}"
    r"[\s\-–—]*$",
    re.IGNORECASE,
)


def is_page_number(text: str) -> bool:
    """Return True if text looks like a standalone page number."""
    return bool(_PAGE_NUMBER_RE.match(text.strip()))


def detect_repeated_noise(
    pages_blocks: list[list[Block]],
    min_pages: int = 2,
) -> set[str]:
    """Find text that appears on >= min_pages pages.

    These are likely headers or footers.
    """
    text_page_count: Counter = Counter()
    total_pages = len(pages_blocks)

    if total_pages < min_pages:
        return set()

    for page_blocks in pages_blocks:
        seen_on_page: set[str] = set()
        for block in page_blocks:
            key = block.text.strip()
            if key and key not in seen_on_page:
                text_page_count[key] += 1
                seen_on_page.add(key)

    threshold = max(min_pages, total_pages * 0.4)
    return {text for text, count in text_page_count.items() if count >= threshold}


def clean_blocks(
    pages_blocks: list[list[Block]],
    noise_min_pages: int = 2,
) -> list[list[Block]]:
    """Remove noise blocks (repeated headers/footers, page numbers) from all pages."""
    noise = detect_repeated_noise(pages_blocks, min_pages=noise_min_pages)

    cleaned: list[list[Block]] = []
    for page_blocks in pages_blocks:
        page_clean: list[Block] = []
        for block in page_blocks:
            stripped = block.text.strip()
            if not stripped:
                continue
            if stripped in noise:
                continue
            if is_page_number(stripped):
                continue
            page_clean.append(block)
        cleaned.append(page_clean)
    return cleaned

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


def _block_lines(block: Block) -> list[str]:
    """Return non-empty stripped lines from a block."""
    return [l.strip() for l in block.text.split("\n") if l.strip()]


def detect_repeated_noise(
    pages_blocks: list[list[Block]],
    min_pages: int = 2,
) -> set[str]:
    """Find lines that appear on >= min_pages pages.

    Works at line level to catch headers that PyMuPDF merges with adjacent text.
    """
    line_page_count: Counter = Counter()
    total_pages = len(pages_blocks)

    if total_pages < min_pages:
        return set()

    for page_blocks in pages_blocks:
        seen_on_page: set[str] = set()
        for block in page_blocks:
            for line in _block_lines(block):
                if line and line not in seen_on_page:
                    line_page_count[line] += 1
                    seen_on_page.add(line)

    threshold = max(min_pages, total_pages * 0.4)
    return {line for line, count in line_page_count.items() if count >= threshold}


def clean_blocks(
    pages_blocks: list[list[Block]],
    noise_min_pages: int = 2,
) -> list[list[Block]]:
    """Remove noise (repeated headers/footers, page numbers) from all pages.

    For multi-line blocks, strips noise lines rather than discarding the whole block.
    """
    noise = detect_repeated_noise(pages_blocks, min_pages=noise_min_pages)

    cleaned: list[list[Block]] = []
    for page_blocks in pages_blocks:
        page_clean: list[Block] = []
        for block in page_blocks:
            lines = _block_lines(block)
            # Filter out noise lines and page numbers at line level
            kept = [
                l for l in lines
                if l not in noise and not is_page_number(l)
            ]
            if not kept:
                continue
            # Rebuild block text from kept lines
            import dataclasses
            new_block = dataclasses.replace(block, text="\n".join(kept))
            page_clean.append(new_block)
        cleaned.append(page_clean)
    return cleaned

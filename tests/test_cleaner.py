from md_converter.cleaner import (
    detect_repeated_noise,
    is_page_number,
    clean_blocks,
)
from md_converter.extractor import Block


def _block(text: str, page: int = 0, y: float = 100.0) -> Block:
    return Block(
        text=text,
        bbox=(72, y, 500, y + 20),
        page_num=page,
        font_size=10,
        is_bold=False,
        is_italic=False,
    )


def test_detect_repeated_noise():
    pages_blocks = [
        [_block("Company Name", page=0, y=10), _block("Content page 1", page=0, y=100)],
        [_block("Company Name", page=1, y=10), _block("Content page 2", page=1, y=100)],
        [_block("Company Name", page=2, y=10), _block("Content page 3", page=2, y=100)],
    ]
    noise = detect_repeated_noise(pages_blocks, min_pages=2)
    assert "Company Name" in noise


def test_non_repeated_not_noise():
    pages_blocks = [
        [_block("Unique content A", page=0), _block("More A", page=0)],
        [_block("Unique content B", page=1), _block("More B", page=1)],
    ]
    noise = detect_repeated_noise(pages_blocks, min_pages=2)
    assert "Unique content A" not in noise


def test_is_page_number():
    assert is_page_number("3")
    assert is_page_number("- 12 -")
    assert is_page_number("Page 5")
    assert is_page_number("  42  ")
    assert not is_page_number("Chapter 3 Introduction")
    assert not is_page_number("The 3 pillars of design")
    assert not is_page_number("Figure 12: Results")


def test_clean_blocks_removes_noise():
    pages_blocks = [
        [_block("Header", page=0, y=5), _block("Real content", page=0, y=100)],
        [_block("Header", page=1, y=5), _block("More content", page=1, y=100)],
        [_block("Header", page=2, y=5), _block("Even more", page=2, y=100)],
    ]
    cleaned = clean_blocks(pages_blocks)
    for page in cleaned:
        texts = [b.text for b in page]
        assert "Header" not in texts


def test_clean_blocks_removes_page_numbers():
    pages_blocks = [
        [_block("Content", page=0), _block("1", page=0, y=800)],
        [_block("More", page=1), _block("2", page=1, y=800)],
        [_block("Even more", page=2), _block("3", page=2, y=800)],
    ]
    cleaned = clean_blocks(pages_blocks)
    for page in cleaned:
        texts = [b.text.strip() for b in page]
        assert "1" not in texts
        assert "2" not in texts
        assert "3" not in texts


def test_single_page_no_noise_removal():
    """Only 1 page: nothing should be treated as repeated noise."""
    pages_blocks = [
        [_block("Header", page=0), _block("Content", page=0)],
    ]
    noise = detect_repeated_noise(pages_blocks, min_pages=2)
    assert len(noise) == 0

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import fitz  # PyMuPDF

TEXT_CHARS_THRESHOLD = 50  # chars per page to consider it text


class PdfType(Enum):
    TEXT = "text"
    SCAN = "scan"
    MIXED = "mixed"


@dataclass
class DetectionResult:
    pdf_type: PdfType
    total_pages: int
    text_pages: int
    scan_pages: int
    chars_per_page: list[int]


def classify_pdf(path: str) -> DetectionResult:
    """Open a PDF and classify each page as text or scan."""
    doc = fitz.open(path)
    chars_per_page: list[int] = []

    for page in doc:
        text = page.get_text("text")
        chars_per_page.append(len(text.strip()))

    doc.close()

    text_pages = sum(1 for c in chars_per_page if c >= TEXT_CHARS_THRESHOLD)
    scan_pages = sum(1 for c in chars_per_page if c < TEXT_CHARS_THRESHOLD)
    total = len(chars_per_page)

    if scan_pages == 0:
        pdf_type = PdfType.TEXT
    elif text_pages == 0:
        pdf_type = PdfType.SCAN
    else:
        pdf_type = PdfType.MIXED

    return DetectionResult(
        pdf_type=pdf_type,
        total_pages=total,
        text_pages=text_pages,
        scan_pages=scan_pages,
        chars_per_page=chars_per_page,
    )

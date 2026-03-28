"""Generate test PDFs for unit and integration tests."""
from pathlib import Path
import fitz

FIXTURES_DIR = Path(__file__).parent


def create_native_pdf() -> Path:
    """Create a structured text PDF with headings, a list, and repeated header/footer noise."""
    out = FIXTURES_DIR / "native.pdf"
    doc = fitz.open()

    # ── Page 1 ────────────────────────────────────────────────────────────────
    page1 = doc.new_page()

    # Repeated header (noise)
    page1.insert_text((72, 30), "ACME Corp", fontsize=9)

    # Title
    page1.insert_text(
        (72, 60), "Annual Report 2024", fontsize=24, fontname="Helvetica-Bold"
    )

    # Section heading
    page1.insert_text(
        (72, 110), "1. Executive Summary", fontsize=16, fontname="Helvetica-Bold"
    )

    # Body paragraph
    body = (
        "This document presents the financial results and operational highlights "
        "for the fiscal year 2024. Revenue grew by 12% compared to the prior year."
    )
    page1.insert_text((72, 140), body, fontsize=12)

    # Bullet list
    page1.insert_text(
        (72, 200), "Key Achievements:", fontsize=14, fontname="Helvetica-Bold"
    )
    bullets = [
        "• Launched three new product lines",
        "• Expanded to five new markets",
        "• Reduced operating costs by 8%",
    ]
    y = 225
    for b in bullets:
        page1.insert_text((80, y), b, fontsize=12)
        y += 20

    # Page number (noise)
    page1.insert_text((290, 800), "1", fontsize=9)

    # ── Page 2 ────────────────────────────────────────────────────────────────
    page2 = doc.new_page()

    # Repeated header (noise)
    page2.insert_text((72, 30), "ACME Corp", fontsize=9)

    # Section heading
    page2.insert_text(
        (72, 60), "2. Financial Results", fontsize=16, fontname="Helvetica-Bold"
    )

    page2.insert_text((72, 100), "Revenue breakdown by region:", fontsize=12)

    # Page number (noise)
    page2.insert_text((290, 800), "2", fontsize=9)

    doc.save(str(out))
    doc.close()
    return out


def create_scan_pdf() -> Path:
    """Create a scan-simulated PDF (empty page — no extractable text)."""
    out = FIXTURES_DIR / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # White filled rect = blank image-like page with no text layer
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    doc.save(str(out))
    doc.close()
    return out


if __name__ == "__main__":
    FIXTURES_DIR.mkdir(exist_ok=True)
    p1 = create_native_pdf()
    p2 = create_scan_pdf()
    print(f"Created: {p1}")
    print(f"Created: {p2}")

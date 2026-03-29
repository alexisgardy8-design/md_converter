"""Integration tests: full pipeline on generated PDFs."""
import json
import pytest
from md_converter.pipeline import convert_pdf
from md_converter.optimizer import Mode
from md_converter.anki_generator import generate_deck, GeneratorOptions
from md_converter.anki_exporter import export_deck, ExportOptions


def test_native_pdf_pipeline(native_pdf_path):
    """Text PDF: pipeline produces valid Markdown with structure."""
    md, report = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)

    assert isinstance(md, str)
    assert len(md) > 100
    assert report.pipeline == "text"
    assert report.total_pages == 2


def test_native_reading_order(native_pdf_path):
    """Title must appear before section headings in the output."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    title_pos = md.find("Annual Report")
    exec_pos = md.find("Executive Summary")
    fin_pos = md.find("Financial Results")
    assert title_pos != -1, "Title not found in output"
    assert exec_pos != -1, "Executive Summary not found"
    assert fin_pos != -1, "Financial Results not found"
    assert title_pos < exec_pos < fin_pos, (
        f"Reading order incorrect: title={title_pos}, exec={exec_pos}, fin={fin_pos}"
    )


def test_native_headings_structure(native_pdf_path):
    """At least two Markdown headings must be detected."""
    md, report = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    heading_lines = [l for l in md.split("\n") if l.startswith("#")]
    assert len(heading_lines) >= 2, f"Expected >= 2 headings, got {heading_lines}"
    assert report.sections_detected >= 2


def test_noise_removed(native_pdf_path):
    """Repeated header 'ACME Corp' and standalone page numbers must be removed."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    occurrences = md.count("ACME Corp")
    assert occurrences == 0, f"Noise 'ACME Corp' appeared {occurrences} times"
    lines = [l.strip() for l in md.split("\n")]
    assert "1" not in lines, "Page number '1' still present in output"
    assert "2" not in lines, "Page number '2' still present in output"


def test_compact_mode_token_reduction(native_pdf_path):
    """Compact mode must produce fewer or equal tokens than fidelity mode."""
    _, report_fidelity = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    _, report_compact = convert_pdf(str(native_pdf_path), mode=Mode.COMPACT)
    assert report_compact.tokens_after <= report_fidelity.tokens_after


def test_report_json_schema(native_pdf_path):
    """Report JSON must be parseable and contain all required fields."""
    _, report = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    data = json.loads(report.to_json())
    required = [
        "source_path", "total_pages", "pipeline",
        "sections_detected", "tables_detected",
        "tokens_before", "tokens_after", "compression_ratio", "warnings",
    ]
    for field in required:
        assert field in data, f"Missing field: {field}"
    assert isinstance(data["warnings"], list)
    assert data["total_pages"] == 2
    assert data["pipeline"] == "text"


def test_report_compression_ratio(native_pdf_path):
    """Compression ratio must be positive and plausible."""
    _, report = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    assert 0 < report.compression_ratio <= 2.0


def test_scan_pdf_detected_as_scan(scanned_pdf_path):
    """Blank (scan) PDF must be classified as scan pipeline.
    Skipped when tesseract is not installed.
    """
    from md_converter.ocr import check_tesseract
    if not check_tesseract():
        pytest.skip("tesseract not installed — install with: sudo apt-get install tesseract-ocr")
    md, report = convert_pdf(str(scanned_pdf_path), mode=Mode.FIDELITY)
    assert report.pipeline == "scan"
    assert isinstance(md, str)


def test_page_breaks_option(native_pdf_path):
    """page_breaks=True must insert --- separators."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY, include_page_breaks=True)
    assert "---" in md


def test_deterministic_output(native_pdf_path):
    """Two runs on the same PDF must produce identical output."""
    md1, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    md2, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    assert md1 == md2


def test_pdf_to_anki_produces_cards(native_pdf_path):
    """Full pipeline: PDF → Markdown → Anki cards (non-empty)."""
    from md_converter.anki_generator import _is_short_answer_allowed
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    cards, n_filtered = generate_deck(md, GeneratorOptions(source_name="native_test"))
    assert len(cards) > 0, "Expected at least one card from a real PDF"
    assert isinstance(n_filtered, int)
    for card in cards:
        assert card.front.strip(), "Card front must not be empty"
        back = card.back.strip()
        # Short answers are valid for formulas, legal citations, and factual data
        assert len(back) >= 20 or _is_short_answer_allowed(back), "Card back too short"


def test_anki_export_csv_importable(native_pdf_path, tmp_path):
    """CSV export must be parseable with csv.reader using default separator."""
    import csv as csv_mod
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    cards, _ = generate_deck(md)
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
    cards1, _ = generate_deck(md)
    cards2, _ = generate_deck(md)
    assert [(c.front, c.back) for c in cards1] == [(c.front, c.back) for c in cards2]


def test_anki_respects_total_cards_per_pdf(native_pdf_path):
    """total_cards_per_pdf=5 must yield at most 5 cards total."""
    md, _ = convert_pdf(str(native_pdf_path), mode=Mode.FIDELITY)
    opts = GeneratorOptions(total_cards_per_pdf=5, source_name="test")
    cards, _ = generate_deck(md, opts)
    assert len(cards) <= 5, f"Expected ≤ 5 cards, got {len(cards)}"

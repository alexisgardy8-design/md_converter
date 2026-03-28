import fitz
import pytest
from md_converter.detector import classify_pdf, PdfType


def test_classify_text_pdf(tmp_path):
    pdf_path = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world " * 50, fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    result = classify_pdf(str(pdf_path))
    assert result.pdf_type == PdfType.TEXT
    assert result.text_pages == 1
    assert result.scan_pages == 0


def test_classify_empty_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    result = classify_pdf(str(pdf_path))
    assert result.pdf_type == PdfType.SCAN
    assert result.scan_pages == 1


def test_classify_mixed_pdf(tmp_path):
    pdf_path = tmp_path / "mixed.pdf"
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Text content " * 20, fontsize=12)
    doc.new_page()  # empty = scan
    doc.save(str(pdf_path))
    doc.close()
    result = classify_pdf(str(pdf_path))
    assert result.pdf_type == PdfType.MIXED
    assert result.text_pages == 1
    assert result.scan_pages == 1
    assert result.total_pages == 2

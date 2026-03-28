from __future__ import annotations
import fitz
from md_converter.detector import classify_pdf, PdfType
from md_converter.extractor import extract_page_blocks, extract_tables
from md_converter.ocr import ocr_page, check_tesseract
from md_converter.cleaner import clean_blocks
from md_converter.structure import reconstruct_structure
from md_converter.renderer import render_markdown
from md_converter.optimizer import optimize, Mode
from md_converter.reporter import build_report, ConversionReport


def convert_pdf(
    source_path: str,
    mode: Mode = Mode.FIDELITY,
    force_ocr: bool = False,
    ocr_lang: str = "eng",
    include_page_breaks: bool = False,
    verbose: bool = False,
) -> tuple[str, ConversionReport]:
    """Convert a single PDF to Markdown. Returns (markdown, report)."""
    path = str(source_path)
    detection = classify_pdf(path)
    warnings: list[str] = []
    all_ocr_confidences: list[float] = []

    if verbose:
        print(
            f"[detector] {path} → {detection.pdf_type.value} "
            f"({detection.text_pages} text, {detection.scan_pages} scan pages)"
        )

    ocr_needed = force_ocr or detection.pdf_type in (PdfType.SCAN, PdfType.MIXED)
    if ocr_needed and not check_tesseract():
        raise RuntimeError(
            "OCR required but tesseract not found. "
            "Install: sudo apt-get install tesseract-ocr"
        )

    doc = fitz.open(path)
    pages_blocks: list = []
    tables_per_page: list = []
    raw_texts: list[str] = []

    for page in doc:
        page_is_scan = (
            force_ocr
            or (detection.pdf_type == PdfType.SCAN)
            or (
                detection.pdf_type == PdfType.MIXED
                and detection.chars_per_page[page.number] < 50
            )
        )

        if page_is_scan:
            if verbose:
                print(f"  [ocr] page {page.number + 1}")
            blocks, conf = ocr_page(page, lang=ocr_lang)
            if conf < 60:
                warnings.append(
                    f"Page {page.number + 1}: low OCR confidence ({conf:.0f}%)"
                )
            all_ocr_confidences.append(conf)
            raw_texts.append(" ".join(b.text for b in blocks))
        else:
            blocks = extract_page_blocks(page)
            raw_texts.append(page.get_text("text"))

        pages_blocks.append(blocks)
        tables_per_page.append(extract_tables(page))

    doc.close()

    ocr_avg_confidence = (
        sum(all_ocr_confidences) / len(all_ocr_confidences)
        if all_ocr_confidences
        else 0.0
    )

    cleaned_blocks = clean_blocks(pages_blocks)
    elements = reconstruct_structure(
        cleaned_blocks, tables_per_page, include_page_breaks=include_page_breaks
    )
    raw_markdown = render_markdown(elements)
    final_markdown = optimize(raw_markdown, mode=mode)
    raw_text_combined = "\n".join(raw_texts)

    report = build_report(
        source_path=path,
        total_pages=detection.total_pages,
        pdf_type=detection.pdf_type,
        elements=elements,
        raw_text=raw_text_combined,
        final_markdown=final_markdown,
        warnings=warnings,
        ocr_avg_confidence=ocr_avg_confidence,
    )

    return final_markdown, report

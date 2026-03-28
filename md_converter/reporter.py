from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from md_converter.detector import PdfType
from md_converter.structure import Element, ElementType
from md_converter.optimizer import count_tokens


@dataclass
class ConversionReport:
    source_path: str
    total_pages: int
    pipeline: str           # "text", "scan", "mixed"
    sections_detected: int
    tables_detected: int
    tokens_before: int
    tokens_after: int
    compression_ratio: float
    warnings: list[str] = field(default_factory=list)
    ocr_avg_confidence: float = 0.0

    def to_json(self, indent: int = 2) -> str:
        d = asdict(self)
        d["compression_ratio"] = round(self.compression_ratio, 3)
        d["ocr_avg_confidence"] = round(self.ocr_avg_confidence, 1)
        return json.dumps(d, indent=indent, ensure_ascii=False)


def build_report(
    source_path: str,
    total_pages: int,
    pdf_type: PdfType,
    elements: list[Element],
    raw_text: str,
    final_markdown: str,
    warnings: list[str] | None = None,
    ocr_avg_confidence: float = 0.0,
) -> ConversionReport:
    sections = sum(1 for e in elements if e.element_type == ElementType.HEADING)
    tables = sum(1 for e in elements if e.element_type == ElementType.TABLE)

    tokens_before = count_tokens(raw_text)
    tokens_after = count_tokens(final_markdown)
    ratio = tokens_after / tokens_before if tokens_before > 0 else 1.0

    pipeline_map = {
        PdfType.TEXT: "text",
        PdfType.SCAN: "scan",
        PdfType.MIXED: "mixed",
    }

    return ConversionReport(
        source_path=source_path,
        total_pages=total_pages,
        pipeline=pipeline_map[pdf_type],
        sections_detected=sections,
        tables_detected=tables,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        compression_ratio=ratio,
        warnings=warnings or [],
        ocr_avg_confidence=round(ocr_avg_confidence, 1),
    )

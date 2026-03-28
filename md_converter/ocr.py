from __future__ import annotations
import io
import fitz
from PIL import Image
import pytesseract
from md_converter.extractor import Block, BlockType


def page_to_image(page: fitz.Page, dpi: int = 200) -> Image.Image:
    """Render a PDF page to a PIL Image."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def ocr_page(page: fitz.Page, lang: str = "eng", dpi: int = 200) -> tuple[list[Block], float]:
    """OCR a page and return (blocks, avg_confidence)."""
    image = page_to_image(page, dpi=dpi)

    try:
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract not found. Install with: sudo apt-get install tesseract-ocr"
        ) from e

    # Reconstruct lines from word-level data
    lines: dict[tuple, dict] = {}
    scale_x = page.rect.width / image.width
    scale_y = page.rect.height / image.height

    n = len(data["text"])
    for i in range(n):
        word = data["text"][i]
        conf_str = data["conf"][i]
        try:
            conf = int(conf_str)
        except (ValueError, TypeError):
            conf = -1
        if not word.strip() or conf < 30:
            continue

        block_num = data["block_num"][i]
        line_num = data["line_num"][i]
        key = (block_num, line_num)

        x = data["left"][i] * scale_x
        y = data["top"][i] * scale_y
        w = data["width"][i] * scale_x
        h = data["height"][i] * scale_y

        if key not in lines:
            lines[key] = {"words": [], "bbox": [x, y, x + w, y + h], "conf": []}
        lines[key]["words"].append(word)
        lines[key]["conf"].append(conf)
        lines[key]["bbox"][2] = max(lines[key]["bbox"][2], x + w)
        lines[key]["bbox"][3] = max(lines[key]["bbox"][3], y + h)

    blocks: list[Block] = []
    all_confs: list[float] = []

    for key in sorted(lines.keys()):
        line = lines[key]
        text = " ".join(line["words"])
        bbox = tuple(line["bbox"])
        line_conf = sum(line["conf"]) / len(line["conf"]) if line["conf"] else 0
        all_confs.extend(line["conf"])
        blocks.append(Block(
            text=text,
            bbox=bbox,
            page_num=page.number,
            font_size=12.0,   # unknown for OCR
            is_bold=False,
            is_italic=False,
        ))

    # Sort reading order top-to-bottom
    blocks.sort(key=lambda b: b.bbox[1])
    avg_confidence = sum(all_confs) / len(all_confs) if all_confs else 0.0
    return blocks, avg_confidence


def check_tesseract() -> bool:
    """Return True if tesseract is available."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except pytesseract.TesseractNotFoundError:
        return False

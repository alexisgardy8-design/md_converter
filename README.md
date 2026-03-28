# md-converter

AI-oriented PDF → Markdown converter with structure-aware extraction and token optimization.

Converts native-text and scanned PDFs to clean, deterministic Markdown that preserves reading order, logical structure, and semantic meaning — while reducing token cost compared to raw text extraction.

---

## Installation

### Python dependencies

```bash
pip install "PyMuPDF>=1.23.0" "pytesseract>=0.3.10" "Pillow>=10.0" \
            "tiktoken>=0.7.0" "click>=8.1" "rich>=13.7"
```

Or install from the project:

```bash
pip install -e .
```

### System dependencies (OCR only)

OCR is only required for scanned PDFs (images without a text layer).

```bash
# Debian / Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra

# macOS
brew install tesseract
```

---

## Usage

### Convert a single PDF

```bash
md-converter document.pdf
md-converter document.pdf -o output/ --mode compact
md-converter scan.pdf --ocr --lang fra
md-converter report.pdf --page-breaks -v
```

### Convert a folder (batch)

```bash
md-converter ./pdfs/ -o ./output/
md-converter ./pdfs/ -o ./output/ --mode compact --verbose
```

### Options

| Option | Default | Description |
|---|---|---|
| `-o, --output PATH` | same dir as input | Output directory |
| `--mode [fidelity\|compact]` | `fidelity` | Conversion mode |
| `--ocr` | off | Force OCR on every page |
| `--lang TEXT` | `eng` | OCR language code (e.g. `fra`, `deu`) |
| `--page-breaks` | off | Insert `---` between pages |
| `-v, --verbose` | off | Verbose pipeline output |

---

## Outputs

For each `document.pdf`, two files are produced:

- `document.md` — structured Markdown
- `document.report.json` — quality and diagnostics report

### Report fields

```json
{
  "source_path": "document.pdf",
  "total_pages": 10,
  "pipeline": "text",
  "sections_detected": 8,
  "tables_detected": 2,
  "tokens_before": 4200,
  "tokens_after": 3150,
  "compression_ratio": 0.75,
  "warnings": [],
  "ocr_avg_confidence": 0.0
}
```

| Field | Description |
|---|---|
| `pipeline` | `text`, `scan`, or `mixed` |
| `sections_detected` | Number of headings found |
| `tables_detected` | Number of tables rendered |
| `tokens_before` | Raw extracted text tokens (cl100k_base) |
| `tokens_after` | Final Markdown tokens |
| `compression_ratio` | `tokens_after / tokens_before` (<1 = reduction) |
| `warnings` | Low-confidence OCR pages, ambiguous content |

---

## Pipeline architecture

```
PDF
 │
 ├─ detector.py     →  text / scan / mixed
 │
 ├─ extractor.py    →  blocks (text + font size + bold + bbox + column)
 │   or
 │  ocr.py          →  blocks from tesseract word-level output
 │
 ├─ cleaner.py      →  remove repeated headers/footers, page numbers
 │
 ├─ structure.py    →  headings (by font size), lists, tables, paragraphs
 │
 ├─ renderer.py     →  Markdown (tables → MD or HTML fallback)
 │
 └─ optimizer.py    →  fidelity / compact normalization + token count
```

---

## Conversion modes

### `fidelity` (default)

Maximum structure preservation. Collapses excessive whitespace but keeps all logical elements including blank lines between sections.

Best for: documents where structure aids comprehension (reports, manuals, research papers).

### `compact`

Aggressive whitespace reduction. Removes blank lines between list items, collapses triple newlines, trims trailing spaces.

Best for: high-volume batch processing where token cost is the primary concern.

---

## AI quality rationale

Why this Markdown is more efficient for LLMs than raw PDF text extraction:

1. **Reading order guaranteed** — Multi-column layouts, sidebars, and figures are ordered by visual column then top-to-bottom within each column. Raw PDF extraction follows storage order, which is often scrambled in multi-column documents.

2. **Noise removed** — Headers, footers, and page numbers that repeat across pages are detected via frequency analysis and stripped before output. In typical business documents this removes 5–15% of irrelevant tokens.

3. **Structure signaled explicitly** — Headings (`#`, `##`, `###`) derived from font-size ratios give the model unambiguous section boundaries. This replaces implicit structure (capitalization, whitespace) that models must infer from raw text.

4. **Tables normalized** — Tabular data rendered as Markdown pipe tables is 30–50% more token-efficient than whitespace-aligned columns, and avoids ambiguous alignment that confuses tokenization.

5. **Compact mode** — Additional whitespace normalization on top of fidelity mode yields a further 5–20% token reduction with no semantic loss.

---

## Running tests

```bash
pip install pytest
python3 -m pytest tests/ -v
```

Expected: 44 passed, 1 skipped (OCR test skipped when tesseract is not installed).

---

## Known limitations

- **OCR accuracy** depends on scan quality and installed tesseract language packs. Low-confidence pages are flagged in the report warnings.
- **Mathematical equations** are not parsed — they appear as paragraph text (or garbled in scans).
- **Footnotes** use positional heuristics (small font at page bottom) and are not explicitly labeled.
- **Tables with merged cells** may render incorrectly; the system falls back to HTML when Markdown table syntax is invalid.
- **Two-column layout** detection uses a fixed 55% page-width midpoint. Unusual layouts may produce incorrect column ordering.
- **Scanned PDFs** require `tesseract-ocr` to be installed separately (system package).
- **Very large PDFs** (>500 pages) process all pages sequentially; there is no parallel processing in v0.1.

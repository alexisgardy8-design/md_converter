# md-converter — Project Primer

## What this project does

Converts PDF files to clean Markdown optimised for LLM consumption:
- Preserves reading order (including multi-column layouts)
- Detects and renders headings, lists, tables
- Removes noise (repeated headers/footers, page numbers)
- Supports OCR for scanned PDFs
- Reports token counts before/after conversion

## File layout

```
md_converter/       Python package (the pipeline)
  detector.py         PDF type detection (text / scan / mixed)
  extractor.py        Layout-aware text extraction via PyMuPDF
  ocr.py              OCR via pytesseract
  cleaner.py          Noise removal (repeated lines, page numbers)
  structure.py        Heading levels, lists, tables → Elements
  renderer.py         Elements → Markdown string
  optimizer.py        Fidelity / compact post-processing + token count
  reporter.py         JSON quality report
  pipeline.py         Orchestrator (calls all of the above)
  cli.py              click CLI entry point (md-converter command)

convert.py          Batch conversion script (input/ → output/)
tests/              pytest test suite (44 tests)
  fixtures/           Generated test PDFs (native + scan)
input/              Drop PDFs here to convert
output/             Generated Markdown and JSON reports (git-ignored)
```

## Typical workflow

1. Drop PDFs into `input/`
2. Run `python3 convert.py`
3. Collect `.md` files from `output/`

## Tech stack

- **PyMuPDF** (`fitz`) — PDF parsing with layout metadata
- **pytesseract** — OCR wrapper (needs `tesseract-ocr` system package)
- **tiktoken** — Token counting (cl100k_base / GPT-4 tokenizer)
- **click + rich** — CLI and terminal output
- **pytest** — Test suite

# md-converter — Project Rules for Claude

## Context

This project converts PDFs to AI-optimised Markdown.
Pipeline: detector → extractor (or OCR) → cleaner → structure → renderer → optimizer → reporter.
CLI: `md-converter` (single file or folder). Batch script: `convert.py` (input/ → output/).

## Architecture rules

- One file, one responsibility. Never merge two unrelated concerns.
- Dependencies flow one way: cli/convert.py → pipeline → {extractor, ocr, cleaner, structure, renderer, optimizer, reporter}.
- No silent fallbacks. If something fails, raise with a clear message.
- `convert.py` owns idempotence logic. The pipeline itself is stateless.

## Key commands

```bash
# Install
pip install -e .

# System OCR (required for scanned PDFs)
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra

# Run all tests
python3 -m pytest tests/ -v

# Convert input/ → output/ (skip already done)
python3 convert.py

# Force re-convert everything
python3 convert.py --force

# Single file conversion
md-converter path/to/file.pdf -o output/ --mode fidelity -v

# Compact mode (fewer tokens)
python3 convert.py --compact
```

## Idempotence convention

A PDF is considered already converted if `output/<same/path>/file.md` exists and is non-empty.
`convert.py --force` bypasses this check.
The pipeline itself (`pipeline.py`) is stateless — idempotence is the script's responsibility.

## Cleaning convention

Before committing, ensure no artifacts are staged:
```bash
find . -name "__pycache__" -o -name "*.pyc" -o -name ".pytest_cache" | xargs rm -rf
```
The `.gitignore` covers: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`, `output/`, `*.report.json`.

## End-of-task checklist

- [ ] Tests pass: `python3 -m pytest tests/ -v`
- [ ] No `__pycache__` or `.pyc` in staged files: `git status`
- [ ] `convert.py` runs clean on `input/`: `python3 convert.py`
- [ ] Second run shows only `[SKIP]` lines
- [ ] Committed on a feature branch (never directly on main)

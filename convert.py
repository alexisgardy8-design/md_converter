#!/usr/bin/env python3
"""
convert.py — Convert all PDFs in input/ to Markdown in output/.

Usage:
    python3 convert.py             # skip already-converted files
    python3 convert.py --force     # reconvert everything
    python3 convert.py --compact   # use compact (token-optimised) mode
    python3 convert.py --verbose   # detailed pipeline output
    python3 convert.py --help      # show all options

Outputs per PDF:
    output/<subpath>/filename.md          Structured Markdown
    output/<subpath>/filename.report.json Quality report (tokens, sections, …)

Exit code: 0 if all conversions succeed, 1 if any conversion fails.
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from md_converter.optimizer import Mode
from md_converter.pipeline import convert_pdf

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"

console = Console()


# ── helpers ──────────────────────────────────────────────────────────────────

def _output_md_path(pdf_path: Path) -> Path:
    """Map input/a/b/doc.pdf → output/a/b/doc.md."""
    relative = pdf_path.relative_to(INPUT_DIR)
    return OUTPUT_DIR / relative.with_suffix(".md")


def _is_already_converted(md_path: Path) -> bool:
    """Return True if a non-empty Markdown file already exists at md_path."""
    return md_path.exists() and md_path.stat().st_size > 0


def _convert_one(
    pdf_path: Path,
    mode: Mode,
    force: bool,
    verbose: bool,
) -> str:
    """Convert a single PDF.

    Returns: 'skip' | 'ok' | 'error'
    Raises:  RuntimeError with a clear message on hard failure.
    """
    md_path = _output_md_path(pdf_path)

    if not force and _is_already_converted(md_path):
        return "skip"

    markdown, report = convert_pdf(
        source_path=str(pdf_path),
        mode=mode,
        verbose=verbose,
    )

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")

    report_path = md_path.with_suffix(".report.json")
    report_path.write_text(report.to_json(), encoding="utf-8")

    if verbose:
        console.print(
            f"    pipeline={report.pipeline}  "
            f"sections={report.sections_detected}  "
            f"tables={report.tables_detected}  "
            f"tokens {report.tokens_before}→{report.tokens_after}"
        )

    return "ok"


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert all PDFs in input/ to Markdown in output/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reconvert PDFs even if the Markdown output already exists.",
    )
    parser.add_argument(
        "--compact", action="store_true",
        help="Use compact mode (aggressive whitespace reduction).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print detailed pipeline information for each file.",
    )
    args = parser.parse_args(argv)

    mode = Mode.COMPACT if args.compact else Mode.FIDELITY

    if not INPUT_DIR.exists():
        console.print(f"[red]ERROR[/red] Input directory not found: {INPUT_DIR}")
        return 1

    pdfs = sorted(INPUT_DIR.rglob("*.pdf")) + sorted(INPUT_DIR.rglob("*.PDF"))
    pdfs = sorted(set(pdfs))

    if not pdfs:
        console.print(f"[yellow]No PDF files found in {INPUT_DIR}[/yellow]")
        return 0

    console.print(
        f"[bold]md-converter[/bold]  input={INPUT_DIR}  output={OUTPUT_DIR}  "
        f"mode={mode.value}  force={args.force}"
    )
    console.print(f"Found [bold]{len(pdfs)}[/bold] PDF(s)\n")

    counts = {"ok": 0, "skip": 0, "error": 0}

    for pdf_path in pdfs:
        rel = pdf_path.relative_to(INPUT_DIR)
        md_path = _output_md_path(pdf_path)

        try:
            result = _convert_one(pdf_path, mode=mode, force=args.force, verbose=args.verbose)
        except Exception as exc:
            console.print(f"  [red][ERROR][/red] {rel}  →  {exc}")
            counts["error"] += 1
            continue

        if result == "skip":
            console.print(f"  [dim][SKIP][/dim]  {rel}  (already converted: {md_path})")
            counts["skip"] += 1
        else:
            ratio_pct = ""
            try:
                import json
                data = json.loads(md_path.with_suffix(".report.json").read_text())
                reduction = round((1 - data["compression_ratio"]) * 100, 1)
                ratio_pct = f"  ({data['tokens_before']}→{data['tokens_after']} tokens, {reduction:+.1f}%)"
            except Exception:
                pass
            console.print(f"  [green][OK][/green]    {rel}  →  {md_path.relative_to(OUTPUT_DIR)}{ratio_pct}")
            counts["ok"] += 1

    # ── summary table ─────────────────────────────────────────────────────────
    console.print()
    t = Table(title="Conversion Summary")
    t.add_column("Status", style="bold")
    t.add_column("Count")
    t.add_row("[green]Converted[/green]", str(counts["ok"]))
    t.add_row("[dim]Skipped[/dim]", str(counts["skip"]))
    t.add_row("[red]Errors[/red]", str(counts["error"]))
    console.print(t)

    return 1 if counts["error"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

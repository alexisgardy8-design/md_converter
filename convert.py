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


def _output_anki_base_path(pdf_path: Path) -> Path:
    """Map input/a/b/doc.pdf → output/a/b/doc (no extension, for Anki files)."""
    relative = pdf_path.relative_to(INPUT_DIR)
    return OUTPUT_DIR / relative.with_suffix("")


def _anki_already_exists(base_path: Path, fmt: str) -> bool:
    """Return True if requested Anki output file(s) exist and are non-empty."""
    csv_path = base_path.parent / (base_path.name + ".anki.csv")
    txt_path = base_path.parent / (base_path.name + ".anki.txt")
    if fmt == "csv":
        return csv_path.exists() and csv_path.stat().st_size > 0
    if fmt == "txt":
        return txt_path.exists() and txt_path.stat().st_size > 0
    return (csv_path.exists() and csv_path.stat().st_size > 0
            and txt_path.exists() and txt_path.stat().st_size > 0)


def _generate_anki_for_pdf(
    pdf_path: Path,
    md_was_skipped: bool,
    args,
    verbose: bool,
) -> tuple[str, int, int]:
    """Generate Anki deck for one PDF. Returns (status, cards_count, filtered_count).

    status: 'ok' | 'skip'
    """
    from md_converter.anki_generator import generate_deck, GeneratorOptions
    from md_converter.anki_exporter import export_deck, ExportOptions

    base_path = _output_anki_base_path(pdf_path)
    md_path = _output_md_path(pdf_path)

    if md_was_skipped and not args.anki_regenerate:
        return "skip", 0, 0
    if not args.force and not args.anki_regenerate and _anki_already_exists(base_path, args.anki_format):
        return "skip", 0, 0

    markdown = md_path.read_text(encoding="utf-8")
    gen_opts = GeneratorOptions(
        max_cards_per_section=args.anki_max_cards,
        min_answer_length=args.anki_min_length,
        source_name=pdf_path.stem,
    )
    cards, n_filtered = generate_deck(markdown, pdf_path.stem, gen_opts)

    export_opts = ExportOptions(format=args.anki_format, separator=args.anki_separator)
    created = export_deck(cards, base_path, export_opts)

    if verbose:
        for p in created:
            console.print(f"    anki → {p.relative_to(OUTPUT_DIR)}")

    return "ok", len(cards), n_filtered


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

    anki = parser.add_argument_group("Anki deck generation")
    anki.add_argument(
        "--anki", action="store_true",
        help="Generate an Anki deck from each converted Markdown file.",
    )
    anki.add_argument(
        "--anki-format", choices=["csv", "txt", "both"], default="csv",
        dest="anki_format",
        help="Anki export format (default: csv).",
    )
    anki.add_argument(
        "--anki-separator", default=";", dest="anki_separator", metavar="SEP",
        help="Field separator for CSV/TXT (default: ;).",
    )
    anki.add_argument(
        "--anki-regenerate", action="store_true", dest="anki_regenerate",
        help="Regenerate deck even if Markdown was skipped (already converted).",
    )
    anki.add_argument(
        "--anki-max-cards", type=int, default=5, dest="anki_max_cards", metavar="N",
        help="Maximum cards per section (default: 5).",
    )
    anki.add_argument(
        "--anki-min-length", type=int, default=20, dest="anki_min_length", metavar="N",
        help="Minimum answer length in characters (default: 20).",
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
    anki_counts = {"ok": 0, "skip": 0, "error": 0}

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

        if args.anki:
            try:
                anki_status, n_cards, n_filtered = _generate_anki_for_pdf(
                    pdf_path, md_was_skipped=(result == "skip"), args=args, verbose=args.verbose,
                )
            except Exception as exc:
                console.print(f"  [red][ANKI ERROR][/red] {rel}  →  {exc}")
                anki_counts["error"] += 1
                continue

            if anki_status == "skip":
                console.print(f"  [dim][ANKI SKIP][/dim] {rel}")
                anki_counts["skip"] += 1
            else:
                console.print(
                    f"  [cyan][ANKI][/cyan]   {rel}  →  "
                    f"{n_cards} cards, {n_filtered} filtered"
                )
                anki_counts["ok"] += 1

    # ── summary table ─────────────────────────────────────────────────────────
    console.print()
    t = Table(title="Conversion Summary")
    t.add_column("Status", style="bold")
    t.add_column("MD")
    if args.anki:
        t.add_column("Anki")
    t.add_row("[green]Converted / Generated[/green]", str(counts["ok"]),
              *(([str(anki_counts["ok"])]) if args.anki else []))
    t.add_row("[dim]Skipped[/dim]", str(counts["skip"]),
              *(([str(anki_counts["skip"])]) if args.anki else []))
    t.add_row("[red]Errors[/red]", str(counts["error"]),
              *(([str(anki_counts["error"])]) if args.anki else []))
    console.print(t)

    return 1 if (counts["error"] > 0 or anki_counts["error"] > 0) else 0


if __name__ == "__main__":
    sys.exit(main())

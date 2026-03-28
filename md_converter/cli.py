from __future__ import annotations
import sys
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from md_converter.optimizer import Mode
from md_converter.pipeline import convert_pdf

console = Console()


def _output_path(input_path: Path, output_dir: Path | None) -> Path:
    if output_dir:
        return output_dir / (input_path.stem + ".md")
    return input_path.with_suffix(".md")


def _report_path(md_path: Path) -> Path:
    return md_path.with_suffix(".report.json")


def _process_single(
    pdf_path: Path,
    output_dir: Path | None,
    mode: Mode,
    force_ocr: bool,
    ocr_lang: str,
    page_breaks: bool,
    verbose: bool,
) -> bool:
    """Convert one PDF. Returns True on success."""
    try:
        markdown, report = convert_pdf(
            source_path=str(pdf_path),
            mode=mode,
            force_ocr=force_ocr,
            ocr_lang=ocr_lang,
            include_page_breaks=page_breaks,
            verbose=verbose,
        )
    except Exception as e:
        console.print(f"[red]ERROR[/red] {pdf_path.name}: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        return False

    md_path = _output_path(pdf_path, output_dir)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")

    rep_path = _report_path(md_path)
    rep_path.write_text(report.to_json(), encoding="utf-8")

    ratio_pct = round((1 - report.compression_ratio) * 100, 1)
    console.print(
        f"  [green]✓[/green] {pdf_path.name} → {md_path.name}"
        f"  ({report.tokens_before} → {report.tokens_after} tokens, "
        f"{ratio_pct:+.1f}%)"
    )

    if report.warnings:
        for w in report.warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}")

    if verbose:
        console.print(f"     pipeline: {report.pipeline}, "
                      f"sections: {report.sections_detected}, "
                      f"tables: {report.tables_detected}")

    return True


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "-o", "--output", "output_dir", default=None,
    type=click.Path(), help="Output directory (default: same as input)",
)
@click.option(
    "--mode", default="fidelity",
    type=click.Choice(["fidelity", "compact"]),
    help="Conversion mode (default: fidelity)",
)
@click.option(
    "--ocr", "force_ocr", is_flag=True, default=False,
    help="Force OCR even for text PDFs",
)
@click.option(
    "--lang", "ocr_lang", default="eng",
    help="OCR language code (default: eng; use fra for French)",
)
@click.option(
    "--page-breaks", is_flag=True, default=False,
    help="Insert --- separators between pages",
)
@click.option(
    "-v", "--verbose", is_flag=True, default=False,
    help="Verbose output",
)
def main(input_path, output_dir, mode, force_ocr, ocr_lang, page_breaks, verbose):
    """Convert PDF(s) to AI-optimized Markdown.

    INPUT_PATH can be a single PDF file or a directory containing PDFs.
    """
    input_p = Path(input_path)
    output_p = Path(output_dir) if output_dir else None
    mode_enum = Mode.FIDELITY if mode == "fidelity" else Mode.COMPACT

    if input_p.is_dir():
        pdfs = sorted(
            list(input_p.glob("**/*.pdf")) + list(input_p.glob("**/*.PDF"))
        )
        if not pdfs:
            console.print(f"[yellow]No PDF files found in {input_p}[/yellow]")
            sys.exit(1)
        console.print(f"Found [bold]{len(pdfs)}[/bold] PDF(s) in {input_p}")
        success = 0
        for pdf in pdfs:
            console.print(f"Processing [cyan]{pdf.name}[/cyan]...")
            if _process_single(pdf, output_p, mode_enum, force_ocr, ocr_lang, page_breaks, verbose):
                success += 1
        _print_summary(len(pdfs), success)
        if success < len(pdfs):
            sys.exit(1)
    else:
        if input_p.suffix.lower() != ".pdf":
            console.print(f"[red]Error:[/red] {input_p} is not a PDF file.")
            sys.exit(1)
        console.print(f"Processing [cyan]{input_p.name}[/cyan]...")
        ok = _process_single(input_p, output_p, mode_enum, force_ocr, ocr_lang, page_breaks, verbose)
        _print_summary(1, 1 if ok else 0)
        if not ok:
            sys.exit(1)


def _print_summary(total: int, success: int) -> None:
    table = Table(title="Conversion Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Total PDFs", str(total))
    table.add_row("Succeeded", f"[green]{success}[/green]")
    failed = total - success
    table.add_row("Failed", f"[red]{failed}[/red]" if failed else "0")
    console.print(table)


if __name__ == "__main__":
    main()

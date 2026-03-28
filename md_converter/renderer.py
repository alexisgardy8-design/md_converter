from __future__ import annotations
import re
from md_converter.structure import Element, ElementType


def _render_table(rows: list[list[str]]) -> str:
    """Render table rows as Markdown table, or HTML if cells contain pipes."""
    if not rows:
        return ""

    flat_cells = [cell for row in rows for cell in row]
    has_pipes = any("|" in cell for cell in flat_cells)

    if has_pipes:
        return _render_table_html(rows)

    lines: list[str] = []
    header = rows[0]
    lines.append("| " + " | ".join(str(c).strip() for c in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows[1:]:
        padded = list(row) + [""] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(str(c).strip() for c in padded[: len(header)]) + " |")
    return "\n".join(lines)


def _render_table_html(rows: list[list[str]]) -> str:
    """Fallback: render as simple HTML table."""
    lines = ["<table>"]
    for i, row in enumerate(rows):
        tag = "th" if i == 0 else "td"
        lines.append("  <tr>")
        for cell in row:
            lines.append(f"    <{tag}>{cell.strip()}</{tag}>")
        lines.append("  </tr>")
    lines.append("</table>")
    return "\n".join(lines)


def render_markdown(elements: list[Element]) -> str:
    """Convert structured elements to a Markdown string."""
    lines: list[str] = []
    ordered_counter = 0
    prev_type: ElementType | None = None

    for elem in elements:
        t = elem.element_type

        if t != ElementType.LIST_ITEM_ORDERED:
            ordered_counter = 0

        if t == ElementType.HEADING:
            prefix = "#" * min(elem.level, 6)
            if lines:
                lines.append("")
            lines.append(f"{prefix} {elem.text}")
            lines.append("")

        elif t == ElementType.PARAGRAPH:
            if prev_type not in (ElementType.PARAGRAPH, None):
                lines.append("")
            lines.append(elem.text)

        elif t == ElementType.LIST_ITEM_UNORDERED:
            lines.append(f"- {elem.text}")

        elif t == ElementType.LIST_ITEM_ORDERED:
            ordered_counter += 1
            lines.append(f"{ordered_counter}. {elem.text}")

        elif t == ElementType.TABLE:
            if lines:
                lines.append("")
            lines.append(_render_table(elem.table_rows))
            lines.append("")

        elif t == ElementType.IMAGE:
            lines.append(f"\n_{elem.text}_\n")

        elif t == ElementType.PAGE_BREAK:
            lines.append("\n---\n")

        elif t == ElementType.CODE_BLOCK:
            lines.append(f"\n```\n{elem.text}\n```\n")

        prev_type = t

    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n"

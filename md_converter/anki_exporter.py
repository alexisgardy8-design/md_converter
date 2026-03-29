from __future__ import annotations
import csv
import io
from dataclasses import dataclass
from pathlib import Path

from md_converter.anki_generator import AnkiCard


@dataclass
class ExportOptions:
    format: str = "csv"     # "csv" | "txt" | "both"
    separator: str = ";"


_COLUMNS = ["front", "back", "tags", "source", "card_type"]


def _tags_str(tags: list[str]) -> str:
    return " ".join(tags)


def cards_to_csv(cards: list[AnkiCard], separator: str = ";") -> str:
    """Render cards to a UTF-8 CSV string, properly escaped."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=separator, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(_COLUMNS)
    for card in cards:
        writer.writerow([card.front, card.back, _tags_str(card.tags), card.source, card.card_type])
    return buf.getvalue()


def cards_to_txt(cards: list[AnkiCard], separator: str = "\t") -> str:
    """Render cards to a TXT string. Newlines inside fields are replaced by spaces."""
    buf = io.StringIO()
    buf.write(separator.join(_COLUMNS) + "\n")
    for card in cards:
        row = [
            card.front.replace("\n", " "),
            card.back.replace("\n", " "),
            _tags_str(card.tags),
            card.source,
            card.card_type,
        ]
        buf.write(separator.join(row) + "\n")
    return buf.getvalue()


def export_deck(
    cards: list[AnkiCard],
    base_path: Path,
    options: ExportOptions | None = None,
) -> list[Path]:
    """Write deck files from base_path stem. Returns list of created paths.

    base_path is the file stem (no extension).
    Creates <base_path>.anki.csv and/or <base_path>.anki.txt.
    """
    if options is None:
        options = ExportOptions()

    base_path = Path(base_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []

    if options.format in ("csv", "both"):
        csv_path = base_path.parent / (base_path.name + ".anki.csv")
        csv_path.write_text(cards_to_csv(cards, separator=options.separator), encoding="utf-8")
        created.append(csv_path)

    if options.format in ("txt", "both"):
        txt_path = base_path.parent / (base_path.name + ".anki.txt")
        txt_path.write_text(cards_to_txt(cards), encoding="utf-8")
        created.append(txt_path)

    return created

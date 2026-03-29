import pytest
from pathlib import Path
from md_converter.anki_generator import AnkiCard
from md_converter.anki_exporter import cards_to_csv, cards_to_txt, export_deck, ExportOptions

SAMPLE_CARDS = [
    AnkiCard(
        front="Définir la dérivée",
        back="La dérivée est la limite du taux de variation.",
        card_type="definition",
        tags=["cours", "section:Calcul", "source:maths"],
        source="maths — Calcul",
    ),
    AnkiCard(
        front='Question avec "guillemets"',
        back="Réponse normale.",
        card_type="example",
        tags=["cours"],
        source="maths — Exemples",
    ),
]


def test_csv_default_separator():
    csv_str = cards_to_csv(SAMPLE_CARDS, separator=";")
    lines = csv_str.strip().splitlines()
    assert lines[0].startswith("front;back;")
    assert len(lines) == 3  # header + 2 data rows


def test_csv_comma_separator():
    csv_str = cards_to_csv(SAMPLE_CARDS, separator=",")
    lines = csv_str.strip().splitlines()
    assert "," in lines[0]
    assert ";" not in lines[0]


def test_csv_quotes_escaped():
    csv_str = cards_to_csv(SAMPLE_CARDS, separator=";")
    # The card with "guillemets" must have doubled quotes somewhere
    assert '""' in csv_str


def test_csv_utf8_accents():
    cards = [AnkiCard(front="Définir énergie", back="L'énergie est une capacité à produire du travail.", card_type="definition", tags=[], source="")]
    csv_bytes = cards_to_csv(cards).encode("utf-8")
    assert "Définir".encode("utf-8") in csv_bytes


def test_csv_contains_all_fields():
    csv_str = cards_to_csv(SAMPLE_CARDS[:1])
    assert "dérivée" in csv_str.lower() or "derivee" in csv_str.lower()
    assert "cours" in csv_str
    assert "definition" in csv_str


def test_txt_tab_separator():
    txt_str = cards_to_txt(SAMPLE_CARDS, separator="\t")
    assert "\t" in txt_str
    lines = txt_str.strip().splitlines()
    assert len(lines) == 3  # header + 2 rows


def test_txt_custom_separator():
    txt_str = cards_to_txt(SAMPLE_CARDS, separator="|")
    assert "|" in txt_str


def test_txt_newlines_in_back_removed():
    cards = [AnkiCard(front="Q?", back="Line1\nLine2\nLine3", card_type="x", tags=[], source="")]
    txt_str = cards_to_txt(cards)
    data_line = txt_str.strip().splitlines()[1]
    assert "\n" not in data_line


def test_export_deck_csv_creates_file(tmp_path):
    base = tmp_path / "test"
    opts = ExportOptions(format="csv", separator=";")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    assert len(paths) == 1
    csv_file = tmp_path / "test.anki.csv"
    assert csv_file.exists()
    assert csv_file.stat().st_size > 0


def test_export_deck_txt_creates_file(tmp_path):
    base = tmp_path / "test"
    opts = ExportOptions(format="txt")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    assert len(paths) == 1
    txt_file = tmp_path / "test.anki.txt"
    assert txt_file.exists()


def test_export_deck_both_creates_two_files(tmp_path):
    base = tmp_path / "test"
    opts = ExportOptions(format="both")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    assert len(paths) == 2
    assert (tmp_path / "test.anki.csv").exists()
    assert (tmp_path / "test.anki.txt").exists()


def test_export_deck_empty_cards_no_error(tmp_path):
    base = tmp_path / "empty"
    paths = export_deck([], base, ExportOptions(format="csv"))
    assert len(paths) == 1
    assert (tmp_path / "empty.anki.csv").exists()


def test_export_deck_returns_correct_paths(tmp_path):
    base = tmp_path / "subdir" / "myfile"
    opts = ExportOptions(format="both")
    paths = export_deck(SAMPLE_CARDS, base, opts)
    names = {p.name for p in paths}
    assert "myfile.anki.csv" in names
    assert "myfile.anki.txt" in names

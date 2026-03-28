import pytest
from pathlib import Path
from tests.fixtures.create_fixtures import create_native_pdf, create_scan_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def generate_fixtures():
    """Generate test PDFs once per test session."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    create_native_pdf()
    create_scan_pdf()


@pytest.fixture(scope="session")
def native_pdf_path(generate_fixtures):
    return FIXTURES_DIR / "native.pdf"


@pytest.fixture(scope="session")
def scanned_pdf_path(generate_fixtures):
    return FIXTURES_DIR / "scanned.pdf"

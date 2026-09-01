# tests/conftest.py
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def get_fixture_files(extension: str):
    """Finds all files with a given extension in tests/fixtures/."""
    files = list(FIXTURES_DIR.glob(f"*{extension}"))
    if not files:
        pytest.skip(f"No {extension} files found in {FIXTURES_DIR}")
    return files
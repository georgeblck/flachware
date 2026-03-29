from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def index_html() -> str:
    return (FIXTURES_DIR / "index.html").read_text(encoding="utf-8", errors="replace")


@pytest.fixture
def artist_html_adrine() -> str:
    return (FIXTURES_DIR / "adrine-ter-arakelyan.html").read_text(
        encoding="utf-8", errors="replace"
    )


@pytest.fixture
def artist_html_afshin() -> str:
    return (FIXTURES_DIR / "afshin-karimi-fard.html").read_text(
        encoding="utf-8", errors="replace"
    )


@pytest.fixture
def artist_html_adrian() -> str:
    return (FIXTURES_DIR / "adrian-soelch.html").read_text(
        encoding="utf-8", errors="replace"
    )

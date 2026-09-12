from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tanakh_epub.books import default_books  # noqa: E402
from tanakh_epub.config import load_config  # noqa: E402
from tanakh_epub.epub.builder import EpubBuilder  # noqa: E402
from tanakh_epub.processing.study_units import ChapterSelection, load_chapters  # noqa: E402
from tanakh_epub.providers.local import LocalProvider  # noqa: E402

POC_MAX_VERSE = 10
"""The POC is בראשית א׳:א׳–י׳ (SPEC.md §34)."""


@pytest.fixture(scope="session")
def config():
    return load_config()


@pytest.fixture(scope="session")
def books():
    return default_books()


@pytest.fixture(scope="session")
def provider(books):
    return LocalProvider(books=books)


@pytest.fixture(scope="session")
def genesis_chapter_1(provider, config, books):
    """The POC chapter, as the internal model."""
    chapters, text_versions, commentary_versions = load_chapters(
        provider,
        config,
        [ChapterSelection(books.by_title("Genesis"), (1,), max_verse=POC_MAX_VERSE)],
    )
    return chapters, text_versions, commentary_versions


@pytest.fixture(scope="session")
def poc_epub(tmp_path_factory, config, books, genesis_chapter_1):
    """The POC build, produced once and shared by every test that inspects it."""
    chapters, text_versions, commentary_versions = genesis_chapter_1
    output = tmp_path_factory.mktemp("epub") / "Genesis_Chapter_1.epub"
    EpubBuilder(config, books).build(
        chapters,
        output=output,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=datetime(2026, 9, 11, 12, 0, 0, tzinfo=UTC),
    )
    return output

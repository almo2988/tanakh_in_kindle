"""SPEC_DATA_SOURCE.md §19 — the real Sefaria endpoints. Runs only with RUN_NETWORK_TESTS=1.

About ten polite requests: whole books only, never a verse.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from tanakh_epub.processing.inventory import Inventory, scan
from tanakh_epub.providers.fetch import fetch_book
from tanakh_epub.providers.local import LocalProvider
from tanakh_epub.providers.sefaria import SefariaProvider

pytestmark = pytest.mark.network

NIKKUD = range(0x05B0, 0x05BD)
TEAMIM = range(0x0591, 0x05AF)


@pytest.fixture(scope="module")
def cache(tmp_path_factory, config, books) -> Path:
    root = tmp_path_factory.mktemp("cache")
    outcomes = fetch_book(SefariaProvider(), config, books.by_title("Genesis"), cache_dir=root)
    assert [o.status for o in outcomes] == ["fetched", "fetched"], outcomes
    return root


@pytest.fixture(scope="module")
def local(cache, config, books) -> LocalProvider:
    return LocalProvider(
        [cache],
        books=books,
        expected_versions={
            "tanakh": config.tanakh_source.version_title,
            "Rashi": config.commentary_sources["Rashi"].version_title,
        },
    )


def test_configured_versions_exist(config) -> None:
    provider = SefariaProvider()
    provider.find_version("Genesis", config.tanakh_source.version_title)
    provider.find_version("Rashi on Genesis", config.commentary_sources["Rashi"].version_title)


def test_genesis_is_chapter_then_verse_with_nikkud_and_teamim(local) -> None:
    text = local.get_book_text("Genesis")
    assert len(text) == 50
    assert all(isinstance(v, str) for v in text[0])
    first = unicodedata.normalize("NFD", text[0][0])
    assert any(ord(c) in NIKKUD for c in first)
    assert any(ord(c) in TEAMIM for c in first)
    assert local.index_lengths("Genesis") == (50, sum(len(c) for c in text))


def test_version_and_license_are_recorded(local, config) -> None:
    source = local.text_source("Genesis")
    assert source.version_title == config.tanakh_source.version_title
    assert source.license == config.tanakh_source.license


def test_rashi_maps_to_verses_by_structure(local) -> None:
    rashi = local.get_book_commentary("Rashi", "Genesis")
    assert len(rashi[0][0]) > 1, "Genesis 1:1 has several Rashi entries"
    assert rashi[0][0][0].startswith("<b>")


def test_markup_inventory_has_only_known_patterns(local) -> None:
    inventory = Inventory()
    scan(inventory, "Genesis", local.get_book_text("Genesis"))
    scan(inventory, "Rashi on Genesis", local.get_book_commentary("Rashi", "Genesis"))
    assert inventory.unknown == []


def test_the_chosen_versions_validate_clean(local, config, books) -> None:
    """NFC loses nothing across the whole book, and every string converts (task 2.7)."""
    from tanakh_epub.processing.validation import validate_book

    report = validate_book(local, config, books.by_title("Genesis"))
    assert report.problems == []
    assert report.nfc_lossy == []
    assert report.nfc_reordered > 0, "Sefaria stores marks in typing order; NFC reorders them"

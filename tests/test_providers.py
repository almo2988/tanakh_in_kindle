"""SPEC.md §20, SPEC_DATA_SOURCE.md §2, §3, §11 — the provider contract."""

from __future__ import annotations

import json

import pytest

from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.providers.base import CommentaryProvider, ProviderError, TextProvider
from tanakh_epub.providers.local import LocalProvider


def test_local_provider_satisfies_both_protocols(provider) -> None:
    assert isinstance(provider, TextProvider)
    assert isinstance(provider, CommentaryProvider)


def test_text_is_chapter_then_verse(provider) -> None:
    text = provider.get_book_text("Genesis")
    assert len(text[0]) == 31
    assert isinstance(text[0][0], str)


def test_commentary_is_chapter_verse_entry(provider) -> None:
    commentary = provider.get_book_commentary("Rashi", "Genesis")
    assert len(commentary[0][0]) == 3, "בראשית א׳:א׳ has three Rashi entries"
    assert commentary[0][2] == [], "בראשית א׳:ג׳ has no Rashi"


def test_version_travels_with_the_content(provider, config) -> None:
    assert provider.text_source("Genesis").version_title == config.tanakh_source.version_title
    assert (
        provider.commentary_source("Rashi", "Genesis").version_title
        == config.commentary_sources["Rashi"].version_title
    )


def test_a_version_mismatch_is_a_miss_not_a_silent_mix(books) -> None:
    """SPEC_DATA_SOURCE §11 — mixing two versions of the Tanakh in one book is the kind
    of error nobody would notice by reading."""
    strict = LocalProvider(books=books, expected_versions={"tanakh": "Some Other Version"})
    with pytest.raises(ProviderError, match="Refusing to mix versions"):
        strict.get_book_text("Genesis")


def test_missing_book_names_where_it_looked(provider) -> None:
    with pytest.raises(ProviderError, match="Looked in"):
        provider.get_book_text("Exodus")


def test_missing_commentary_is_not_an_error(provider) -> None:
    """Rashi coverage is uneven across the Tanakh (SPEC_DATA_SOURCE §5)."""
    assert provider.has_commentary("Rashi", "Genesis") is True
    assert provider.has_commentary("Rashi", "Exodus") is False


def test_partial_fixture_reports_only_the_chapters_it_has(provider) -> None:
    assert provider.available_chapters("Genesis") == (1,)
    with pytest.raises(ProviderError, match="no chapter 2"):
        provider.get_chapter_text("Genesis", 2)


# ---- the fixtures themselves --------------------------------------------


@pytest.mark.parametrize("name", ["genesis_1.json", "rashi_genesis_1.json"])
def test_fixture_records_how_it_was_captured(name: str) -> None:
    """A fixture nobody can re-capture is a fixture nobody can trust."""
    fixture = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    capture = fixture["_capture"]
    assert capture["command"].startswith("curl ")
    assert "sefaria.org/api" in capture["command"]
    assert capture["script"] == "scripts/capture_fixtures.py"
    assert capture["captured_at"]
    for key in ("index", "version_title", "license", "source", "fetched_at"):
        assert fixture[key], f"{name} is missing {key}"


def test_fixture_was_sliced_from_a_whole_book_request() -> None:
    """CLAUDE.md non-negotiable 7: whole books, never single verses."""
    fixture = json.loads((FIXTURES_DIR / "genesis_1.json").read_text(encoding="utf-8"))
    assert fixture["_capture"]["whole_book_chapters"] == 50
    assert "Genesis?" in fixture["_capture"]["command"]
    assert fixture["chapters_included"] == [1]

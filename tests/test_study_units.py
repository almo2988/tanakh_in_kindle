"""SPEC.md §2, §13, §19, §22, §23 — verse–commentary pairing."""

from __future__ import annotations

import pytest

from tanakh_epub.models import StudyUnit, Verse
from tanakh_epub.processing.study_units import ChapterSelection, ContentError, load_chapters, stats


def test_poc_chapter_has_ten_verses(genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    assert len(chapters) == 1
    assert len(chapters[0].study_units) == 10


def test_every_verse_carries_its_provider_and_version(genesis_chapter_1) -> None:
    chapters, text_versions, commentary_versions = genesis_chapter_1
    for unit in chapters[0].study_units:
        assert unit.verse.source_provider
        assert unit.verse.source_version == text_versions["Genesis"]
        for entry in unit.commentaries:
            assert entry.source_version == commentary_versions["Rashi"]


def test_commentary_follows_its_own_verse(genesis_chapter_1) -> None:
    """Pairing comes from Sefaria's reference structure, never from matching text."""
    chapters, _, _ = genesis_chapter_1
    for unit in chapters[0].study_units:
        for entry in unit.commentaries:
            assert (entry.book, entry.chapter, entry.verse) == (
                unit.verse.book,
                unit.verse.chapter,
                unit.verse.verse,
            )
            assert entry.source_reference == (
                f"Rashi on Genesis {unit.verse.chapter}:{unit.verse.verse}:{entry.entry_number}"
            )


def test_multiple_entries_keep_source_order(genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    first = chapters[0].study_units[0]
    assert len(first.commentaries) == 3, "בראשית א׳:א׳ should have three Rashi entries"
    assert [e.entry_number for e in first.commentaries] == [1, 2, 3]
    assert first.commentaries[0].dibur_hamatchil == "בראשית."


def test_a_verse_without_rashi_has_no_commentary(genesis_chapter_1) -> None:
    """בראשית א׳:ג׳ has no Rashi — the case SPEC §22 exists for."""
    chapters, _, _ = genesis_chapter_1
    third = chapters[0].study_units[2]
    assert third.verse.verse == 3
    assert third.commentaries == []
    assert third.has_commentary is False


def test_stats_count_what_is_there(genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    counts = stats(chapters)
    assert counts.verses == 10
    assert counts.verses_with_commentary == 9
    assert counts.verses_without_commentary == 1
    assert counts.commentary_entries == 17


def test_model_is_frozen() -> None:
    verse = Verse("Genesis", 1, 1, "x", "Sefaria", "v")
    with pytest.raises(AttributeError):
        verse.chapter = 2  # type: ignore[misc]
    assert StudyUnit(verse=verse).has_commentary is False
    assert verse.reference.canonical_ref() == "Genesis 1:1"
    assert verse.reference.commentary_ref("Rashi on ", 2) == "Rashi on Genesis 1:1:2"


def test_missing_chapter_fails_loudly(provider, config, books) -> None:
    """The fixture holds chapter 1 only; asking for chapter 2 must not yield a short book."""
    with pytest.raises((ContentError, Exception)):
        load_chapters(provider, config, [ChapterSelection(books.by_title("Genesis"), (2,))])

"""SPEC.md §9, §33 — the canonical book table."""

from __future__ import annotations

import re

import pytest

from tanakh_epub.books import SLUG_PATTERN, load_books

EXPECTED_BOOK_COUNT = 39
XML_ID = re.compile(r"^[A-Za-z_][-A-Za-z0-9_.]*$")


def test_all_thirty_nine_books_present(books) -> None:
    assert len(books) == EXPECTED_BOOK_COUNT


def test_sections_in_canonical_order(books) -> None:
    order = [book.section for book in books]
    assert order == ["torah"] * 5 + ["neviim"] * 21 + ["ketuvim"] * 13
    assert [b.sefaria_title for b in books][:2] == ["Genesis", "Exodus"]
    assert [b.sefaria_title for b in books][-1] == "II Chronicles"


def test_slugs_are_unique(books) -> None:
    slugs = [book.slug for book in books]
    assert len(set(slugs)) == len(slugs)


def test_slugs_are_url_and_id_safe(books) -> None:
    for book in books:
        assert SLUG_PATTERN.match(book.slug), book.slug
        assert XML_ID.match(book.verse_id(1, 1)), book.verse_id(1, 1)
        assert book.chapter_filename(1).isascii()


def test_slugs_are_not_derived_from_english_titles(books) -> None:
    """Naive slugging collides on the numbered books and breaks on spaces."""
    assert books.by_title("I Samuel").slug == "samuel-1"
    assert books.by_title("II Samuel").slug == "samuel-2"
    assert books.by_title("I Kings").slug == "kings-1"
    assert books.by_title("II Chronicles").slug == "chronicles-2"
    assert books.by_title("Song of Songs").slug == "song-of-songs"


def test_every_book_has_a_hebrew_title(books) -> None:
    for book in books:
        assert book.hebrew_title
        assert not book.hebrew_title.isascii(), book.sefaria_title


def test_filenames_and_ids_follow_the_spec(books) -> None:
    genesis = books.by_title("Genesis")
    assert genesis.chapter_filename(1) == "genesis-001.xhtml"
    assert genesis.chapter_filename(50) == "genesis-050.xhtml"
    assert genesis.verse_id(1, 1) == "genesis-1-1"
    assert books.by_title("I Samuel").verse_id(3, 14) == "samuel-1-3-14"
    assert genesis.chapter_anchor(1) == "chapter-1"


def test_unknown_book_fails_loudly(books) -> None:
    with pytest.raises(KeyError):
        books.by_title("Bereshit")
    with pytest.raises(KeyError):
        books.by_slug("nope")


def test_duplicate_slug_is_rejected(tmp_path) -> None:
    path = tmp_path / "books.yaml"
    path.write_text(
        "books:\n"
        '  - { sefaria_title: "A", hebrew_title: "א", slug: a, section: torah }\n'
        '  - { sefaria_title: "B", hebrew_title: "ב", slug: a, section: torah }\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="slug"):
        load_books(path)


def test_unsafe_slug_is_rejected(tmp_path) -> None:
    path = tmp_path / "books.yaml"
    path.write_text(
        "books:\n"
        '  - sefaria_title: "I Samuel"\n'
        '    hebrew_title: "שמואל א׳"\n'
        '    slug: "I Samuel"\n'
        "    section: neviim\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="URL/ID-safe"):
        load_books(path)


def test_a_malformed_entry_is_rejected_with_a_useful_message(tmp_path) -> None:
    path = tmp_path / "books.yaml"
    path.write_text("books:\n  - [not, a, mapping]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_books(path)

"""The canonical book table — SPEC.md §9.

Book identity lives in ``config/books.yaml`` and nowhere else. In particular slugs are
read, never derived: lower-casing "I Samuel" or "Song of Songs" would produce collisions
and unusable file names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .paths import BOOKS_CONFIG

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
"""URL- and XML-ID-safe: lowercase, digits, single hyphens, never leading with a digit
in a way that breaks an ``id`` attribute (all slugs start with a letter)."""

SECTIONS = ("torah", "neviim", "ketuvim")


@dataclass(frozen=True)
class BookInfo:
    sefaria_title: str
    hebrew_title: str
    slug: str
    section: str
    order: int
    """1-based position in canonical Tanakh order; also the spine order."""

    def chapter_filename(self, chapter: int, part: str = "") -> str:
        """``genesis-001.xhtml`` — SPEC.md §11."""
        return f"{self.slug}-{chapter:03d}{part}.xhtml"

    def chapter_anchor(self, chapter: int) -> str:
        """``chapter-1`` — the stable target of the TOC entry (SPEC.md §18)."""
        return f"chapter-{chapter}"

    def verse_id(self, chapter: int, verse: int) -> str:
        """``genesis-1-1`` — SPEC.md §12.1."""
        return f"{self.slug}-{chapter}-{verse}"


@dataclass(frozen=True)
class BookTable:
    books: tuple[BookInfo, ...]
    section_titles: dict[str, str]

    def __iter__(self):
        return iter(self.books)

    def __len__(self) -> int:
        return len(self.books)

    def by_title(self, sefaria_title: str) -> BookInfo:
        for book in self.books:
            if book.sefaria_title == sefaria_title:
                return book
        raise KeyError(
            f'"{sefaria_title}" is not in config/books.yaml. '
            f"Book names are never invented in code; add it to the table first."
        )

    def by_slug(self, slug: str) -> BookInfo:
        for book in self.books:
            if book.slug == slug:
                return book
        raise KeyError(f'No book with slug "{slug}" in config/books.yaml')

    def in_section(self, section: str) -> tuple[BookInfo, ...]:
        return tuple(b for b in self.books if b.section == section)


def load_books(path: Path | None = None) -> BookTable:
    """Read and validate ``config/books.yaml``.

    Validation is done here, once, so that no later stage has to wonder whether a slug is
    safe to put in a file name or an ``id`` attribute.
    """
    path = path or BOOKS_CONFIG
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    entries = raw.get("books") or []
    if not entries:
        raise ValueError(f"{path} contains no books")

    books: list[BookInfo] = []
    seen_slugs: dict[str, str] = {}
    seen_titles: set[str] = set()

    for order, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: book #{order} is not a mapping, got {type(entry).__name__}")
        missing = {"sefaria_title", "hebrew_title", "slug", "section"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: book #{order} is missing {sorted(missing)}")

        slug = entry["slug"]
        if not SLUG_PATTERN.match(slug):
            raise ValueError(
                f'{path}: slug "{slug}" is not URL/ID-safe '
                f"(expected lowercase words joined by single hyphens)"
            )
        if slug in seen_slugs:
            raise ValueError(
                f'{path}: slug "{slug}" is used by both '
                f'"{seen_slugs[slug]}" and "{entry["sefaria_title"]}"'
            )
        seen_slugs[slug] = entry["sefaria_title"]

        if entry["sefaria_title"] in seen_titles:
            raise ValueError(f'{path}: duplicate Sefaria title "{entry["sefaria_title"]}"')
        seen_titles.add(entry["sefaria_title"])

        if entry["section"] not in SECTIONS:
            raise ValueError(
                f'{path}: "{entry["sefaria_title"]}" has section "{entry["section"]}"; '
                f"expected one of {SECTIONS}"
            )

        books.append(
            BookInfo(
                sefaria_title=entry["sefaria_title"],
                hebrew_title=entry["hebrew_title"],
                slug=slug,
                section=entry["section"],
                order=order,
            )
        )

    return BookTable(books=tuple(books), section_titles=dict(raw.get("sections") or {}))


@lru_cache(maxsize=1)
def default_books() -> BookTable:
    return load_books()

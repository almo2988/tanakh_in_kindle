"""Navigation — SPEC.md §10.

Two documents describing the same two levels: the EPUB 3 ``nav.xhtml`` and an EPUB 2
``toc.ncx``. The NCX is not legacy baggage here — Kindle's conversion tools still read it.

**Depth is exactly two: book → chapter.** Kindle's "Go to" menu shows two nested levels;
a third (section → book → chapter) would hide every chapter behind a section.
``navigation.include_sections`` therefore adds תורה / נביאים / כתובים as *flat* top-level
entries, never as parents.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..books import BookTable
from ..config import Config
from ..processing.hebrew_numbers import chapter_label
from ..rendering.html_renderer import RenderedChapter

MAX_DEPTH = 2
TEXT_DIR = "text"


@dataclass(frozen=True)
class NavEntry:
    title: str
    href: str
    chapters: tuple[NavEntry, ...] = ()


@dataclass(frozen=True)
class NavigationModel:
    books: tuple[NavEntry, ...]
    sections: tuple[NavEntry, ...]
    start_href: str
    sources_href: str | None

    @property
    def depth(self) -> int:
        return 2 if any(book.chapters for book in self.books) else 1


def build_navigation(
    config: Config,
    books: BookTable,
    rendered: list[RenderedChapter],
    *,
    sources_filename: str | None,
) -> NavigationModel:
    if not rendered:
        raise ValueError("Cannot build navigation for an empty book")

    by_book: dict[str, list[RenderedChapter]] = {}
    for chapter in rendered:
        by_book.setdefault(chapter.book.sefaria_title, []).append(chapter)

    book_entries: list[NavEntry] = []
    for title, chapters in by_book.items():
        info = books.by_title(title)
        first = chapters[0]
        chapter_entries = (
            tuple(
                NavEntry(
                    title=chapter_label(chapter.chapter),
                    href=f"{TEXT_DIR}/{chapter.filename}#{chapter.anchor}",
                )
                for chapter in chapters
            )
            if config.navigation.include_chapters
            else ()
        )
        book_entries.append(
            NavEntry(
                title=info.hebrew_title,
                href=f"{TEXT_DIR}/{first.filename}",
                chapters=chapter_entries,
            )
        )

    sections: list[NavEntry] = []
    if config.navigation.include_sections:
        # Flat, pointing at each section's first book — never a parent node (SPEC §10).
        seen: set[str] = set()
        for chapter in rendered:
            section = chapter.book.section
            if section in seen:
                continue
            seen.add(section)
            sections.append(
                NavEntry(
                    title=books.section_titles.get(section, section),
                    href=f"{TEXT_DIR}/{chapter.filename}",
                )
            )

    return NavigationModel(
        books=tuple(book_entries),
        sections=tuple(sections),
        start_href=f"{TEXT_DIR}/{rendered[0].filename}",
        sources_href=f"{TEXT_DIR}/{sources_filename}" if sources_filename else None,
    )


def render_nav(environment, model: NavigationModel) -> str:
    return environment.get_template("nav.xhtml.j2").render(
        toc_title="תוכן העניינים",
        landmarks_title="ניווט",
        start_title="תחילת הספר",
        sources_title="מקורות",
        books=[
            {
                "title": book.title,
                "href": book.href,
                "chapters": [{"title": c.title, "href": c.href} for c in book.chapters],
            }
            for book in model.books
        ],
        sections=[{"title": s.title, "href": s.href} for s in model.sections],
        start_href=model.start_href,
        sources_href=model.sources_href,
    )


def render_ncx(environment, model: NavigationModel, *, identifier: str, title: str) -> str:
    points = []
    play_order = 0

    for entry in model.sections:
        play_order += 1
        points.append(
            {
                "id": f"navpoint-{play_order}",
                "play_order": play_order,
                "title": entry.title,
                "href": entry.href,
                "children": [],
            }
        )

    for entry in model.books:
        play_order += 1
        children = []
        point = {
            "id": f"navpoint-{play_order}",
            "play_order": play_order,
            "title": entry.title,
            "href": entry.href,
            "children": children,
        }
        for chapter in entry.chapters:
            play_order += 1
            children.append(
                {
                    "id": f"navpoint-{play_order}",
                    "play_order": play_order,
                    "title": chapter.title,
                    "href": chapter.href,
                }
            )
        points.append(point)

    if model.sources_href:
        play_order += 1
        points.append(
            {
                "id": f"navpoint-{play_order}",
                "play_order": play_order,
                "title": "מקורות",
                "href": model.sources_href,
                "children": [],
            }
        )

    return environment.get_template("toc.ncx.j2").render(
        identifier=identifier,
        title=title,
        depth=model.depth,
        nav_points=points,
    )

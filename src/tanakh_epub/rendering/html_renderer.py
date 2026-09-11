"""Chapter XHTML — SPEC.md §11, §12, §13, §17, §18, §22, §23.

One file per chapter, stable ids, book heading on the first chapter of each book. The
renderer consumes only the internal model; it never sees a provider response and never
performs HTTP (SPEC.md §20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from ..books import BookInfo, BookTable
from ..config import Config
from ..models import Chapter, CommentaryEntry, StudyUnit
from ..paths import TEMPLATES_DIR
from ..processing.hebrew_numbers import chapter_label, verse_label
from ..processing.markup import paragraphs

HEBREW_MONTHS = (
    "בינואר",
    "בפברואר",
    "במרץ",
    "באפריל",
    "במאי",
    "ביוני",
    "ביולי",
    "באוגוסט",
    "בספטמבר",
    "באוקטובר",
    "בנובמבר",
    "בדצמבר",
)


def hebrew_date(moment: datetime) -> str:
    """``11 בספטמבר 2026`` — Hebrew wording, ordinary digits."""
    return f"{moment.day} {HEBREW_MONTHS[moment.month - 1]} {moment.year}"


def build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


@dataclass(frozen=True)
class RenderedChapter:
    book: BookInfo
    chapter: int
    filename: str
    anchor: str
    title: str
    xhtml: str

    @property
    def size_bytes(self) -> int:
        return len(self.xhtml.encode("utf-8"))


def _entry_context(entry: CommentaryEntry) -> dict:
    return {
        "id": f"{entry.commentator.lower()}-{entry.book.replace(' ', '-').lower()}"
        f"-{entry.chapter}-{entry.verse}-{entry.entry_number}",
        "dibur_hamatchil": entry.dibur_hamatchil,
        # markup.py has already escaped these and emitted only internal tags.
        "paragraphs": [Markup(p) for p in paragraphs(entry.text)],
    }


def _unit_context(unit: StudyUnit, book: BookInfo, config: Config) -> dict:
    verse = unit.verse
    verse_paragraphs = paragraphs(verse.hebrew_text)

    commentary = None
    if unit.commentaries or config.show_empty_commentary:
        # Phase 1 renders one commentator. Entries keep source order, always (SPEC §23),
        # and a verse with none renders no block at all (SPEC §22).
        name = unit.commentaries[0].commentator if unit.commentaries else config.commentaries[0]
        info = config.commentator(name)
        commentary = {
            "slug": info.slug,
            "hebrew": info.hebrew,
            "entries": [_entry_context(entry) for entry in unit.commentaries],
        }
        if not commentary["entries"]:
            commentary = None

    return {
        "verse_id": book.verse_id(verse.chapter, verse.verse),
        "verse_label": verse_label(verse.verse),
        # A verse is a single paragraph in practice; a break inside one is joined with a
        # line break rather than splitting SPEC §12.1's markup in two.
        "verse_html": Markup("<br/>").join(Markup(p) for p in verse_paragraphs),
        "commentary": commentary,
    }


class ChapterRenderer:
    def __init__(self, config: Config, books: BookTable, environment: Environment | None = None):
        self.config = config
        self.books = books
        self.env = environment or build_environment()

    def render(self, chapter: Chapter, *, book_start: bool) -> RenderedChapter:
        book = self.books.by_title(chapter.book)
        label = chapter_label(chapter.number)
        title = f"{book.hebrew_title} {label}"

        xhtml = self.env.get_template("chapter.xhtml.j2").render(
            page_title=title,
            book_hebrew_title=book.hebrew_title,
            chapter_label=label,
            chapter_anchor=book.chapter_anchor(chapter.number),
            book_start=book_start,
            units=[_unit_context(unit, book, self.config) for unit in chapter.study_units],
        )

        return RenderedChapter(
            book=book,
            chapter=chapter.number,
            filename=book.chapter_filename(chapter.number),
            anchor=book.chapter_anchor(chapter.number),
            title=title,
            xhtml=xhtml,
        )

    def render_all(self, chapters: list[Chapter]) -> list[RenderedChapter]:
        seen_books: set[str] = set()
        rendered: list[RenderedChapter] = []
        for chapter in chapters:
            first = chapter.book not in seen_books
            seen_books.add(chapter.book)
            rendered.append(self.render(chapter, book_start=first))
        return rendered

    def render_sources(self, *, build_date: datetime) -> str:
        config = self.config
        text_sources = [
            {
                "label": "טקסט המקרא",
                "version_title": config.tanakh_source.version_title,
                "license": config.tanakh_source.license,
            }
        ]
        for name in config.commentaries:
            source = config.commentary_sources[name]
            text_sources.append(
                {
                    "label": f"פירוש {config.commentator(name).hebrew}",
                    "version_title": source.version_title,
                    "license": source.license,
                }
            )

        fonts = [
            {
                "label": "גופן המקרא",
                "name": config.biblical_font.name,
                "license": config.biblical_font.license,
            },
            {
                "label": "גופן הפירוש",
                "name": config.rashi_font.name,
                "license": config.rashi_font.license,
            },
        ]

        return self.env.get_template("sources.xhtml.j2").render(
            heading="מקורות",
            text_heading="טקסטים",
            fonts_heading="גופנים",
            build_heading="הפקה",
            text_sources=text_sources,
            fonts=fonts,
            build_date_hebrew=hebrew_date(build_date),
        )

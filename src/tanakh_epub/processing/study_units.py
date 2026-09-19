"""Study units — SPEC.md §2, §13, §19, §22, §23.

A study unit is one verse plus the commentary attached to it. Pairing comes from Sefaria's
reference structure — ``Rashi on Genesis 1:1:2`` *is* the second Rashi entry on Genesis 1:1
— never from matching Hebrew text or dibur hamatchil (SPEC_DATA_SOURCE.md §3).

This is where raw source strings become the internal model: markup is converted, the
result is audited against the internal subset, and every object carries the provider and
the exact version it came from.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..books import BookInfo
from ..config import CommentatorInfo, Config
from ..models import Chapter, CommentaryEntry, StudyUnit, Verse, VerseReference
from .markup import assert_internal_markup_only, convert_commentary_entry, convert_verse


class ContentError(RuntimeError):
    """Content that cannot be turned into a study unit — SPEC.md §21."""


@dataclass(frozen=True)
class BuildStats:
    verses: int
    commentary_entries: int
    verses_with_commentary: int
    verses_without_commentary: int


def _commentary_for(book_commentary: list[list[list[str]]], chapter: int, verse: int) -> list[str]:
    """Entries for one verse, or none. Absent chapters and verses are not an error:
    coverage is uneven and a missing entry means "no Rashi here" (SPEC_DATA_SOURCE.md §5).
    """
    if chapter - 1 >= len(book_commentary):
        return []
    chapter_entries = book_commentary[chapter - 1]
    if verse - 1 >= len(chapter_entries):
        return []
    return chapter_entries[verse - 1] or []


def build_chapter(
    *,
    book: BookInfo,
    chapter: int,
    book_text: list[list[str]],
    commentary: dict[str, list[list[list[str]]]],
    config: Config,
    text_version: str,
    commentary_versions: dict[str, str],
    provider_name: str = "Sefaria",
    max_verse: int | None = None,
) -> Chapter:
    """Build one chapter's study units from already-fetched whole-book data."""
    if chapter < 1 or chapter - 1 >= len(book_text):
        raise ContentError(
            f"{book.sefaria_title} has no chapter {chapter} in the loaded data "
            f"({len(book_text)} chapters available)"
        )

    verses_raw = book_text[chapter - 1]
    if not verses_raw:
        raise ContentError(f"{book.sefaria_title} {chapter} is empty in the loaded data")
    if max_verse is not None:
        verses_raw = verses_raw[:max_verse]

    units: list[StudyUnit] = []
    for index, raw in enumerate(verses_raw, start=1):
        reference = VerseReference(book.sefaria_title, chapter, index)
        canonical = reference.canonical_ref()

        if not raw or not raw.strip():
            raise ContentError(f"{canonical} is empty in the loaded data")

        hebrew_text = convert_verse(raw, reference=canonical)
        assert_internal_markup_only(hebrew_text, reference=canonical)
        if not hebrew_text:
            raise ContentError(f"{canonical} converted to an empty string")

        verse = Verse(
            book=book.sefaria_title,
            chapter=chapter,
            verse=index,
            hebrew_text=hebrew_text,
            source_provider=provider_name,
            source_version=text_version,
        )

        entries: list[CommentaryEntry] = []
        for name in config.commentaries:
            commentator: CommentatorInfo = config.commentator(name)
            raw_entries = _commentary_for(commentary.get(name, []), chapter, index)
            for entry_number, raw_entry in enumerate(raw_entries, start=1):
                if not raw_entry or not raw_entry.strip():
                    # An empty slot is "no entry", not a defect — but it must not become
                    # an empty commentary block (SPEC.md §22).
                    continue
                source_reference = reference.commentary_ref(
                    commentator.sefaria_prefix, entry_number
                )
                converted = convert_commentary_entry(raw_entry, reference=source_reference)
                assert_internal_markup_only(converted.text, reference=source_reference)
                if not converted.text and not converted.dibur_hamatchil:
                    raise ContentError(f"{source_reference} converted to an empty entry")
                entries.append(
                    CommentaryEntry(
                        commentator=name,
                        book=book.sefaria_title,
                        chapter=chapter,
                        verse=index,
                        entry_number=entry_number,
                        dibur_hamatchil=converted.dibur_hamatchil,
                        text=converted.text,
                        source_provider=provider_name,
                        source_version=commentary_versions.get(name, ""),
                        source_reference=source_reference,
                    )
                )

        units.append(StudyUnit(verse=verse, commentaries=entries))

    return Chapter(book=book.sefaria_title, number=chapter, study_units=units)


def stats(chapters: list[Chapter]) -> BuildStats:
    units = [unit for chapter in chapters for unit in chapter.study_units]
    with_commentary = sum(1 for unit in units if unit.has_commentary)
    return BuildStats(
        verses=len(units),
        commentary_entries=sum(len(unit.commentaries) for unit in units),
        verses_with_commentary=with_commentary,
        verses_without_commentary=len(units) - with_commentary,
    )


@dataclass(frozen=True)
class ChapterSelection:
    """What to build: a book, and optionally a single chapter and a verse ceiling.

    The verse ceiling exists for the POC (בראשית א׳:א׳–י׳, SPEC.md §34) and for nothing
    else; a full build never sets it.
    """

    book: BookInfo
    chapters: tuple[int, ...] | None = None
    max_verse: int | None = None


def load_chapters(
    provider,
    config: Config,
    selections: list[ChapterSelection],
) -> tuple[list[Chapter], dict[str, str], dict[str, dict[str, str]]]:
    """Fetch whole books once and slice the requested chapters out of them in memory.

    Returns the chapters, the text version per book, and the commentary version per
    commentator per book (``{"Rashi": {"Genesis": "…"}}``) — the versions travel with the
    content so the מקורות page and the build manifest report what was actually used, not
    what config hoped for.
    """
    chapters: list[Chapter] = []
    text_versions: dict[str, str] = {}
    commentary_versions: dict[str, dict[str, str]] = {}

    for selection in selections:
        book = selection.book
        title = book.sefaria_title

        book_text = provider.get_book_text(title)
        text_versions[title] = provider.text_source(title).version_title

        commentary: dict[str, list[list[list[str]]]] = {}
        book_versions: dict[str, str] = {}
        for name in config.commentaries:
            if not provider.has_commentary(name, title):
                # Coverage is uneven; a book without Rashi renders verses only.
                continue
            commentary[name] = provider.get_book_commentary(name, title)
            version = provider.commentary_source(name, title).version_title
            book_versions[name] = version
            commentary_versions.setdefault(name, {})[title] = version

        wanted = selection.chapters or tuple(
            number for number, verses in enumerate(book_text, start=1) if verses
        )
        for number in wanted:
            chapters.append(
                build_chapter(
                    book=book,
                    chapter=number,
                    book_text=book_text,
                    commentary=commentary,
                    config=config,
                    text_version=text_versions[title],
                    commentary_versions=book_versions,
                    provider_name=provider.text_source(title).provider,
                    max_verse=selection.max_verse,
                )
            )

    return chapters, text_versions, commentary_versions

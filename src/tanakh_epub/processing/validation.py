"""Data completeness validation — SPEC_DATA_SOURCE.md §18.

Run by ``python -m tanakh_epub validate``. Every expected count comes from Sefaria's own
index (``index_lengths``, recorded in the cache at fetch time) or from the shape of the
fetched data — nothing is hard-coded. A book passes only when:

- its chapter and verse counts match the index, and no verse is empty;
- every verse and every commentary entry converts with no unknown markup and leaves only
  internal markup behind;
- NFC loses nothing: it may reorder combining marks and split a precomposed presentation
  form (U+FB1D–FB4F) into letter + marks, but the fully decomposed text never changes;
- the commentary lines up with the text: no entry on a chapter or verse the text lacks,
  and never more entries than the commentary's own index counts. The index counts every
  version of the commentary together, so *fewer* entries is a warning naming the gap in
  the chosen version, not a failure;
- no rendered chapter file is over ``layout.max_file_kb``.

It also checks each embedded font's own character map against every character that font
will be asked to draw. A missing glyph does not fail the build — the Kindle draws that
character from a fallback font — but it is listed as a warning with the first place it
occurs, so it can be looked at on the device.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..books import BookInfo, BookTable
from ..config import Config
from ..providers.base import ProviderError
from .markup import (
    InternalMarkupError,
    UnknownMarkupError,
    assert_internal_markup_only,
    convert_commentary_entry,
    convert_verse,
)
from .normalize import to_nfc
from .study_units import ChapterSelection, ContentError, load_chapters

MAX_LISTED = 10
"""Problems listed per category before the report says "and N more"."""


@dataclass
class CommentaryReport:
    name: str
    index_title: str
    present: bool
    version: str = ""
    entries: int = 0
    expected_entries: int | None = None
    verses_with: int = 0
    expected_verses_with: int | None = None
    misaligned: list[str] = field(default_factory=list)


@dataclass
class BookReport:
    title: str
    version: str = ""
    chapters: int = 0
    expected_chapters: int | None = None
    verses: int = 0
    expected_verses: int | None = None
    empty_verses: list[str] = field(default_factory=list)
    unknown_markup: list[str] = field(default_factory=list)
    nfc_reordered: int = 0
    nfc_decomposed: int = 0
    """Strings with a precomposed presentation form NFC split into letter + marks."""
    nfc_lossy: list[str] = field(default_factory=list)
    commentaries: list[CommentaryReport] = field(default_factory=list)
    verses_without_commentary: int = 0
    missing_glyphs: list[str] = field(default_factory=list)
    chapter_files: int = 0
    oversized: list[str] = field(default_factory=list)
    largest_chapter_kb: float = 0.0
    error: str | None = None

    @property
    def problems(self) -> list[str]:
        out: list[str] = []
        if self.error:
            out.append(self.error)
        if self.expected_chapters is not None and self.chapters != self.expected_chapters:
            out.append(f"{self.chapters} chapters, index says {self.expected_chapters}")
        if self.expected_verses is not None and self.verses != self.expected_verses:
            out.append(f"{self.verses} verses, index says {self.expected_verses}")
        for label, items in (
            ("empty verse", self.empty_verses),
            ("unknown markup", self.unknown_markup),
            ("NFC changed the characters", self.nfc_lossy),
            ("chapter file over the size limit", self.oversized),
        ):
            out.extend(f"{label}: {item}" for item in items)
        for c in self.commentaries:
            if not c.present:
                continue
            if c.expected_entries is not None and c.entries > c.expected_entries:
                out.append(f"{c.index_title}: {c.entries} entries, index says {c.expected_entries}")
            if c.expected_verses_with is not None and c.verses_with > c.expected_verses_with:
                out.append(
                    f"{c.index_title}: {c.verses_with} verses with commentary, "
                    f"index says {c.expected_verses_with}"
                )
            out.extend(f"{c.index_title}: {item}" for item in c.misaligned)
        return out

    @property
    def warnings(self) -> list[str]:
        return [
            f"{c.index_title}: this version has {c.expected_entries - c.entries} fewer "
            f"entries than the index counts across all versions"
            for c in self.commentaries
            if c.present and c.expected_entries is not None and c.entries < c.expected_entries
        ] + self.missing_glyphs

    @property
    def ok(self) -> bool:
        return not self.problems


def _nfc_check(report: BookReport, raw: str, reference: str) -> None:
    normalized = to_nfc(raw)
    if normalized == raw:
        return
    if Counter(normalized) == Counter(raw):
        report.nfc_reordered += 1
    elif Counter(unicodedata.normalize("NFD", raw)) == Counter(normalized):
        report.nfc_decomposed += 1
    else:
        report.nfc_lossy.append(reference)


def _convert(report: BookReport, convert, raw: str, reference: str):
    try:
        converted = convert(raw, reference=reference)
        text = converted if isinstance(converted, str) else converted.text
        assert_internal_markup_only(text, reference=reference)
    except (UnknownMarkupError, InternalMarkupError) as exc:
        report.unknown_markup.append(str(exc).split(". Nothing is stripped")[0])
        return None
    return converted


_ENTITIES = {"&amp;": "&", "&lt;": "<", "&gt;": ">"}


def _characters(internal: str) -> str:
    """The characters of internal markup a font will actually be asked to draw."""
    text = re.sub(r"<[^>]*>", "", internal)
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    return "".join(c for c in text if not c.isspace())


def font_codepoints(path: Path) -> set[int] | None:
    """The font's character map, or ``None`` if fontTools is not installed."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    return set(TTFont(path).getBestCmap())


class _GlyphNeeds:
    """First reference for every character each font is asked to draw."""

    def __init__(self) -> None:
        self.by_font: dict[str, dict[str, str]] = {}

    def add(self, font: str, internal: str, reference: str) -> None:
        seen = self.by_font.setdefault(font, {})
        for char in _characters(internal):
            seen.setdefault(char, reference)

    def missing(self, config: Config) -> list[str]:
        fonts = {"biblical": config.biblical_font, "rashi": config.rashi_font}
        out: list[str] = []
        for role, needs in self.by_font.items():
            font = fonts[role]
            covered = font_codepoints(font.file)
            if covered is None:
                return ["glyph coverage not checked: fontTools is not installed"]
            for char, reference in sorted(needs.items(), key=lambda item: item[1]):
                if ord(char) not in covered:
                    name = unicodedata.name(char, "unnamed")
                    out.append(
                        f"{font.family} has no glyph for U+{ord(char):04X} {name} "
                        f"(first at {reference}); the Kindle will use a fallback font for it"
                    )
        return out


def validate_book(provider, config: Config, book: BookInfo, *, render=None) -> BookReport:
    """``render`` turns the book's chapters into ``(filename, size_bytes)`` pairs; it is
    injected so the size check uses exactly the renderer the build uses."""
    title = book.sefaria_title
    report = BookReport(title=title)
    try:
        text = provider.get_book_text(title)
        report.version = provider.text_source(title).version_title
    except ProviderError as exc:
        report.error = str(exc)
        return report

    lengths = provider.index_lengths(title)
    if lengths:
        report.expected_chapters, report.expected_verses = lengths[0], lengths[1]

    glyphs = _GlyphNeeds()
    commentary_font = "rashi" if config.typography.rashi_script else "biblical"
    dibur_font = (
        "biblical" if config.typography.dibur_hamatchil_in_biblical_font else commentary_font
    )

    report.chapters = len(text)
    for c_number, chapter in enumerate(text, start=1):
        if not chapter:
            report.empty_verses.append(f"{title} {c_number} (whole chapter)")
        for v_number, raw in enumerate(chapter, start=1):
            reference = f"{title} {c_number}:{v_number}"
            report.verses += 1
            if not raw or not raw.strip():
                report.empty_verses.append(reference)
                continue
            _nfc_check(report, raw, reference)
            converted = _convert(report, convert_verse, raw, reference)
            if converted:
                glyphs.add("biblical", converted, reference)

    verses_with_any: set[tuple[int, int]] = set()
    for name in config.commentaries:
        commentator = config.commentator(name)
        index_title = commentator.index_title(title)
        c_report = CommentaryReport(name, index_title, provider.has_commentary(name, title))
        report.commentaries.append(c_report)
        if not c_report.present:
            continue
        commentary = provider.get_book_commentary(name, title)
        c_report.version = provider.commentary_source(name, title).version_title
        c_lengths = provider.index_lengths(title, name)
        if c_lengths and len(c_lengths) >= 3:
            c_report.expected_verses_with, c_report.expected_entries = c_lengths[1], c_lengths[2]
        for c_number, chapter in enumerate(commentary, start=1):
            for v_number, entries in enumerate(chapter or [], start=1):
                entries = [e for e in (entries or []) if e and e.strip()]
                if not entries:
                    continue
                if c_number > len(text) or v_number > len(text[c_number - 1]):
                    c_report.misaligned.append(
                        f"{index_title} {c_number}:{v_number} has no verse in {title}"
                    )
                c_report.verses_with += 1
                verses_with_any.add((c_number, v_number))
                for e_number, raw in enumerate(entries, start=1):
                    reference = f"{index_title} {c_number}:{v_number}:{e_number}"
                    c_report.entries += 1
                    _nfc_check(report, raw, reference)
                    converted = _convert(report, convert_commentary_entry, raw, reference)
                    if converted:
                        glyphs.add(commentary_font, converted.text, reference)
                        if converted.dibur_hamatchil:
                            glyphs.add(
                                dibur_font,
                                converted.dibur_hamatchil,
                                f"{reference}, opening words",
                            )
    report.verses_without_commentary = report.verses - len(verses_with_any)
    report.missing_glyphs = glyphs.missing(config)

    if render is not None and not report.unknown_markup and not report.empty_verses:
        try:
            chapters, _, _ = load_chapters(provider, config, [ChapterSelection(book)])
        except (ContentError, ProviderError) as exc:
            report.error = f"could not assemble the chapters: {exc}"
            return report
        sizes = render(chapters)
        report.chapter_files = len(sizes)
        limit = config.layout.max_file_kb * 1024
        report.largest_chapter_kb = max((size for _, size in sizes), default=0) / 1024
        report.oversized = [
            f"{name} ({size / 1024:.0f} KB)" for name, size in sizes if size > limit
        ]

    return report


def validate(provider, config: Config, books: BookTable, titles: list[str], *, render=None):
    return [validate_book(provider, config, books.by_title(t), render=render) for t in titles]


def _listed(items: list[str]) -> list[str]:
    shown = [f"    {item}" for item in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        shown.append(f"    … and {len(items) - MAX_LISTED} more")
    return shown


def format_report(reports: list[BookReport], config: Config, books: BookTable) -> str:
    versions = [f"tanakh version: {config.tanakh_source.version_title}"]
    versions += [
        f"{name} version: {config.commentary_sources[name].version_title}"
        for name in config.commentaries
    ]
    total_books = len(books)
    present = [r for r in reports if not r.error]
    chapters = sum(r.chapters for r in present)
    expected_chapters = sum(r.expected_chapters or r.chapters for r in present)
    verses = sum(r.verses for r in present)
    expected_verses = sum(r.expected_verses or r.verses for r in present)

    lines = ["VALIDATION REPORT", *(f"  {v}" for v in versions), ""]
    lines.append(f"Books checked:        {len(reports)} / {total_books}")
    lines.append(f"Chapters:          {chapters:6,} / {expected_chapters:,}")
    lines.append(f"Verses:            {verses:6,} / {expected_verses:,}")
    lines.append(f"Empty verses:      {sum(len(r.empty_verses) for r in present):6,}")
    lines.append(f"Unknown markup:    {sum(len(r.unknown_markup) for r in present):6,}")
    lines.append(
        f"NFC:               {sum(r.nfc_reordered for r in present):6,} strings reordered, "
        f"{sum(r.nfc_decomposed for r in present)} with presentation forms decomposed, "
        f"{sum(len(r.nfc_lossy) for r in present)} changed"
    )
    for name in config.commentaries:
        with_it = [r.title for r in present for c in r.commentaries if c.name == name and c.present]
        without = [r.title for r in present if r.title not in with_it]
        entries = sum(c.entries for r in present for c in r.commentaries if c.name == name)
        lines.append(
            f"Books with {name}:     {len(with_it)} / {len(present)}"
            + (f"   (without: {', '.join(without)})" if without else "")
        )
        lines.append(f"{name} entries:     {entries:6,}")
    lines.append(
        f"Verses with commentary: {sum(r.verses - r.verses_without_commentary for r in present):,}"
    )
    lines.append(f"Verses without:         {sum(r.verses_without_commentary for r in present):,}")
    files = sum(r.chapter_files for r in present)
    if files:
        largest = max(r.largest_chapter_kb for r in present)
        lines.append(
            f"Chapter files > {config.layout.max_file_kb} KB: "
            f"{sum(len(r.oversized) for r in present)} of {files} (largest {largest:.0f} KB)"
        )
    else:
        lines.append("Chapter files: not rendered (fix the problems above first)")

    failing = [r for r in reports if not r.ok]
    warned = [(r.title, w) for r in reports for w in r.warnings]
    if warned:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"  {warning}" for _, warning in warned)
    lines.append("")
    if not failing:
        lines.append("RESULT: clean")
    else:
        lines.append(f"RESULT: {len(failing)} book(s) with problems")
        for r in failing:
            lines.append(f"  {r.title}")
            lines.extend(_listed(r.problems))
    return "\n".join(lines) + "\n"

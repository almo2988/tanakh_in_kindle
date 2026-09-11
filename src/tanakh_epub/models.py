"""Internal data model — SPEC.md §19.

This is the only shape the rendering layer ever sees. Providers convert whatever the
source gives them into these objects; nothing downstream knows that Sefaria exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VerseReference:
    """A canonical English reference — SPEC_DATA_SOURCE.md §6.

    English internally, Hebrew only at render time (SPEC_DATA_SOURCE.md §16).
    """

    book: str
    chapter: int
    verse: int

    def canonical_ref(self) -> str:
        """`Genesis 1:1`."""
        return f"{self.book} {self.chapter}:{self.verse}"

    def commentary_ref(self, prefix: str, entry: int) -> str:
        """`Rashi on Genesis 1:1:1`."""
        return f"{prefix}{self.canonical_ref()}:{entry}"


@dataclass(frozen=True)
class Verse:
    book: str
    """Sefaria English title, e.g. "Genesis"."""

    chapter: int
    verse: int

    hebrew_text: str
    """NFC; source markup already converted to internal markup (SPEC_DATA_SOURCE.md §9.3)."""

    source_provider: str
    source_version: str
    """The exact Sefaria versionTitle the text came from."""

    @property
    def reference(self) -> VerseReference:
        return VerseReference(self.book, self.chapter, self.verse)


@dataclass(frozen=True)
class CommentaryEntry:
    commentator: str
    """Key in config/commentators.yaml, e.g. "Rashi"."""

    book: str
    chapter: int
    verse: int

    entry_number: int
    """1-based, in source order. Never reordered (SPEC.md §23)."""

    dibur_hamatchil: str | None
    """Extracted from the entry's own leading <b> element, not by text matching."""

    text: str
    """NFC; internal markup, with the dibur hamatchil removed."""

    source_provider: str
    source_version: str
    source_reference: str
    """Full Sefaria reference, e.g. "Rashi on Genesis 1:1:1"."""


@dataclass(frozen=True)
class StudyUnit:
    """One verse and the commentary attached to it — SPEC.md §2."""

    verse: Verse
    commentaries: list[CommentaryEntry] = field(default_factory=list)
    """May be empty; source order preserved."""

    @property
    def has_commentary(self) -> bool:
        return bool(self.commentaries)


@dataclass(frozen=True)
class Chapter:
    book: str
    number: int
    study_units: list[StudyUnit]


@dataclass(frozen=True)
class Book:
    sefaria_title: str
    chapters: list[Chapter]

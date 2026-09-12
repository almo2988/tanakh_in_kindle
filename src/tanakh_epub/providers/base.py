"""Provider contracts — SPEC.md §20.

Content retrieval is separated from rendering. Providers hand over whole books; per-verse
access is an in-memory lookup over what they returned (SPEC_DATA_SOURCE.md §2). Nothing
below this layer performs HTTP, and nothing above it sees a provider response format.

The two ``get_book_*`` signatures are exactly the ones in SPEC.md §20. The ``*_source``
methods are the necessary companion: ``Verse.source_version`` and
``CommentaryEntry.source_version`` are required fields of the model, so the version a book
actually came from has to travel with it rather than being assumed from config.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import SourceInfo


class ProviderError(RuntimeError):
    """Raised when required content cannot be provided — SPEC_DATA_SOURCE.md §17.

    Never swallowed into a partial book: an incomplete Tanakh that looks complete is the
    one failure mode this project cannot tolerate.
    """


@runtime_checkable
class TextProvider(Protocol):
    def get_books(self) -> list[str]:
        """Sefaria index titles this provider can serve."""

    def get_book_text(self, book: str) -> list[list[str]]:
        """``[chapter][verse]`` → raw source string, index ``i`` being chapter ``i + 1``.

        Empty inner lists mean "no text here" (SPEC_DATA_SOURCE.md §3).
        """

    def text_source(self, book: str) -> SourceInfo:
        """Provenance of what ``get_book_text`` just returned."""


@runtime_checkable
class CommentaryProvider(Protocol):
    def get_book_commentary(self, commentator: str, book: str) -> list[list[list[str]]]:
        """``[chapter][verse][entry]`` → raw source string, structurally aligned with the
        base text (SPEC_DATA_SOURCE.md §3). A missing index is "no commentary for this
        book", not a failure (SPEC_DATA_SOURCE.md §5).
        """

    def commentary_source(self, commentator: str, book: str) -> SourceInfo:
        """Provenance of what ``get_book_commentary`` just returned."""

    def has_commentary(self, commentator: str, book: str) -> bool:
        """Whether this provider has any commentary for the book at all."""

"""Offline provider — reads checked-in fixtures and cached/processed JSON.

Phase 1 builds entirely through this provider: `tests/fixtures/` holds real Sefaria data
captured once by `scripts/capture_fixtures.py`, so the build and the whole test suite run
with no network at all. In Phase 2 the Sefaria provider fills `data/cache/` in the same
file shape and this class keeps working unchanged — it is the reader, not the fetcher.

File shape (SPEC_DATA_SOURCE.md §11):

    {"index": "Genesis", "kind": "text", "version_title": "...", "license": "...",
     "language": "he", "source": "api", "fetched_at": "...", "depth": 2,
     "chapters_included": [1], "text": [[verse, ...], ...]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..books import BookTable, default_books
from ..config import SourceInfo
from ..paths import CACHE_DIR, FIXTURES_DIR
from .base import ProviderError


@dataclass(frozen=True)
class _Dataset:
    path: Path
    index: str
    kind: str
    depth: int
    text: list
    source: SourceInfo
    chapters_included: tuple[int, ...]
    index_lengths: tuple[int, ...] | None
    """Sefaria's own counts for the index, recorded at fetch time; absent in fixtures."""

    def chapter(self, number: int) -> list:
        if number not in self.chapters_included:
            available = ", ".join(str(c) for c in self.chapters_included) or "none"
            raise ProviderError(
                f'{self.path.name} has no chapter {number} of "{self.index}" '
                f"(chapters in this dataset: {available})"
            )
        return self.text[self.chapters_included.index(number)]

    def padded(self) -> list:
        """``[chapter][...]`` with index ``i`` meaning chapter ``i + 1``.

        A partial dataset — a fixture holding one chapter — pads the chapters it does not
        have with empty lists, which is already Sefaria's own way of saying "no text here"
        (SPEC_DATA_SOURCE.md §3). That keeps the provider contract in SPEC.md §20 exactly
        as written, whatever subset happens to be on disk.
        """
        out: list = [[] for _ in range(max(self.chapters_included, default=0))]
        for number, chapter in zip(self.chapters_included, self.text, strict=True):
            out[number - 1] = chapter
        return out


def _load(path: Path) -> _Dataset:
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProviderError(f"No local data at {path}") from None
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{path} is not valid JSON: {exc}") from None

    for required in ("index", "version_title", "text", "depth"):
        if required not in raw:
            raise ProviderError(f'{path} is missing "{required}"')

    text = raw["text"]
    included = raw.get("chapters_included")
    if included is None:
        included = list(range(1, len(text) + 1))
    if len(included) != len(text):
        raise ProviderError(
            f"{path}: chapters_included lists {len(included)} chapters but text has {len(text)}"
        )

    return _Dataset(
        path=path,
        index=raw["index"],
        kind=raw.get("kind", "text"),
        depth=int(raw["depth"]),
        text=text,
        source=SourceInfo(
            provider=raw.get("provider", "Sefaria"),
            version_title=raw["version_title"],
            language=raw.get("language", "he"),
            license=raw.get("license") or "unknown",
            source_url=raw.get("version_source"),
            checked=raw.get("fetched_at"),
        ),
        chapters_included=tuple(int(c) for c in included),
        index_lengths=tuple(raw["index_lengths"]) if raw.get("index_lengths") else None,
    )


class LocalProvider:
    """Serves whole books out of one directory of JSON files.

    ``roots`` are searched in order. The default puts the cache first, so a book fetched
    from Sefaria shadows its one-chapter fixture; the test suite passes the fixtures alone.
    """

    def __init__(
        self,
        roots: list[Path] | None = None,
        *,
        books: BookTable | None = None,
        expected_versions: dict[str, str] | None = None,
    ) -> None:
        self.roots = roots or [CACHE_DIR, FIXTURES_DIR]
        self.books = books or default_books()
        self.expected_versions = expected_versions or {}
        self._cache: dict[Path, _Dataset] = {}

    # ---- locating files -------------------------------------------------

    def _candidates(self, book: str, commentator: str | None) -> list[Path]:
        info = self.books.by_title(book)
        if commentator is None:
            names = [f"{info.slug}_1.json", f"{info.slug}.json"]
            subdir = "tanakh"
        else:
            slug = commentator.lower()
            names = [f"{slug}_{info.slug}_1.json", f"{info.slug}.json"]
            subdir = slug
        paths: list[Path] = []
        for root in self.roots:
            paths.extend(root / name for name in names)
            paths.extend(root / subdir / name for name in names)
        return paths

    def _dataset(self, book: str, commentator: str | None) -> _Dataset:
        for path in self._candidates(book, commentator):
            if path.is_file():
                if path not in self._cache:
                    self._cache[path] = _load(path)
                return self._cache[path]
        label = book if commentator is None else f"{commentator} on {book}"
        looked_in = "\n  ".join(str(p) for p in self._candidates(book, commentator))
        raise ProviderError(f"No local data for {label}. Looked in:\n  {looked_in}")

    def _checked(self, dataset: _Dataset, key: str, book: str) -> _Dataset:
        """A dataset whose version differs from config is a miss, never a silent mix.

        SPEC_DATA_SOURCE.md §11. ``expected_versions`` may name a version per book as
        ``"Rashi:Isaiah"``; that wins over the commentator-wide ``"Rashi"``.
        """
        expected = self.expected_versions.get(f"{key}:{book}") or self.expected_versions.get(key)
        if expected and dataset.source.version_title != expected:
            raise ProviderError(
                f'{dataset.path.name} holds version "{dataset.source.version_title}" '
                f'but the build is configured for "{expected}". '
                f"Refusing to mix versions."
            )
        return dataset

    # ---- TextProvider ---------------------------------------------------

    def get_books(self) -> list[str]:
        found = []
        for book in self.books:
            try:
                self._dataset(book.sefaria_title, None)
            except ProviderError:
                continue
            found.append(book.sefaria_title)
        return found

    def get_book_text(self, book: str) -> list[list[str]]:
        dataset = self._checked(self._dataset(book, None), "tanakh", book)
        if dataset.depth != 2:
            raise ProviderError(f"{dataset.path.name} has depth {dataset.depth}, expected 2")
        return dataset.padded()

    def text_source(self, book: str) -> SourceInfo:
        return self._dataset(book, None).source

    def index_lengths(self, book: str, commentator: str | None = None) -> tuple[int, ...] | None:
        return self._dataset(book, commentator).index_lengths

    def dataset_path(self, book: str, commentator: str | None = None) -> Path:
        return self._dataset(book, commentator).path

    def available_chapters(self, book: str) -> tuple[int, ...]:
        return self._dataset(book, None).chapters_included

    def get_chapter_text(self, book: str, chapter: int) -> list[str]:
        return self._checked(self._dataset(book, None), "tanakh", book).chapter(chapter)

    # ---- CommentaryProvider ---------------------------------------------

    def has_commentary(self, commentator: str, book: str) -> bool:
        try:
            self._dataset(book, commentator)
        except ProviderError:
            return False
        return True

    def get_book_commentary(self, commentator: str, book: str) -> list[list[list[str]]]:
        dataset = self._checked(self._dataset(book, commentator), commentator, book)
        if dataset.depth != 3:
            raise ProviderError(f"{dataset.path.name} has depth {dataset.depth}, expected 3")
        return dataset.padded()

    def commentary_source(self, commentator: str, book: str) -> SourceInfo:
        return self._dataset(book, commentator).source

    def get_chapter_commentary(self, commentator: str, book: str, chapter: int) -> list[list[str]]:
        return self._checked(self._dataset(book, commentator), commentator, book).chapter(chapter)

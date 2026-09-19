"""Fill the cache — the ``fetch`` command (SPEC_DATA_SOURCE.md §11–§12).

For each requested book: the Tanakh text in the configured version, then each configured
commentary. A cached file is reused when it holds the configured version; a file holding a
different version counts as missing and is fetched again (never mixed silently). A
commentary index that does not exist on Sefaria is "no commentary for this book" — logged
and reported, not an error (§5). A configured *version* that does not exist is an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..books import BookInfo
from ..config import Config
from .base import ProviderError
from .sefaria import NotFound, SefariaProvider, cache_path, cached_version, write_cache


@dataclass(frozen=True)
class FetchOutcome:
    label: str
    """``Genesis`` or ``Rashi on Genesis``."""

    status: str
    """``fetched`` · ``cached`` · ``absent`` (no such commentary index) · ``failed``."""

    path: Path | None = None
    detail: str = ""


def fetch_book(
    provider: SefariaProvider,
    config: Config,
    book: BookInfo,
    *,
    cache_dir: Path,
    refresh: bool = False,
) -> list[FetchOutcome]:
    outcomes = [
        _fetch_one(
            provider,
            label=book.sefaria_title,
            version_title=config.tanakh_source.version_title,
            path=cache_path(cache_dir, "tanakh", book.slug),
            kind="text",
            depth=2,
            refresh=refresh,
        )
    ]
    for name in config.commentaries:
        commentator = config.commentator(name)
        index_title = commentator.index_title(book.sefaria_title)
        try:
            provider.get_index(index_title)
        except NotFound:
            outcomes.append(FetchOutcome(index_title, "absent", detail="Sefaria has no such index"))
            continue
        except ProviderError as exc:
            outcomes.append(FetchOutcome(index_title, "failed", detail=str(exc)))
            continue
        outcomes.append(
            _fetch_one(
                provider,
                label=index_title,
                version_title=config.commentary_source(name, book.sefaria_title).version_title,
                path=cache_path(cache_dir, commentator.slug, book.slug),
                kind="commentary",
                depth=3,
                refresh=refresh,
                commentator=name,
            )
        )
    return outcomes


def _fetch_one(
    provider: SefariaProvider,
    *,
    label: str,
    version_title: str,
    path: Path,
    kind: str,
    depth: int,
    refresh: bool,
    commentator: str | None = None,
) -> FetchOutcome:
    held = cached_version(path)
    if held == version_title and not refresh:
        return FetchOutcome(label, "cached", path)
    try:
        fetched = provider.fetch_book(label, version_title=version_title, depth=depth)
    except ProviderError as exc:
        return FetchOutcome(label, "failed", path, str(exc))
    write_cache(path, fetched, kind=kind, depth=depth, commentator=commentator)
    replaced = f' (replaced version "{held}")' if held and held != version_title else ""
    return FetchOutcome(label, "fetched", path, f"from {fetched.source}{replaced}")

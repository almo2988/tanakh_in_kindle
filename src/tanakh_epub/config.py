"""Build configuration — SPEC.md §30.

A thin, validated view over ``config/default.yaml``. Values that the renderer or the EPUB
writer depend on are pulled out into frozen dataclasses so a typo in the YAML fails here,
with a path, rather than three layers down as a ``KeyError`` or a silently missing style.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .paths import COMMENTATORS_CONFIG, DEFAULT_CONFIG, PROJECT_ROOT


@dataclass(frozen=True)
class SourceInfo:
    """Provenance of one text — feeds the מקורות page and the build manifest."""

    provider: str
    version_title: str
    language: str
    license: str
    source_url: str | None = None
    checked: str | None = None


@dataclass(frozen=True)
class FontInfo:
    file: Path
    family: str
    name: str
    license: str
    license_file: Path | None

    @property
    def suffix(self) -> str:
        return self.file.suffix.lower()


@dataclass(frozen=True)
class Typography:
    biblical_scale: float
    rashi_scale: float
    verse_number_scale: float
    divider_scale: float
    rashi_script: bool
    dibur_hamatchil_in_biblical_font: bool


@dataclass(frozen=True)
class Layout:
    file_per: str
    max_file_kb: int
    page_break_before_book: bool


@dataclass(frozen=True)
class Navigation:
    include_sections: bool
    include_books: bool
    include_chapters: bool


@dataclass(frozen=True)
class CommentatorInfo:
    name: str
    """Key in config/commentators.yaml, e.g. "Rashi" — used internally only."""

    hebrew: str
    """The divider label the reader sees."""

    slug: str
    sefaria_prefix: str

    def index_title(self, book_sefaria_title: str) -> str:
        """``Rashi on Genesis``."""
        return f"{self.sefaria_prefix}{book_sefaria_title}"


@dataclass(frozen=True)
class Config:
    title: str
    creator: str
    publisher: str
    delivery: str
    device: str
    commentaries: tuple[str, ...]
    tanakh_source: SourceInfo
    commentary_sources: dict[str, SourceInfo]
    biblical_font: FontInfo
    rashi_font: FontInfo
    typography: Typography
    layout: Layout
    navigation: Navigation
    cover_mode: str
    show_empty_commentary: bool
    output_dir: Path
    output_filename: str
    commentators: dict[str, CommentatorInfo]
    raw: dict[str, Any]
    path: Path

    def commentator(self, name: str) -> CommentatorInfo:
        try:
            return self.commentators[name]
        except KeyError:
            raise KeyError(
                f'"{name}" is not in config/commentators.yaml. '
                f"Commentator labels and slugs are never hard-coded."
            ) from None

    @property
    def config_hash(self) -> str:
        """Stable hash of the config file, for the build manifest."""
        canonical = yaml.safe_dump(self.raw, sort_keys=True, allow_unicode=True)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _font(raw: dict[str, Any], key: str, config_path: Path) -> FontInfo:
    try:
        entry = raw["fonts"][key]
    except KeyError:
        raise ValueError(f"{config_path}: fonts.{key} is missing") from None

    file = PROJECT_ROOT / entry["file"]
    if not file.is_file():
        raise FileNotFoundError(
            f"{config_path}: fonts.{key}.file points at {file}, which does not exist"
        )
    if not entry.get("license"):
        # CLAUDE.md non-negotiable 9.
        raise ValueError(
            f"{config_path}: fonts.{key} has no recorded license. "
            f"A font whose license has not been checked is never embedded."
        )

    license_file = entry.get("license_file")
    return FontInfo(
        file=file,
        family=entry["family"],
        name=entry.get("name", entry["family"]),
        license=entry["license"],
        license_file=PROJECT_ROOT / license_file if license_file else None,
    )


def _source(entry: dict[str, Any], label: str, config_path: Path) -> SourceInfo:
    for required in ("provider", "version_title", "language", "license"):
        if not entry.get(required):
            raise ValueError(f"{config_path}: {label}.{required} is missing")
    return SourceInfo(
        provider=entry["provider"],
        version_title=entry["version_title"],
        language=entry["language"],
        license=entry["license"],
        source_url=entry.get("source_url"),
        checked=str(entry["checked"]) if entry.get("checked") else None,
    )


def load_commentators(path: Path | None = None) -> dict[str, CommentatorInfo]:
    path = path or COMMENTATORS_CONFIG
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, CommentatorInfo] = {}
    for name, entry in (raw.get("commentators") or {}).items():
        missing = {"hebrew", "slug", "sefaria_prefix"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: commentator {name} is missing {sorted(missing)}")
        out[name] = CommentatorInfo(
            name=name,
            hebrew=entry["hebrew"],
            slug=entry["slug"],
            sefaria_prefix=entry["sefaria_prefix"],
        )
    if not out:
        raise ValueError(f"{path} defines no commentators")
    return out


def load_config(path: Path | None = None) -> Config:
    path = path or DEFAULT_CONFIG
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    commentaries = tuple((raw.get("include") or {}).get("commentaries") or [])
    commentators = load_commentators()
    for name in commentaries:
        if name not in commentators:
            raise ValueError(
                f'{path}: include.commentaries lists "{name}", '
                f"which is not defined in config/commentators.yaml"
            )

    sources = raw.get("sources") or {}
    commentary_sources = {
        name: _source(entry, f"sources.commentaries.{name}", path)
        for name, entry in (sources.get("commentaries") or {}).items()
    }
    for name in commentaries:
        if name not in commentary_sources:
            raise ValueError(f"{path}: no sources.commentaries entry for {name}")

    typography_raw = raw.get("typography") or {}
    layout_raw = raw.get("layout") or {}
    navigation_raw = raw.get("navigation") or {}

    if layout_raw.get("file_per", "chapter") != "chapter":
        # SPEC.md §11: one file per book is withdrawn, not configurable.
        raise ValueError(f'{path}: layout.file_per must be "chapter"')

    return Config(
        title=raw["title"],
        creator=raw.get("creator", ""),
        publisher=raw.get("publisher", ""),
        delivery=(raw.get("target") or {}).get("delivery", "calibre-kfx"),
        device=(raw.get("target") or {}).get("device", ""),
        commentaries=commentaries,
        tanakh_source=_source(sources["tanakh"], "sources.tanakh", path),
        commentary_sources=commentary_sources,
        biblical_font=_font(raw, "biblical", path),
        rashi_font=_font(raw, "rashi", path),
        typography=Typography(
            biblical_scale=float(typography_raw.get("biblical_scale", 1.25)),
            rashi_scale=float(typography_raw.get("rashi_scale", 0.85)),
            verse_number_scale=float(typography_raw.get("verse_number_scale", 0.75)),
            divider_scale=float(typography_raw.get("divider_scale", 0.85)),
            rashi_script=bool(typography_raw.get("rashi_script", True)),
            dibur_hamatchil_in_biblical_font=bool(
                typography_raw.get("dibur_hamatchil_in_biblical_font", True)
            ),
        ),
        layout=Layout(
            file_per="chapter",
            max_file_kb=int(layout_raw.get("max_file_kb", 300)),
            page_break_before_book=bool(layout_raw.get("page_break_before_book", True)),
        ),
        navigation=Navigation(
            include_sections=bool(navigation_raw.get("include_sections", False)),
            include_books=bool(navigation_raw.get("include_books", True)),
            include_chapters=bool(navigation_raw.get("include_chapters", True)),
        ),
        cover_mode=(raw.get("cover") or {}).get("mode", "none"),
        show_empty_commentary=bool((raw.get("debug") or {}).get("show_empty_commentary", False)),
        output_dir=PROJECT_ROOT / (raw.get("output") or {}).get("dir", "output"),
        output_filename=(raw.get("output") or {}).get("filename", "Tanakh_with_Rashi.epub"),
        commentators=commentators,
        raw=raw,
        path=path,
    )

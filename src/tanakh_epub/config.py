"""Build configuration — SPEC.md §30.

A thin, validated view over ``config/default.yaml``. Values that the renderer or the EPUB
writer depend on are pulled out into frozen dataclasses so a typo in the YAML fails here,
with a path, rather than three layers down as a ``KeyError`` or a silently missing style.
"""

from __future__ import annotations

import dataclasses
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
    biblical_line_height: float = 1.9
    rashi_line_height: float = 1.65


@dataclass(frozen=True)
class Spacing:
    """Vertical space, in ``em`` of the element it sits on — exactly as CSS reads it.

    Defaults are the values the stylesheet carried before layout profiles existed, so a
    config without a ``spacing`` section renders as it always did.
    """

    study_unit: float = 1.1
    verse: float = 0.35
    divider_margin_top: float = 0.5
    divider_padding_top: float = 0.15
    divider_padding_bottom: float = 0.15
    divider_margin_bottom: float = 0.4
    divider_align: str = "center"
    entry: float = 0.4
    rashi_paragraph: float = 0.3


@dataclass(frozen=True)
class Breaks:
    """The optional page-break hints (SPEC §27). Two hints are not optional and so are not
    here: verse + divider + first entry stay together, and a chapter heading stays with
    what follows it. Everything here is a hint a reader may ignore."""

    keep_each_entry_together: bool = False
    keep_divider_with_neighbours: bool = False
    keep_book_heading_with_next: bool = False


@dataclass(frozen=True)
class LayoutProfile:
    name: str
    """Key under ``layout_profiles`` — e.g. ``dense``."""

    label: str
    """Stable developer-facing id, e.g. ``C-dense``. Never shown to the reader."""

    hebrew_label: str
    """What the reader sees in the title of an experiment build, e.g. ``פריסה ג׳``."""

    description: str


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
    """The commentator's first configured version — the one for Genesis. Per-book versions
    are in ``commentary_book_sources``; use ``commentary_source(name, book)``."""

    commentary_book_sources: dict[str, dict[str, SourceInfo]]
    """``{commentator: {book: source}}`` for commentaries configured with ``versions``."""
    biblical_font: FontInfo
    rashi_font: FontInfo
    typography: Typography
    spacing: Spacing
    breaks: Breaks
    layout_profile: LayoutProfile
    layout_profiles: dict[str, LayoutProfile]
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

    def commentary_source(self, name: str, book: str) -> SourceInfo:
        """The version of ``name`` configured for ``book`` (D6: one per group of books)."""
        by_book = self.commentary_book_sources.get(name) or {}
        if not by_book:
            return self.commentary_sources[name]
        try:
            return by_book[book]
        except KeyError:
            raise KeyError(
                f"sources.commentaries.{name}.versions names no version for {book}"
            ) from None

    def commentary_versions_for(
        self, name: str, books: list[str] | None = None
    ) -> list[SourceInfo]:
        """The distinct versions of ``name`` used by ``books`` (default: every configured
        book), in the order they are configured."""
        by_book = self.commentary_book_sources.get(name) or {}
        if not by_book:
            return [self.commentary_sources[name]]
        wanted = by_book.keys() if books is None else [b for b in books if b in by_book]
        out: list[SourceInfo] = []
        for source in by_book.values():
            if source not in out and any(by_book[b] == source for b in wanted):
                out.append(source)
        return out

    @property
    def config_hash(self) -> str:
        """Stable hash of the config file and the layout profile applied to it, for the build
        manifest — and for the identifier, so the layout variants of the same content
        sit side by side on the device instead of replacing one another."""
        canonical = yaml.safe_dump(
            {"config": self.raw, "layout_profile": self.layout_profile.name},
            sort_keys=True,
            allow_unicode=True,
        )
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


def _versions_by_book(
    entry: dict[str, Any], label: str, config_path: Path
) -> dict[str, SourceInfo]:
    """``versions:`` — a list of versions, each naming the books it covers. Shared keys
    (``provider``, ``language``, ``checked``) sit on the commentator and may be overridden
    per version. A book named twice is an error: which version it gets must be obvious."""
    shared = {k: v for k, v in entry.items() if k != "versions"}
    by_book: dict[str, SourceInfo] = {}
    for index, version in enumerate(entry.get("versions") or []):
        item_label = f"{label}.versions[{index}]"
        books = version.get("books") or []
        if not books:
            raise ValueError(f"{config_path}: {item_label} lists no books")
        source = _source({**shared, **version}, item_label, config_path)
        for book in books:
            if book in by_book:
                raise ValueError(f"{config_path}: {book} is in more than one {label}.versions")
            by_book[book] = source
    if not by_book:
        raise ValueError(f"{config_path}: {label}.versions is empty")
    return by_book


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


PROFILE_TYPOGRAPHY_KEYS = frozenset(
    {
        "biblical_scale",
        "rashi_scale",
        "verse_number_scale",
        "divider_scale",
        "biblical_line_height",
        "rashi_line_height",
    }
)
"""What a layout profile may change in ``typography``: sizes and line heights only. Which
font sets the commentary is a font decision (D3), not a layout one, so every variant of
the experiment is set in the same faces."""

PROFILE_SECTIONS = {
    "typography": PROFILE_TYPOGRAPHY_KEYS,
    "spacing": frozenset(f.name for f in dataclasses.fields(Spacing)),
    "breaks": frozenset(f.name for f in dataclasses.fields(Breaks)),
}
PROFILE_META_KEYS = frozenset({"label", "hebrew_label", "description", "extends"})
DIVIDER_ALIGNMENTS = ("center", "right")
BASE_PROFILE = LayoutProfile(
    name="base",
    label="base",
    hebrew_label="",
    description="the typography, spacing and breaks sections, unmodified",
)


def _profile_overrides(
    profiles: dict[str, Any], name: str, path: Path, chain: tuple[str, ...] = ()
) -> dict[str, dict[str, Any]]:
    """The overrides a profile makes, with anything it ``extends`` applied first."""
    if name not in profiles:
        available = ", ".join(profiles) or "none"
        raise ValueError(f'{path}: no layout profile "{name}" (defined: {available})')
    if name in chain:
        raise ValueError(f"{path}: layout profiles extend in a cycle: {' → '.join(chain)} → {name}")

    entry = profiles[name] or {}
    unknown = set(entry) - PROFILE_META_KEYS - PROFILE_SECTIONS.keys()
    if unknown:
        raise ValueError(f"{path}: layout_profiles.{name} has unknown keys {sorted(unknown)}")

    if entry.get("extends"):
        merged = _profile_overrides(profiles, entry["extends"], path, (*chain, name))
    else:
        merged = {section: {} for section in PROFILE_SECTIONS}

    for section, allowed in PROFILE_SECTIONS.items():
        values = entry.get(section) or {}
        refused = set(values) - allowed
        if refused:
            raise ValueError(
                f"{path}: layout_profiles.{name}.{section} cannot set {sorted(refused)}. "
                f"A layout profile changes sizes, spacing and page-break hints only — "
                f"never fonts or content."
            )
        merged[section] = {**merged[section], **values}
    return merged


def _layout_profiles(raw: dict[str, Any], path: Path) -> dict[str, LayoutProfile]:
    out: dict[str, LayoutProfile] = {}
    labels: set[str] = set()
    for name, entry in (raw.get("layout_profiles") or {}).items():
        entry = entry or {}
        missing = {"label", "hebrew_label"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: layout_profiles.{name} is missing {sorted(missing)}")
        if entry["label"] in labels:
            raise ValueError(f'{path}: two layout profiles share the label "{entry["label"]}"')
        labels.add(entry["label"])
        out[name] = LayoutProfile(
            name=name,
            label=entry["label"],
            hebrew_label=entry["hebrew_label"],
            description=" ".join(str(entry.get("description", "")).split()),
        )
    return out


def _positive(section: str, key: str, value: Any, path: Path, *, zero_ok: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path}: {section}.{key} must be a number, not {value!r}")
    if value < 0 or (value == 0 and not zero_ok):
        raise ValueError(f"{path}: {section}.{key} must be {'≥' if zero_ok else '>'} 0")
    return float(value)


def _spacing(values: dict[str, Any], path: Path) -> Spacing:
    unknown = set(values) - PROFILE_SECTIONS["spacing"]
    if unknown:
        raise ValueError(f"{path}: spacing has unknown keys {sorted(unknown)}")
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key == "divider_align":
            if value not in DIVIDER_ALIGNMENTS:
                raise ValueError(
                    f"{path}: spacing.divider_align must be one of {DIVIDER_ALIGNMENTS}"
                )
            out[key] = value
        else:
            out[key] = _positive("spacing", key, value, path, zero_ok=True)
    return Spacing(**out)


def _breaks(values: dict[str, Any], path: Path) -> Breaks:
    unknown = set(values) - PROFILE_SECTIONS["breaks"]
    if unknown:
        raise ValueError(f"{path}: breaks has unknown keys {sorted(unknown)}")
    for key, value in values.items():
        if not isinstance(value, bool):
            raise ValueError(f"{path}: breaks.{key} must be true or false")
    return Breaks(**values)


def load_config(path: Path | None = None, *, profile: str | None = None) -> Config:
    """Load the config, with a layout profile applied.

    ``profile`` names an entry under ``layout_profiles``; without it, ``layout.profile``
    decides, and a config that names no profile at all renders its ``typography``,
    ``spacing`` and ``breaks`` sections as written.
    """
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
    commentary_sources: dict[str, SourceInfo] = {}
    commentary_book_sources: dict[str, dict[str, SourceInfo]] = {}
    for name, entry in (sources.get("commentaries") or {}).items():
        label = f"sources.commentaries.{name}"
        if "versions" in entry:
            by_book = _versions_by_book(entry, label, path)
            commentary_book_sources[name] = by_book
            commentary_sources[name] = next(iter(by_book.values()))
        else:
            commentary_sources[name] = _source(entry, label, path)
    for name in commentaries:
        if name not in commentary_sources:
            raise ValueError(f"{path}: no sources.commentaries entry for {name}")

    typography_raw = raw.get("typography") or {}
    layout_raw = raw.get("layout") or {}
    navigation_raw = raw.get("navigation") or {}

    if layout_raw.get("file_per", "chapter") != "chapter":
        # SPEC.md §11: one file per book is withdrawn, not configurable.
        raise ValueError(f'{path}: layout.file_per must be "chapter"')

    profiles = _layout_profiles(raw, path)
    profile_name = profile or layout_raw.get("profile")
    if profile_name is None:
        layout_profile = BASE_PROFILE
        overrides: dict[str, dict[str, Any]] = {section: {} for section in PROFILE_SECTIONS}
    else:
        overrides = _profile_overrides(raw.get("layout_profiles") or {}, profile_name, path)
        layout_profile = profiles[profile_name]

    typography_values = {
        "biblical_scale": typography_raw.get("biblical_scale", 1.25),
        "rashi_scale": typography_raw.get("rashi_scale", 0.85),
        "verse_number_scale": typography_raw.get("verse_number_scale", 0.75),
        "divider_scale": typography_raw.get("divider_scale", 0.85),
        "biblical_line_height": typography_raw.get("biblical_line_height", 1.9),
        "rashi_line_height": typography_raw.get("rashi_line_height", 1.65),
        **overrides["typography"],
    }

    return Config(
        title=raw["title"],
        creator=raw.get("creator", ""),
        publisher=raw.get("publisher", ""),
        delivery=(raw.get("target") or {}).get("delivery", "calibre-kfx"),
        device=(raw.get("target") or {}).get("device", ""),
        commentaries=commentaries,
        tanakh_source=_source(sources["tanakh"], "sources.tanakh", path),
        commentary_sources=commentary_sources,
        commentary_book_sources=commentary_book_sources,
        biblical_font=_font(raw, "biblical", path),
        rashi_font=_font(raw, "rashi", path),
        typography=Typography(
            **{
                key: _positive("typography", key, value, path, zero_ok=False)
                for key, value in typography_values.items()
            },
            rashi_script=bool(typography_raw.get("rashi_script", True)),
            dibur_hamatchil_in_biblical_font=bool(
                typography_raw.get("dibur_hamatchil_in_biblical_font", True)
            ),
        ),
        spacing=_spacing({**(raw.get("spacing") or {}), **overrides["spacing"]}, path),
        breaks=_breaks({**(raw.get("breaks") or {}), **overrides["breaks"]}, path),
        layout_profile=layout_profile,
        layout_profiles=profiles,
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

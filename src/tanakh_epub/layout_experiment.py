"""The layout experiment — docs/LAYOUT_EXPERIMENT.md.

Builds one EPUB per layout profile from a single load of the content, so the variants
cannot differ in anything but the stylesheet — and checks that they do not before it
reports success. It does not rank the variants. Which one reads best on a 7″ Paperwhite
is a device question (decision D10), not something this code can measure.

What legitimately differs between the variants, and why:

* ``styles/main.css`` — the point of the exercise.
* ``dc:title`` gets the profile's Hebrew label (``פריסה ג׳``), or the variants are
  indistinguishable in the Kindle library.
* ``dc:identifier`` and the ``tanakh:config-hash``/``tanakh:layout-profile`` metadata are
  derived from the profile, or the device would treat them as one book and each
  sideload would replace the last.
"""

from __future__ import annotations

import dataclasses
import textwrap
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .books import BookTable
from .config import Config, LayoutProfile, load_config
from .epub.builder import OEBPS, BuildResult, EpubBuilder
from .models import Chapter
from .processing.study_units import stats

PER_VARIANT_FILES = frozenset(
    {
        f"{OEBPS}/styles/main.css",
        f"{OEBPS}/content.opf",
        f"{OEBPS}/toc.ncx",
        f"{OEBPS}/build_manifest.json",
    }
)
"""The only files allowed to differ between variants: the stylesheet, and the three files
that carry the title, identifier and layout profile. Every chapter, the nav document, the
sources page and both fonts must be byte-for-byte the same."""


@dataclass(frozen=True)
class Variant:
    profile: LayoutProfile
    config: Config
    result: BuildResult
    css_bytes: int

    @property
    def xhtml_bytes(self) -> int:
        return sum(chapter.size_bytes for chapter in self.result.chapters)


def output_name(profile: LayoutProfile) -> str:
    """``layout_C_dense.epub`` — from the stable label, so the name never drifts."""
    return f"layout_{profile.label.replace('-', '_')}.epub"


def profile_config(config_path: Path | None, profile: LayoutProfile) -> Config:
    config = load_config(config_path, profile=profile.name)
    return dataclasses.replace(config, title=f"{config.title} — {profile.hebrew_label}")


def build_variants(
    *,
    config_path: Path | None,
    profile_names: list[str],
    books: BookTable,
    chapters: list[Chapter],
    text_versions: dict[str, str],
    commentary_versions: dict[str, dict[str, str]],
    output_dir: Path,
    build_date: datetime,
) -> list[Variant]:
    """One EPUB per profile, from the same ``chapters`` and the same build date."""
    available = load_config(config_path).layout_profiles
    unknown = [name for name in profile_names if name not in available]
    if unknown:
        raise ValueError(
            f"No layout profile {', '.join(unknown)} (defined: {', '.join(available) or 'none'})"
        )

    variants: list[Variant] = []
    for name in profile_names:
        profile = available[name]
        config = profile_config(config_path, profile)
        builder = EpubBuilder(config, books)
        result = builder.build(
            chapters,
            output=output_dir / output_name(profile),
            text_versions=text_versions,
            commentary_versions=commentary_versions,
            build_date=build_date,
        )
        with zipfile.ZipFile(result.path) as archive:
            css_bytes = archive.getinfo(f"{OEBPS}/styles/main.css").file_size
        variants.append(Variant(profile, config, result, css_bytes))
    return variants


def content_differences(variants: list[Variant]) -> list[str]:
    """Files other than the stylesheet, OPF and NCX that differ between variants — which
    must be none. Returned rather than raised so the caller can report every one."""
    if len(variants) < 2:
        return []

    def contents(path: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    reference = contents(variants[0].result.path)
    problems: list[str] = []
    for variant in variants[1:]:
        other = contents(variant.result.path)
        if reference.keys() != other.keys():
            problems.append(
                f"{variant.profile.label}: different file list from {variants[0].profile.label}"
            )
            continue
        for name in sorted(reference):
            if name not in PER_VARIANT_FILES and reference[name] != other[name]:
                problems.append(f"{variant.profile.label}: {name} differs")
    return problems


def _kb(size: int) -> str:
    return f"{size / 1024:.1f} KB"


def _hints(config: Config) -> str:
    b = config.breaks
    hints = ["verse + divider + first entry", "chapter heading → text"]
    if b.keep_each_entry_together:
        hints.append("each commentary entry")
    if b.keep_divider_with_neighbours:
        hints.append("divider ↔ verse and first entry")
    if b.keep_book_heading_with_next:
        hints.append("book heading → chapter heading")
    return "; ".join(hints)


def _change(value: float, reference: float) -> str:
    if reference == value:
        return ""
    return f"  ({(value - reference) / reference:+.0%} vs A)"


def format_report(variants: list[Variant], chapters: list[Chapter]) -> str:
    counts = stats(chapters)
    books = sorted({chapter.book for chapter in chapters})
    lines = [
        "Layout experiment",
        f"  content  {len(chapters)} chapter(s) of {', '.join(books)}: {counts.verses} verses, "
        f"{counts.commentary_entries} commentary entries "
        f"({counts.verses_without_commentary} verses without)",
        "  Sizes are in em of the reader's chosen font size; spacing is in em of the",
        "  element it sits on, as CSS reads it. Line pitch = size × line height.",
        "",
    ]
    reference = variants[0].config
    ref_bible = reference.typography.biblical_scale * reference.typography.biblical_line_height
    ref_rashi = reference.typography.rashi_scale * reference.typography.rashi_line_height

    for v in variants:
        t, sp = v.config.typography, v.config.spacing
        bible_pitch = t.biblical_scale * t.biblical_line_height
        rashi_pitch = t.rashi_scale * t.rashi_line_height
        path = v.result.path
        lines += [
            f"{v.profile.label}    {path.name}",
            *textwrap.wrap(
                v.profile.description, width=88, initial_indent="  ", subsequent_indent="  "
            ),
            f"  Biblical text     {t.biblical_scale:g}em, line-height {t.biblical_line_height:g}"
            f"  → line pitch {bible_pitch:.2f}em{_change(bible_pitch, ref_bible)}",
            f"  Rashi             {t.rashi_scale:g}em, line-height {t.rashi_line_height:g}"
            f"  → line pitch {rashi_pitch:.2f}em{_change(rashi_pitch, ref_rashi)}",
            f"  Verse number      {t.verse_number_scale:g}em, inline",
            f"  Divider           {t.divider_scale:g}em, {sp.divider_align}, one rule above; "
            f"margin {sp.divider_margin_top:g}/{sp.divider_margin_bottom:g}em, "
            f"padding {sp.divider_padding_top:g}/{sp.divider_padding_bottom:g}em",
            f"  Study-unit gap    {sp.study_unit:g}em",
            f"  Verse gap         {sp.verse:g}em",
            f"  Entry gap         {sp.entry:g}em "
            f"(paragraphs inside an entry {sp.rashi_paragraph:g}em)",
            f"  Page-break hints  {_hints(v.config)}",
            f"  Sizes             EPUB {_kb(v.result.total_bytes)} · "
            f"XHTML {_kb(v.xhtml_bytes)} in {len(v.result.chapters)} file(s) · "
            f"CSS {_kb(v.css_bytes)}",
            "",
        ]
    return "\n".join(lines)

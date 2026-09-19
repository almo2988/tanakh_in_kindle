"""The stylesheet — SPEC.md §14, §15, §16, §24, §26, §27.

Generated rather than checked in, because every size, line height, space and optional
page-break hint comes from the config — ``typography``, ``spacing`` and ``breaks``, with
the active layout profile applied on top — and the two ``@font-face`` rules come from
``fonts.*``. A hand-written CSS file would drift from the config the first time a scale
changed, and the layout experiment needs several stylesheets from one renderer.

Constraints, all from the device:

* **Only the properties in §26**, minus ``direction``: EPUB 3 forbids it in a style
  sheet, so direction comes from ``dir="rtl"`` in the markup instead. No grid, no flexbox,
  no ``position``, no ``@page``. The book has to stay readable when a reader ignores
  almost all of this, which is close to what Kindle does.
* **No ``px``, ``vh`` or ``vw``.** Everything is ``em``/``rem``/``%`` so that changing the
  Kindle font size scales verse, verse number, divider and commentary together and keeps
  the ratios (§14).
* ``break-*`` are hints, always emitted with their CSS 2 ``page-break-*`` twin. Whether
  the Paperwhite honours them is what the layout experiment finds out; nothing may depend
  on it either way (§13, §27).
* **One embedded font family per ``font-family`` stack**, followed by a generic.
* **The Rashi font must never be the heaviest first family.** Kindle's converter turns
  that one into the book's default font, which the reader's font menu replaces — the
  real reason the commentary never showed in Rashi script on the device. See
  `CommentaryParts`.
"""

from __future__ import annotations

import re

from ..config import Config
from ..models import Chapter

FONT_MEDIA_TYPES = {
    ".ttf": "application/vnd.ms-opentype",
    ".otf": "application/vnd.ms-opentype",
}
"""EPUB 3.3 calls `font/ttf` and `font/otf` the current types and this one obsolete, but
`application/vnd.ms-opentype` is what Kindle's converter has always recognised — the
modern types date from 2017, long after KFX's resource parser. EPUBCheck accepts both with
0 errors and 0 warnings, so there is nothing to trade away by using the one the target
device understands. SPEC §0: when anything conflicts, choose what works on the Kindle."""

EPUB_FONT_NAMES = {
    "biblical": "biblical_hebrew",
    "rashi": "rashi",
}
"""File names inside the EPUB (SPEC.md §11). The repo keeps the upstream file names so
the version being shipped is never in doubt; the EPUB uses stable role-based names."""


def epub_font_href(config: Config, role: str) -> str:
    font = config.biblical_font if role == "biblical" else config.rashi_font
    return f"fonts/{EPUB_FONT_NAMES[role]}{font.suffix}"


def font_media_type(suffix: str) -> str:
    try:
        return FONT_MEDIA_TYPES[suffix]
    except KeyError:
        raise ValueError(
            f'Font extension "{suffix}" is not embeddable here. '
            f"WOFF does not survive Kindle conversion reliably (SPEC.md §15); use TTF or OTF."
        ) from None


COMMENTARY_PART_FAMILY = "Rashi Part"
"""Placeholder family names that head the commentary stacks. No font by these names exists;
each stack falls straight through to the Rashi font. See `CommentaryParts`."""

_TAG = re.compile(r"<[^>]+>")


def _text_volume(markup: str) -> int:
    return len(_TAG.sub("", markup))


class CommentaryParts:
    """Spreads the commentary over several placeholder font names — the fix for the Rashi
    font the Paperwhite never showed.

    Kindle's converter (Kindle Previewer / KFX) takes the first family of whichever
    `font-family` stack covers the most text, makes it the book's **default** font, and
    rewrites every style that names it to just ``default``. On the device ``default`` is
    exactly what the reader's font menu replaces. Rashi outweighs the verses roughly three
    to one, so the Rashi font always became the default, and the commentary came out in
    the Kindle's own square Hebrew font. Seen by decoding the converted KPF, in every build
    since Phase 1 began.

    So each commentary paragraph's stack starts with one of several placeholder names,
    ``"Rashi Part 0", "Noto Rashi Hebrew", serif``. Paragraphs are dealt to the lightest
    part in order, and there are enough parts that each carries at most half the verse
    text's volume. The biblical font is then the heaviest first family, becomes the
    default, and the Rashi font stays named explicitly in every commentary style.

    Only useful when the commentary has a font of its own; with `rashi_script: false` the
    commentary is in the biblical font and there is nothing to protect.
    """

    def __init__(self, count: int, biblical: int = 0) -> None:
        self.count = count
        self.biblical = biblical
        self.loads = [0] * count

    @classmethod
    def plan(cls, chapters: list[Chapter], config: Config) -> CommentaryParts:
        if not config.typography.rashi_script:
            return cls(0)
        biblical = commentary = 0
        for chapter in chapters:
            for unit in chapter.study_units:
                biblical += _text_volume(unit.verse.hebrew_text)
                commentary += sum(_text_volume(e.text) for e in unit.commentaries)
        if commentary == 0:
            return cls(0)
        # Half the verse volume per part leaves room for greedy dealing to be uneven by
        # up to one long paragraph; one extra part on top for the same reason.
        share = max(1, biblical // 2)
        return cls(-(-commentary // share) + 1, biblical)

    @property
    def protects_rashi_font(self) -> bool:
        """False when one part still outweighs the verses — possible only in a build so
        small that a single Rashi paragraph is longer than all its verses together (the
        ten-verse POC: Rashi on 1:1 alone). Paragraphs are not split, so no plan can help."""
        return not self.count or max(self.loads) < self.biblical

    def assign(self, paragraph: str) -> int | None:
        if not self.count:
            return None
        part = self.loads.index(min(self.loads))
        self.loads[part] += _text_volume(paragraph)
        return part


def _n(value: float) -> str:
    """Trim trailing zeros so the stylesheet reads like something a person wrote."""
    return f"{value:g}"


def _em(value: float) -> str:
    """A length in em; a bare ``0`` when it is zero."""
    return f"{value:g}em" if value else "0"


def _break_hint(prop: str, value: str) -> str:
    """A page-break hint in both spellings. ``break-*`` is CSS Fragmentation 3,
    ``page-break-*`` its CSS 2.1 ancestor, which older reading systems — and possibly the
    Kindle converter — know instead."""
    legacy = {"avoid": "avoid", "page": "always"}[value]
    return f"  break-{prop}: {value};\n  page-break-{prop}: {legacy};\n"


def _optional_breaks(config: Config) -> str:
    b = config.breaks
    rules: list[str] = []
    if b.keep_book_heading_with_next:
        rules.append(f".book-heading {{\n{_break_hint('after', 'avoid')}}}")
    if b.keep_divider_with_neighbours:
        # Inside .keep-together this is redundant — until a first entry longer than a
        # page forces the reader to split the block anyway. Then it still keeps the label
        # off the foot of one page and away from the verse it belongs to.
        rules.append(
            f".commentary-divider {{\n{_break_hint('before', 'avoid')}"
            f"{_break_hint('after', 'avoid')}}}"
        )
    if b.keep_each_entry_together:
        # One entry at a time, never the run of them: the study unit as a whole must stay
        # free to split, or a long Rashi leaves a screen of blank space in front of it.
        rules.append(f".commentary-entry {{\n{_break_hint('inside', 'avoid')}}}")
    if not rules:
        return ""
    return "\n/* Optional hints — `breaks` in the config. */\n\n" + "\n\n".join(rules) + "\n"


def render_css(config: Config, commentary_parts: int = 0) -> str:
    t = config.typography
    sp = config.spacing
    biblical = config.biblical_font
    rashi = config.rashi_font

    # One embedded family per stack, then a generic — never two embedded families.
    #
    # SPEC §16 writes this as `"Rashi", "BiblicalHebrew", serif`. Dropping the middle
    # entry did not by itself fix the device — see CommentaryParts for what did — but it
    # stays: nothing is lost by dropping the middle entry. It existed so a character missing from
    # the Rashi font would fall back to the biblical one, and tests/test_fonts.py already
    # proves no such character exists in the commentary: it checks the embedded font's cmap
    # against the actual text on every run.
    commentary_stack = (
        f'"{rashi.family}", serif' if t.rashi_script else f'"{biblical.family}", serif'
    )
    dibur_stack = (
        f'"{biblical.family}", serif' if t.dibur_hamatchil_in_biblical_font else commentary_stack
    )

    part_rules = "".join(
        f".commentary-text.part-{i} {{\n"
        f'  font-family: "{COMMENTARY_PART_FAMILY} {i}", "{rashi.family}", serif;\n'
        "}\n\n"
        for i in range(commentary_parts)
    )

    book_break = _break_hint("before", "page") if config.layout.page_break_before_book else ""

    rashi_note = (
        f"   {rashi.name} — commentary, in Rashi script."
        if t.rashi_script
        else f"   {rashi.name} — embedded but unused: typography.rashi_script is false, "
        f"so the\n   commentary falls back to the biblical font."
    )

    return f"""@charset "utf-8";

/* Tanakh + Rashi — generated from {config.path.name} by rendering/css.py.
   Layout profile: {config.layout_profile.label}.
   Do not edit by hand: change the config and rebuild.

   Fonts (embedded; applied on Kindle only when the reader selects "Publisher Font"):
   {biblical.name} — biblical text.
{rashi_note}
*/

@font-face {{
  font-family: "{biblical.family}";
  font-weight: normal;
  font-style: normal;
  src: url("../{epub_font_href(config, "biblical")}") format("truetype");
}}

@font-face {{
  font-family: "{rashi.family}";
  font-weight: normal;
  font-style: normal;
  src: url("../{epub_font_href(config, "rashi")}") format("truetype");
}}

/* ---- Page ---------------------------------------------------------- */
/* Direction is set by dir="rtl" on <html> and <body>, not here: EPUB 3
   forbids `direction` and `unicode-bidi` in a style sheet (EPUBCheck
   CSS-001), which overrides the literal CSS in SPEC §17/§26. The rendered
   result is the same, and the attribute is the more robust of the two —
   a reader that drops the stylesheet still lays the page out right-to-left. */

body {{
  text-align: right;
  font-family: "{biblical.family}", serif;
  line-height: 1.6;
  margin: 0;
  padding: 0;
}}

/* ---- Headings ------------------------------------------------------ */
/* Headings must not eat the screen: no title pages, no vertical padding
   the reader has to page past (SPEC §18). */

h1, h2 {{
  font-family: "{biblical.family}", serif;
  font-weight: normal;
  text-align: center;
  line-height: 1.4;
}}

.book-heading {{
  font-size: 1.6em;
  margin: 0.4em 0 0.3em 0;
}}

.chapter-heading {{
  font-size: 1.15em;
  margin: 0.6em 0 0.5em 0;
{_break_hint("after", "avoid")}}}

.book-start {{
{book_break}}}

/* ---- Verse --------------------------------------------------------- */

.study-unit {{
  margin: 0 0 {_em(sp.study_unit)} 0;
}}

/* The verse number is an inline span at the start of the verse's own line —
   never a block of its own. */
.verse {{
  margin: 0 0 {_em(sp.verse)} 0;
  text-indent: 0;
}}

.verse-number {{
  font-family: "{biblical.family}", serif;
  font-size: {_n(t.verse_number_scale)}em;
  font-weight: bold;
  margin-left: 0.35em;
}}

.biblical-text {{
  font-family: "{biblical.family}", serif;
  font-size: {_n(t.biblical_scale)}em;
  line-height: {_n(t.biblical_line_height)};   /* room for ניקוד above and טעמים below */
}}

.letter-large {{
  font-size: 1.35em;
}}

.letter-small {{
  font-size: 0.8em;
}}

.parasha-marker {{
  font-size: 0.85em;
}}

/* ---- Commentary ---------------------------------------------------- */
/* Separation is one thin rule above a label, nothing else: no second rule,
   no colour, no background, no icon — it has to read the same on E-Ink, in
   dark mode and inverted (SPEC §24). */

.commentary-divider {{
  font-family: "{biblical.family}", serif;
  font-size: {_n(t.divider_scale)}em;
  text-align: {sp.divider_align};
  margin: {_em(sp.divider_margin_top)} 0 {_em(sp.divider_margin_bottom)} 0;
  padding: {_em(sp.divider_padding_top)} 0 {_em(sp.divider_padding_bottom)} 0;
  border-top: thin solid;
}}

.commentary {{
  margin: 0;
}}

.commentary-entry {{
  margin: 0 0 {_em(sp.entry)} 0;
}}

.commentary-text {{
  font-family: {commentary_stack};
  font-size: {_n(t.rashi_scale)}em;
  line-height: {_n(t.rashi_line_height)};
  margin: 0 0 {_em(sp.rashi_paragraph)} 0;
  text-indent: 0;
}}

/* The commentary's stack opens with a placeholder name, dealt over several
   parts, so that Kindle's converter never makes the Rashi font the book's
   default font — the one slot the reader's font menu replaces. See
   CommentaryParts in rendering/css.py. */
{part_rules}
.dibur-hamatchil {{
  font-family: {dibur_stack};
  font-weight: bold;
  margin-left: 0.3em;
}}

/* ---- Page-break hints ---------------------------------------------- */
/* Verse + divider + first entry ask to stay together. The study unit as a
   whole never does: a long Rashi would leave blank pages in front of it
   in any reader that honours the hint (SPEC §13). */

.keep-together {{
{_break_hint("inside", "avoid")}}}
{_optional_breaks(config)}
/* ---- מקורות --------------------------------------------------------- */

.sources-lead {{
  margin: 0.6em 0 1em 0;
}}

.source-entry {{
  margin: 0 0 0.7em 0;
}}

.source-label {{
  font-weight: bold;
  margin-left: 0.3em;
}}

.source-detail {{
  font-size: 0.9em;
  margin: 0 0 0.15em 0;
}}
"""

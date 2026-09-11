"""The stylesheet — SPEC.md §14, §15, §16, §24, §26, §27.

Generated rather than checked in, because every size comes from ``typography.*`` in the
config and the two ``@font-face`` rules come from ``fonts.*``. A hand-written CSS file
would drift from the config the first time a scale changed.

Constraints, all from the device:

* **Only the properties in §26**, minus ``direction``: EPUB 3 forbids it in a style
  sheet, so direction comes from ``dir="rtl"`` in the markup instead. No grid, no flexbox,
  no ``position``, no ``@page``. The book has to stay readable when a reader ignores
  almost all of this, which is close to what Kindle does.
* **No ``px``, ``vh`` or ``vw``.** Everything is ``em``/``rem``/``%`` so that changing the
  Kindle font size scales verse, verse number, divider and commentary together and keeps
  the ratios (§14).
* ``break-inside``/``break-before`` are hints. Kindle ignores them; nothing may depend on
  them (§13, §27).
"""

from __future__ import annotations

from ..config import Config

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


def _n(value: float) -> str:
    """Trim trailing zeros so the stylesheet reads like something a person wrote."""
    return f"{value:g}"


def render_css(config: Config) -> str:
    t = config.typography
    biblical = config.biblical_font
    rashi = config.rashi_font

    # SPEC §15.2: with rashi_script off, the commentary falls back to the biblical font.
    # The Rashi @font-face is still declared and the file still embedded, so flipping the
    # switch is a config change and a rebuild, not a font hunt.
    commentary_stack = (
        f'"{rashi.family}", "{biblical.family}", serif'
        if t.rashi_script
        else f'"{biblical.family}", serif'
    )
    dibur_stack = (
        f'"{biblical.family}", serif' if t.dibur_hamatchil_in_biblical_font else commentary_stack
    )

    book_break = (
        "  break-before: page;\n  page-break-before: always;\n"
        if config.layout.page_break_before_book
        else ""
    )

    rashi_note = (
        f"   {rashi.name} — commentary, in Rashi script."
        if t.rashi_script
        else f"   {rashi.name} — embedded but unused: typography.rashi_script is false, "
        f"so the\n   commentary falls back to the biblical font."
    )

    return f"""@charset "utf-8";

/* Tanakh + Rashi — generated from {config.path.name} by rendering/css.py.
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
  break-after: avoid;
  page-break-after: avoid;
}}

.book-start {{
{book_break}}}

/* ---- Verse --------------------------------------------------------- */

.study-unit {{
  margin: 0 0 1.1em 0;
}}

.verse {{
  margin: 0 0 0.35em 0;
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
  line-height: 1.9;   /* room for ניקוד above and טעמים below without collisions */
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
/* Separation is a thin rule and a label, nothing else: no colour, no
   background, no icon — it has to read the same on E-Ink, in dark mode and
   inverted (SPEC §24). */

.commentary-divider {{
  font-family: "{biblical.family}", serif;
  font-size: {_n(t.divider_scale)}em;
  text-align: center;
  margin: 0.5em 0 0.4em 0;
  padding: 0.15em 0;
  border-top: thin solid;
  border-bottom: thin solid;
}}

.commentary {{
  margin: 0;
}}

.commentary-entry {{
  margin: 0 0 0.4em 0;
}}

.commentary-text {{
  font-family: {commentary_stack};
  font-size: {_n(t.rashi_scale)}em;
  line-height: 1.65;
  margin: 0 0 0.3em 0;
  text-indent: 0;
}}

.dibur-hamatchil {{
  font-family: {dibur_stack};
  font-weight: bold;
  margin-left: 0.3em;
}}

/* ---- Page-break hints ---------------------------------------------- */
/* Only this small block asks to stay together: verse + divider + first
   entry. Wrapping a whole study unit would leave blank pages in readers
   that honour the hint, and Kindle ignores it either way (SPEC §13). */

.keep-together {{
  break-inside: avoid;
  page-break-inside: avoid;
}}

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

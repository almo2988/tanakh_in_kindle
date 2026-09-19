# Decisions

What was decided, and why. Each decision is also recorded where it takes effect, usually in
`config/default.yaml`; code comments refer to them by number (D1–D10).

| ID | Question | Decision |
|---|---|---|
| D1 | How the book reaches the Kindle | **Send to Kindle.** Tested on a Paperwhite (12th gen); fonts, RTL and navigation survive. Calibre KFX over USB is documented as a fallback but untested. |
| D2 | Font for the biblical text | **Taamey Frank CLM Medium 0.110** (GPL-2.0 with the Culmus font-embedding exception). Its OpenType tables stack ניקוד and טעמים correctly on the device. |
| D3 | Font for Rashi | **Noto Rashi Hebrew 1.007** (SIL OFL 1.1): real Rashi script. `typography.rashi_script: false` falls back to the biblical font. |
| D4 | Rashi size | **0.86em**, set by the C-dense layout. Legible on the Paperwhite. |
| D5 | Tanakh text | ***Miqra according to the Masorah*** (CC BY-SA), all 39 books. Richer than the alternatives: large and small letters, real paragraph breaks, qamats qatan, both כתיב and קרי. |
| D6 | Rashi text | **Vocalized throughout, one version per book.** No single Hebrew Rashi on Sefaria covers the Tanakh. Rosenbaum & Silbermann for the Torah, Metsudah for Joshua, Kings and the five Megillot, and the Sefaria vocalized edition for the other 26 books. That last edition's license is listed by Sefaria as "unknown", which is why the built book is for personal reading. Survey in `docs/VERSION_SELECTION.md`. |
| D7 | Book titles | All 39 titles in `config/books.yaml` match Sefaria's index exactly. |
| D8 | EPUB writer | **Hand-rolled** (zipfile + Jinja2) rather than `ebooklib`. The OPF spine direction, the NCX kept beside the nav document and the exact font media types each need precise control for the Kindle converter. |
| D9 | Where the commentary sits | **Inline.** Both tap-to-open mechanisms (`<details>` and the EPUB footnote popup) were built and tested: on a Kindle any tap turns the page, so neither can work. |
| D10 | Page layout | **C-dense**, chosen on the device over two roomier variants. `python -m tanakh_epub experiment-layout` rebuilds the comparison (`docs/LAYOUT_EXPERIMENT.md`). |

## Kindle findings

Things learned on the device that the code now depends on. Each has a test.

- **Kindle's converter promotes the most-used font to the book's default font,** and the
  reader's font menu replaces that default. Rashi outweighs the verses about 3:1, so the
  Rashi font took the slot and the commentary lost its Rashi script whenever the reader
  picked a font. The commentary is now dealt over placeholder family names
  (`CommentaryParts` in `rendering/css.py`) so the biblical font is the default and the
  Rashi font is always named explicitly. Found by decoding the converted KPF.
- **A `font-family` stack names one embedded family, then a generic.** The Paperwhite
  ignored a stack naming two embedded families.
- **The CSS family name is the font's own internal name** (name ID 1), not a label.
- **Direction comes from `dir="rtl"`, not CSS.** EPUB 3 forbids `direction` in a style
  sheet (EPUBCheck CSS-001). `dir="rtl"` on `<html>` and `<body>` plus
  `page-progression-direction="rtl"` in the OPF gives right-to-left page turns.
- **NFC reorders Hebrew combining marks** from Sefaria's typing order into canonical order,
  and splits the few precomposed presentation forms. Nothing is lost, and marks stack
  correctly on the device. `validate` checks every string.
- **Page-break hints are only hints.** The study unit as a whole is never asked to stay
  together; readers that honour it would leave blank pages before long Rashi.

## Data findings

- Sefaria-Export's text moved from GitHub to a public Google Cloud Storage bucket.
  `fetch` reads it first and falls back to the API; both return identical text.
- Sefaria's commentary index counts are not authoritative. They count every version
  together and are stale for some books, so `validate` warns on them rather than failing.
  The Tanakh's own chapter and verse counts must match exactly, and do (929 and 23,206).
- The four suspended letters (e.g. מְנַשֶּׁה, Judges 18:30) come as a bare `<sup>`. The
  spec's "drop `<sup>`" rule was written for footnote markers; these are kept and set
  small. Details in `docs/MARKUP_RULES.md`.

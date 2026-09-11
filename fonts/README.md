# Fonts

Only fonts whose license has been read and recorded live here (CLAUDE.md, non-negotiable 9).
Both fonts below report `fsType = 0` (installable embedding permitted) in their own `OS/2`
table, and both are **static** TrueType — a variable font is not known to survive Kindle's
KFX conversion.

| File | Family | Version | Role | License |
|---|---|---|---|---|
| `TaameyFrankCLM-Medium.ttf` | Taamey Frank CLM | 0.110 | biblical text (D2) | GPL-2.0 + font-embedding exception (`LICENSE-TaameyFrankCLM.txt`) |
| `NotoRashiHebrew-Regular.ttf` | Noto Rashi Hebrew | 1.007 | commentary, in Rashi script (D3) | SIL OFL 1.1 (`LICENSE-NotoRashiHebrew.txt`) |

`Taamey Frank CLM` carries the Hancock/Hudson Biblical Hebrew OpenType layout logic, which
is what positions ניקוד and טעמים without collisions.

`Noto Rashi Hebrew` is genuine Rashi script — a semi-cursive skeleton based on 15th-century
Sephardic writing — and replaced the square placeholder that the first Paperwhite test
rejected. It covers every character present in the Rashi fixture, which `tests/test_fonts.py`
asserts on every run: a font that is missing a glyph does not fail the build, it renders a
blank box, and only on the device.

Rashi commentary is unvocalized, so the commentary font is not required to stack ניקוד;
the biblical font is, and is tested for it.

`typography.rashi_script: false` remains the escape hatch if Rashi script proves hard to
read on the 7″ screen — the commentary then falls back to the biblical font. The Rashi
`@font-face` is still declared and the file still embedded, so it is a config change and a
rebuild, not a font hunt.

Inside the EPUB these are renamed to `OEBPS/fonts/biblical_hebrew.ttf` and
`OEBPS/fonts/rashi.ttf` (SPEC.md §11); the repo keeps the upstream file names so the
version being shipped is never in doubt.

Sources, both fetched 2026-09-11:

- Taamey Frank CLM — <https://www.sefaria.org/static/fonts/Taamey-Frank/TaameyFrankCLM-Medium.ttf>,
  upstream the Culmus Project <https://culmus.sourceforge.io/>. `GNU-GPL-2.0.txt` is the
  full text of the licence its embedding exception modifies.
- Noto Rashi Hebrew — the static TrueType build behind
  <https://fonts.googleapis.com/css2?family=Noto+Rashi+Hebrew:wght@400>, upstream
  <https://github.com/notofonts/hebrew>.

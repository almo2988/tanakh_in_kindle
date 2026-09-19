# Layout experiment — three candidates for the Paperwhite

**Decision D10: C-dense**, chosen on the Paperwhite (2026-09-19) and used by every build.
This document records the three candidates, why there were several, and how they were
judged — the method to reuse if the layout is ever revisited.

## Why an experiment, not a choice

The book is a reflowable Hebrew Tanakh with Rashi **inline**: every verse is followed
immediately by its commentary, with nothing collapsible and nothing tap-to-open (D9 ruled
those out — a tap turns the page). So the only levers left are typography, spacing and
page-break hints, and the goal is:

> the most comfortable reading and the most useful text per screen on a 7″ Paperwhite,
> while each verse still reads as one unit with its Rashi.

Those pull against each other, and what feels right on a 300 ppi E-Ink screen cannot be
judged from a desktop browser or computed. So the build produces three candidates from
**identical content** and the device test compares them.

## The three variants

| | A-current | B-balanced | C-dense |
|---|---|---|---|
| Role | control | modest step | dense |
| Biblical text | 1.25em / 1.9 | 1.15em / 1.75 | 1.1em / 1.6 |
| Biblical line pitch | 2.38em | 2.01em (−15%) | 1.76em (−26%) |
| Rashi | 0.9em / 1.65 | 0.9em / 1.5 | 0.86em / 1.42 |
| Rashi line pitch | 1.49em | 1.35em (−9%) | 1.22em (−18%) |
| Verse number (inline) | 0.75em | 0.72em | 0.7em |
| Divider label | 0.85em, centred | 0.8em, at line start | 0.78em, at line start |
| Gap after a study unit | 1.1em | 0.75em | 0.55em |
| Gap between Rashi entries | 0.4em | 0.25em | 0.15em |

"Size / number" is font size / line height. Line pitch is size × line height, in em of the
reader's chosen font size. Every value lives in `config/default.yaml` under
`layout_profiles`; the build prints the full set, with sizes, every time.

In Chrome at a Paperwhite-like width, בראשית א׳ comes out 16% shorter in B and 27% shorter
in C than in A. That is only a rough guide to text per screen — the Kindle's own
renderer will not match it exactly.

**The progression is deliberate.** A→B→C change only typography and spacing, with the same
page-break hints, so the comparison isolates one question: *how dense is still
comfortable*.

**A fourth variant, D-dense-break-aware, was tried and dropped.** It was C plus extra
page-break hints: each Rashi entry asked not to split, the divider asked to stay with its
neighbours, and the book title asked to stay with the chapter heading. It was rejected
(2026-09-19). The `breaks` switches for those hints are still in the config,
all off, so the idea can be retried without new code.

**A is the control, with one exception.** It reproduces the old stylesheet value for value,
except that the divider now has one rule above the label instead of one above and one
below. That rule is a requirement for every variant, not something being tested.

**Line heights were measured, not guessed.** Shaped with the font's own OpenType
positioning (HarfBuzz), the tallest mark in Taamey Frank CLM sits 0.93em above the baseline
and the lowest 0.31em below: 1.24em of ink. The lowest biblical line height here, 1.6,
still leaves 0.36em between the worst-case marks of two lines. A test keeps every profile at
1.54 or above. Noto Rashi Hebrew needs 1.13em, and the lowest Rashi line height is 1.42.

**The Rashi size barely moves.** D4 (is Rashi script at 0.9em legible?) has not been checked
on the device. B leaves it at 0.9, and only C goes down to 0.86.

## Page breaks: what is grouped, and what is left free

Kindle decides where pages end. Nothing here fixes page lengths, and the book reads
correctly whether or not a reader honours any hint.

```text
study-unit                                   ← free to split: never asked to stay together
  keep-together                              ← asks not to split (every variant)
    verse (number inline)
    divider: one rule, then רש״י
    first commentary entry
  commentary
    entry 2                                  ← free to split
    entry 3                                  ← free to split
    …
```

- **Verse + divider + first entry** ask to stay together in every variant, so a verse
  never ends one page with its Rashi starting on the next.
- **Later entries** make no request, so a long Rashi flows freely across pages. Asking
  each entry to stay whole was D, which was rejected.
- **The whole study unit never asks to stay together.** Rashi on א׳:א׳ alone runs for
  several screens; asking to keep it together would leave a near-empty page in front of it
  on any reader that honours the request.
- Chapter headings stay with their text in every variant.
- Every hint is written in both spellings, `break-*` and the older `page-break-*`.
  `orphans` and `widows` are not used because SPEC §26 does not allow them.

**Do the hints do anything on a Kindle?** Earlier notes assumed Kindle ignores them. The
converter does keep them: with D's extra hints, the converted book carried about 24 KB
more internal data than C's from 329 bytes more CSS. Kindle Previewer 4 converts all
three variants with Enhanced Typesetting, 0 errors and 0 quality issues.

## Building the candidates

```sh
python -m tanakh_epub experiment-layout                     # every book with local data
python -m tanakh_epub experiment-layout --chapter Genesis 1 # the offline benchmark
python -m tanakh_epub experiment-layout --chapter Genesis 1 --kpf   # + Kindle Previewer KPFs
python -m tanakh_epub experiment-layout --profiles balanced dense
```

Output, in `output/`:

```text
layout_A_current.epub
layout_B_balanced.epub
layout_C_dense.epub
layout_experiment.txt          the parameters and sizes of each, as printed
```

The command loads the content once and builds every variant from it. It then compares the
archives and **fails if anything other than the stylesheet, the title and the
identifier differs**: every chapter file, the navigation, the sources page and both fonts
must be byte-identical. The title carries a Hebrew label (`… — פריסה ג׳`) and the
identifier is derived from the profile, so they sit side by side in the Kindle library
instead of replacing each other.

A normal `build` uses `layout.profile` (currently `current`, i.e. A) and accepts
`--layout-profile NAME` to try another. Settling D10 means changing that one line.

Nothing in any profile is specific to Genesis. The same profiles apply unchanged to
any selection, up to the full Tanakh.

## The device test (human)

**Benchmark.** בראשית פרק א׳, all 31 verses: 55 Rashi entries, including the very long
א׳:א׳, verses with five and seven entries, seven verses with no Rashi, and one-line and
multi-line verses. The offline fixtures hold one chapter, so **chapter and book
boundaries cannot be tested yet**. Repeat the comparison with the full Genesis build in
Phase 2, and across books in Phase 3.

**Conditions.** Sideload all three through the same path (D1), select **Publisher Font** in
each, and read each at three Kindle font sizes: **small, default and large**. These are
settings on the device, not something in the EPUB. Use the same sizes for all three.

**For each variant × size, note:**

1. Hebrew readability of the biblical text.
2. ניקוד / טעמים collisions between lines. Check the verses that wrap, such as א׳:ז׳.
3. Rashi readability (this also answers D4).
4. Verse → Rashi association: is it obvious which verse a Rashi belongs to?
5. Ugly fragments at page boundaries: a lone רש״י label, one line of an entry, or a verse
   stranded from its commentary.
6. Blank space: pages that end early.
7. Useful text per screen: verses per page turn in the first few pages.
8. Comfort over a longer stretch of reading, not just a first impression.
9. What changes when the font size changes. Everything should scale together.
10. Transitions at the chapter start (and, once the data exists, between chapters and books).

Record the results, then decide D10 (`docs/DECISIONS.md`), set
`layout.profile`.

## What cannot be verified automatically

- Where the Paperwhite actually puts page breaks, and whether it honours any hint.
- How the Kindle's own text shaper positions marks. The collision margin above was measured
  with HarfBuzz, not with the Kindle's shaper.
- Legibility and comfort.
- EPUBCheck was not run in the session that added the experiment (no Java on that machine).
  Kindle Previewer's conversion was run, and reported 0 errors.

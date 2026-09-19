# Markup rules

How Sefaria's inline markup becomes internal markup. The authority is
`src/tanakh_epub/processing/markup.py` → `RULES`; this file explains each row and records
where it was seen. When the converter stops the build on unknown markup, its message points
here — add the row *and* the rule together.

> **Scope.** These rules cover exactly the patterns `inventory-markup` found in the cached
> data — all 39 books and their Rashi, 51,434 strings, as of 2026-09-19 — and nothing more. That is
> deliberate: an untested rule is worse than a loud failure. Run
> `python -m tanakh_epub inventory-markup` after fetching each new book; it exits non-zero
> and names the first reference of anything without a rule.

## Sources these rules were derived from

| | Version | Inventoried over |
|---|---|---|
| Tanakh | *Miqra according to the Masorah* | all 39 books — 23,206 verses |
| Rashi | the seven versions in `config/default.yaml` (D6) | all 39 books — 28,228 entries |

## Implemented rules

| Sefaria markup | Found in | Rule | Example |
|---|---|---|---|
| `<b>…</b>` leading a commentary entry | Rashi | Extracted as `dibur_hamatchil`, removed from `text`; rendered as `<span class="dibur-hamatchil">`. Structural extraction from Sefaria's own markup — never a text match against the verse. | `Rashi on Genesis 1:1:1` → `בראשית.` |
| `<b>…</b>` anywhere else | both | Kept as `<b>` | `Genesis 1:29` — a bold paseq `׀` |
| `<big>…</big>` | Tanakh | `<span class="letter-large">` | `Genesis 1:1` — the enlarged ב of בראשית |
| `<small>…</small>` | Tanakh | `<span class="letter-small">` | `Genesis 1:5` — the paseq `׀` |
| `<span class="mam-spi-pe">{פ}</span>` | Tanakh | `<span class="parasha-marker">`; the `{פ}` also ends the paragraph | `Genesis 1:5`, `1:8`, `1:13` |
| `<span class="mam-spi-samekh">{ס}</span>` | Tanakh | `<span class="parasha-marker">`; an open parasha does **not** end the paragraph | `Genesis 3:15` (48 in Genesis) |
| `<span class="mam-kq">` with `mam-kq-k` and `mam-kq-q` inside | Tanakh | The spans are removed and the text kept whole. MAM puts the כתיב in parentheses and the קרי in brackets inside the text, as printed Tanakhs do, so nothing is lost | `Genesis 8:17` → `(הוצא) [הַיְצֵ֣א]` (12 in Genesis) |
| `<span class="mam-kq-trivial">` | Tanakh | Span removed, word kept. A כתיב/קרי difference MAM prints as a single vocalized word | `Genesis 13:3` אׇֽהֳלֹה֙ (4 in Genesis) |
| `<sup class="footnote-marker">*</sup>` + `<i class="footnote">…</i>` | Tanakh | **Dropped with their content** (`SPEC_DATA_SOURCE.md` §9.2). MAM's notes on other manuscript traditions, e.g. `(בספרי ספרד ואשכנז מִנְּשֽׂוֹא)`. A note may contain `<big>`; it goes with the note | `Genesis 4:13`, `5:1` (7 in Genesis) |
| `<small>…</small>` inside a Rashi entry | Rashi | `<span class="letter-small">`, as in the Tanakh | `Rashi on Genesis 17:13:1` — `(ס"א …)` |
| `<span class="mam-spi-invnun">׆</span>` | Tanakh | Span removed, the inverted nun kept | `Numbers 10:35–36`, `Psalms 107` (9 in all) |
| `<span class="mam-implicit-maqaf">־</span>` | Tanakh | Span removed, the maqaf kept | `Psalms 1:1` (109, all in Psalms, Proverbs, Job) |
| `<sup>…</sup>` with no class | Tanakh | **Kept**, as `<span class="letter-small">`. These are the four suspended letters (אותיות תלויות): `Judges 18:30` מְ**נַ**שֶּׁה, `Psalms 80:14`, `Job 38:13`, `38:15`. `SPEC_DATA_SOURCE.md` §9.2's "drop `<sup>`" is meant for footnote markers, which carry a class here; dropping these would delete letters of the text. Raising them would need `vertical-align`, which is outside SPEC §26's Kindle-safe CSS, so they are set small instead | `Judges 18:30` |
| `<br>` inside `<b>` | Rashi | A space. The paragraph cannot end inside the bold without splitting it | `Rashi on Job 38:1:1` (once) — a dibur hamatchil on two lines |
| `<br>` | both | Paragraph break | `Genesis 1:5`, after the parasha marker |
| `&nbsp;` `&thinsp;` | Tanakh | Resolved to U+00A0 and U+2009 and **kept**. They are deliberate typography — they space the paseq and the parasha marker — so whitespace collapsing skips them. | `Genesis 1:5` |
| Bidi controls U+200E, U+200F, U+202A, U+202C; U+200D; U+034F | Rashi | Kept — text, not markup. Invisible, so the glyph check skips them. The one U+202A (Rashi on Exodus 1:21:1) wraps only a full stop, and the stray U+202C have nothing to close | `Rashi on Exodus 1:11:3` |
| **anything else** | both | **The build stops**, naming the tag, the class and the reference. | — |

## Known, not yet ruled on

| Markup | Where | Note |
|---|---|---|
| `<i>…</i>` with no class | not in Genesis | `SPEC_DATA_SOURCE.md` §9.2 says keep as `<em>`; the rule is added when a book actually has one |

## Not markup, but worth knowing

- **Presentation forms.** `Rashi on Genesis 43:10:1` spells some letters with precomposed
  Hebrew presentation forms (U+FB2A–FB4B, e.g. כּ as one character). NFC splits each into
  letter + mark. Same text; `validate` counts these separately from the ordinary mark
  reordering and fails only if the decomposed text would change.
- **Characters the fonts lack.** Taamey Frank CLM has no `…` (U+2026), `–` (U+2013) or
  `—` (U+2014). The first two occur in some Rashi opening words, which are set in the
  biblical font; the Kindle draws those characters from a fallback font. `validate` lists
  each with its first reference.
- **Joshua 21:36–37** are `—` in MAM. The edition omits these two verses, following the
  Aleppo Codex tradition, and leaves the dash in their place. Kept as the source has it.

## Internal markup

After conversion, `Verse.hebrew_text` and `CommentaryEntry.text` contain only:

- `<b>`, `<em>`
- `<span class="letter-large">`, `<span class="letter-small">`, `<span class="parasha-marker">`
- paragraph breaks, carried as a blank line (`\n\n`) and split by `markup.paragraphs()`

`markup.assert_internal_markup_only()` enforces this on every verse and every entry before
anything is rendered (`SPEC_DATA_SOURCE.md` §9.3).

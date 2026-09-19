# Markup rules

How Sefaria's inline markup becomes internal markup. The authority is
`src/tanakh_epub/processing/markup.py` → `RULES`; this file explains each row and records
where it was seen. When the converter stops the build on unknown markup, its message points
here — add the row *and* the rule together.

> **Scope.** These rules cover exactly the patterns `inventory-markup` found in the cached
> data — all of Genesis and Rashi on Genesis, as of 2026-09-19 — and nothing more. That is
> deliberate: an untested rule is worse than a loud failure. Run
> `python -m tanakh_epub inventory-markup` after fetching each new book; it exits non-zero
> and names the first reference of anything without a rule.

## Sources these rules were derived from

| | Version | Inventoried over |
|---|---|---|
| Tanakh | *Miqra according to the Masorah* | all of בראשית — 1,533 verses |
| Rashi | *Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934* | all of רש״י על בראשית — 2,016 entries |

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
| `<br>` | both | Paragraph break | `Genesis 1:5`, after the parasha marker |
| `&nbsp;` `&thinsp;` | Tanakh | Resolved to U+00A0 and U+2009 and **kept**. They are deliberate typography — they space the paseq and the parasha marker — so whitespace collapsing skips them. | `Genesis 1:5` |
| U+200F RIGHT-TO-LEFT MARK | Rashi | Kept — it is text, not markup | `Rashi on Genesis 5:24:1` (once) |
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
- **Characters the fonts lack.** Taamey Frank CLM has no `…` (U+2026). It occurs in two
  Rashi opening words (`Rashi on Genesis 25:27:1`, `44:18:1`), which are set in the
  biblical font, so the Kindle draws that one character from a fallback font. `validate`
  lists every such character as a warning.

## Internal markup

After conversion, `Verse.hebrew_text` and `CommentaryEntry.text` contain only:

- `<b>`, `<em>`
- `<span class="letter-large">`, `<span class="letter-small">`, `<span class="parasha-marker">`
- paragraph breaks, carried as a blank line (`\n\n`) and split by `markup.paragraphs()`

`markup.assert_internal_markup_only()` enforces this on every verse and every entry before
anything is rendered (`SPEC_DATA_SOURCE.md` §9.3).

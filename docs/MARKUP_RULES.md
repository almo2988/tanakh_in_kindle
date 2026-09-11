# Markup rules

How Sefaria's inline markup becomes internal markup. The authority is
`src/tanakh_epub/processing/markup.py` → `RULES`; this file explains each row and records
where it was seen. When the converter stops the build on unknown markup, its message points
here — add the row *and* the rule together.

> **Phase 1 scope.** These rules cover exactly the patterns present in the checked-in
> fixtures (`tests/fixtures/genesis_1.json`, `tests/fixtures/rashi_genesis_1.json`) and
> nothing more. That is deliberate: an untested rule is worse than a loud failure. Phase 2
> runs `inventory-markup` over the whole dataset and completes the table from what it finds
> (`PROGRESS.md` task 2.5 / 2.6, `SPEC_DATA_SOURCE.md` §9).

## Sources these rules were derived from

| | Version | Inventoried over |
|---|---|---|
| Tanakh | *Miqra according to the Masorah* | בראשית פרק א׳ (fixture) — and the whole book was surveyed once during capture |
| Rashi | *Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934* | רש״י על בראשית פרק א׳ (fixture) |

## Implemented rules

| Sefaria markup | Found in | Rule | Example |
|---|---|---|---|
| `<b>…</b>` leading a commentary entry | Rashi | Extracted as `dibur_hamatchil`, removed from `text`; rendered as `<span class="dibur-hamatchil">`. Structural extraction from Sefaria's own markup — never a text match against the verse. | `Rashi on Genesis 1:1:1` → `בראשית.` |
| `<b>…</b>` anywhere else | both | Kept as `<b>` | `Genesis 1:29` — a bold paseq `׀` |
| `<big>…</big>` | Tanakh | `<span class="letter-large">` | `Genesis 1:1` — the enlarged ב of בראשית |
| `<small>…</small>` | Tanakh | `<span class="letter-small">` | `Genesis 1:5` — the paseq `׀` |
| `<span class="mam-spi-pe">{פ}</span>` | Tanakh | `<span class="parasha-marker">`; the `{פ}` also ends the paragraph | `Genesis 1:5`, `1:8`, `1:13` |
| `<br>` | both | Paragraph break | `Genesis 1:5`, after the parasha marker |
| `&nbsp;` `&thinsp;` | Tanakh | Resolved to U+00A0 and U+2009 and **kept**. They are deliberate typography — they space the paseq and the parasha marker — so whitespace collapsing skips them. | `Genesis 1:5` |
| **anything else** | both | **The build stops**, naming the tag, the class and the reference. | — |

## Known, not yet ruled on

Seen elsewhere in Genesis under MAM, outside the fixture chapter. Each will stop the build
until Phase 2 gives it a rule — which is the intended behaviour, not a gap:

| Markup | Count in Genesis | Likely meaning |
|---|---|---|
| `<span class="mam-spi-samekh">` | 48 | open parasha marker `{ס}` — does **not** end the paragraph |
| `<span class="mam-kq">`, `mam-kq-k`, `mam-kq-q`, `mam-kq-trivial` | 12 / 12 / 12 / 4 | כתיב/קרי — the class carries the whole meaning, so it cannot be ignored |
| `<sup class="footnote-marker">` + `<i class="footnote">` | 7 each | MAM editorial footnotes — `SPEC_DATA_SOURCE.md` §9.2 says drop, content included |
| `<i>…</i>` | 0 in Genesis | `SPEC_DATA_SOURCE.md` §9.2 says keep as `<em>` |

## Internal markup

After conversion, `Verse.hebrew_text` and `CommentaryEntry.text` contain only:

- `<b>`, `<em>`
- `<span class="letter-large">`, `<span class="letter-small">`, `<span class="parasha-marker">`
- paragraph breaks, carried as a blank line (`\n\n`) and split by `markup.paragraphs()`

`markup.assert_internal_markup_only()` enforces this on every verse and every entry before
anything is rendered (`SPEC_DATA_SOURCE.md` §9.3).

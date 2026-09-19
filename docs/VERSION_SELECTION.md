# Version selection — D5 (Tanakh) and D6 (Rashi)

Candidates for the two Phase 2 decisions, surveyed on 2026-09-19 from the Sefaria API
(`/api/texts/versions/<index>`) and the Sefaria-Export bucket, over the whole of Genesis
and Rashi on Genesis. The human decides; the recommendation is marked.
`SPEC_DATA_SOURCE.md` §4–§5 give the criteria.

## D5 — the Tanakh text

Both candidates have ניקוד and טעמים, all 50 chapters and 1,533 verses of Genesis, and
exist for all 39 books in the export.

| | **Miqra according to the Masorah** (MAM) — *recommended, and what is built today* | Tanach with Ta'amei Hamikra |
|---|---|---|
| License | CC BY-SA | Public Domain |
| Source | Aleppo Codex and related manuscripts, edited by User:Dovi on Hebrew Wikisource | tanach.us (Westminster Leningrad Codex) |
| Enlarged and reduced letters | Marked (`<big>`, `<small>`) — the large ב of בראשית | Not marked |
| Parasha breaks | `{פ}` ends the paragraph, `{ס}` stays inline | Plain text `(פ)` / `(ס)`, no paragraph break |
| כתיב/קרי | Both readings: `(הוצא) [הַיְצֵ֣א]` | Both readings, כתיב without parentheses: `הוצא [הַיְצֵ֣א]` |
| Paseq / legarmeih | Visibly distinguished | Plain `׀` |
| Qamats qatan | Its own Unicode character | Ordinary qamats |
| Editorial notes | 7 in Genesis (other manuscript traditions) — **dropped** by the markup rules | None |
| Tested on the Paperwhite | Yes — marks stack correctly (D2) | No |
| Markup rules needed | 11 patterns, all covered | None |

**Why MAM:** it is the richer reading text (large letters, real paragraph breaks,
qamats qatan), it is what the device test passed on, and every pattern in Genesis already
has a rule. **What it costs:** CC BY-SA obliges the book to name the source and the
license — the מקורות page already does — and anyone who redistributes a modified version
must share it under the same license. For a personal Kindle copy that changes nothing.

## D6 — Rashi

**No single Hebrew Rashi version covers the whole Tanakh on Sefaria.** This does not affect
Phase 2, which is Genesis only, but it decides how Phase 3 is configured.

For Genesis:

| | **Rosenbaum & Silbermann 1929–1934** — *recommended, and what is built today* | On Your Way | Metsudah 2009 |
|---|---|---|---|
| License | Public Domain | Public Domain | CC BY |
| Vocalized | Yes (2,014 of 2,016 entries) | No | — |
| Entries on Genesis | 2,016 | 2,001 | — |
| Dibur hamatchil | Leading `<b>` | Leading `<b>` | — |
| Other markup | One `<small>` (ס"א in 17:13) | None | — |

Rosenbaum & Silbermann is missing one entry that Sefaria's index counts: Genesis 21:2,
`לזקניו`, which only the Metsudah version has. `validate` reports it as a warning.

Across the Tanakh (Hebrew versions of `Rashi on <book>` in the export index, 2026-09-07):

| Version | Books | License | Vocalized |
|---|---|---|---|
| Rosenbaum & Silbermann 1929–1934 | Genesis, Exodus, Leviticus, Deuteronomy | Public Domain | Yes |
| Rosenbaum & Silbermann — corrected vocalization | Numbers only (a different version title) | Public Domain | Yes |
| Sefaria vocalized edition | 26 books of Nevi'im and Ketuvim | **unknown** | Yes |
| On Your Way | 37 books (I and II Kings are "On Your Way -- new") | Public Domain | No |
| Metsudah (several titles) | Torah, Joshua, Kings, the five Megillot | CC BY | Yes |
| `merged` | all 39 | — | mixed |

`merged` is Sefaria's combination of several versions. It is never used: which version
each entry came from would be lost, and the spec requires one recorded version per text.

**What Phase 3 needs from D6:** a version per book, not one per commentator. The likely
shape is Rosenbaum & Silbermann for the Torah (with its Numbers variant), then either the
Sefaria vocalized edition (vocalized like the Torah, but its license is unrecorded and has
to be asked of Sefaria before it is embedded) or On Your Way (Public Domain, but
unvocalized — a visible change of style between Deuteronomy and Joshua). Books that
neither covers (Joshua, Ruth, Song of Songs, Lamentations, Ecclesiastes, Esther, Kings)
fall back to Metsudah or On Your Way. The config and `fetch` do not support per-book
versions yet; that is Phase 3 task 3.1.

**For Phase 2:** keep Rosenbaum & Silbermann for Genesis.

**Decided 2026-09-19 (D6): vocalized Rashi throughout.** Rosenbaum & Silbermann for the
Torah (Numbers under its "corrected vocalization" title), Metsudah for Joshua, both books of
Kings and the five Megillot, and the Sefaria vocalized edition for the other 26 books. The
human chose the vowel points over a clear license for those 26: Sefaria lists that
edition's license as "unknown", the מקורות page says so, and the build is for personal
reading. `config/default.yaml` holds the mapping; per-book versions are implemented.

**Entry counts.** Sefaria's index counts differ from the chosen versions by a few entries
in 17 books, in both directions. Fewer can mean the entry exists only in another version
(Genesis 21:2); more means the index is stale (Rashi on Jonah has 53 entries in Sefaria's
own merge of all versions, and the index says 51). `validate` reports these as warnings.

## Book titles (D7)

All 39 `sefaria_title` values in `config/books.yaml` match Sefaria index titles exactly,
checked against the export index (2026-09-19). Each also has a MAM and a Ta'amei Hamikra
version, and a `Rashi on <book>` index.

## Where the data comes from

The Sefaria-Export repository on GitHub no longer holds the text. Since 2026 it is an
index (`books.json`) plus scripts, and the files are in a public Google Cloud Storage
bucket at `https://storage.googleapis.com/sefaria-export/json/<categories>/<title>/Hebrew/<version>.json`.
`fetch` builds that path from the index's own `categories` and falls back to the API when
the export has no file. Both sources return the same text: chapter 1 of Genesis and of
Rashi on Genesis matched the checked-in fixtures (captured from the API) byte for byte.

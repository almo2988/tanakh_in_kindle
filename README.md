# תנ״ך עם פירוש רש״י — a Hebrew Tanakh + Rashi EPUB for the Kindle Paperwhite

A Python generator that builds a reflowable Hebrew EPUB 3 of the Tanakh with Rashi's
commentary, for reading on a **Kindle Paperwhite (12th gen, 2024)**. All content comes from
[Sefaria](https://www.sefaria.org/).

Reading content is **Hebrew only**. English appears in filenames, logs, config and the
version identifiers the source licenses require you to name — never in the book itself.

> **Status: Phase 3 (full Tanakh).** All 39 books with רש״י build into one EPUB,
> `output/Tanakh_with_Rashi.epub`. What is left is the device test. `PROGRESS.md` is the
> authority on what is done and what is next.

---

## Quick start

```sh
uv sync                       # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
python -m tanakh_epub fetch                       # all 39 books + Rashi into data/cache/ (~230 requests)
python -m tanakh_epub inventory-markup            # must report 0 unknown patterns
python -m tanakh_epub validate                    # counts, markup, NFC, glyphs, file sizes
python -m tanakh_epub build                       # → output/Tanakh_with_Rashi.epub (~5.5 MB)
python -m tanakh_epub check output/Tanakh_with_Rashi.epub
```

Every command takes `--book Genesis` (or `--books …`) to work on part of the Tanakh.
`build` also writes `Tanakh_with_Rashi.build_manifest.json` and
`Tanakh_with_Rashi.SOURCES_AND_LICENSES.md` next to the book. The book keeps the same
identifier from build to build, so sending a rebuilt copy replaces the old one on the
Kindle; `build --new-identifier` makes it a new book instead.

`fetch` is the only command that uses the network. It reads Sefaria's public export
bucket, falls back to the API, and skips a book already cached in the configured version.
Everything else reads the cache, so builds work offline. A book that was never fetched
falls back to the checked-in fixtures (בראשית א׳ only), so this still works with no network:

```sh
python -m tanakh_epub build --chapter Genesis 1 --max-verse 10 --output output/Genesis_Chapter_1.epub
```

`check` runs EPUBCheck, and Kindle Previewer as well if it is installed. Neither is
required to build; both say "SKIPPED" rather than quietly passing when absent.

Requires Python 3.12+. `scripts/epubcheck.sh` downloads EPUBCheck into `tools/` on first
use. It needs Java; on a Mac without a JDK it uses the Java bundled inside Kindle Previewer.
Kindle Previewer itself is macOS/Windows only and cannot be installed by a script.

```sh
pytest                        # offline; network tests skipped unless RUN_NETWORK_TESTS=1
ruff check . && ruff format .
```

### Layout experiment

The layout was chosen on the Paperwhite: C-dense (decision D10), which every build now uses.
The comparison command is kept for future changes. It builds the same content with each
layout:

```sh
python -m tanakh_epub experiment-layout --chapter Genesis 1
```

This writes `output/layout_A_current.epub`, `layout_B_balanced` and `layout_C_dense`, plus a
report of each one's parameters and sizes. Only the stylesheet, the title and the
identifier differ between them, so all three can sit in the Kindle library together. What to compare, and at which font sizes, is in
`docs/LAYOUT_EXPERIMENT.md`.

---

## Getting the book onto the Kindle

The Kindle does not read EPUB directly — it converts to KFX. **Which path you use changes
what survives**. Send to Kindle (Path B) is the path tested on the Paperwhite and chosen
(decision D1 in `PROGRESS.md`); Path A is kept as a fallback but has not been tested.

### First, on the device — this is not optional

Open the book, tap **Aa** → **Font** → select **Publisher Font**.

Embedded fonts apply *only* under Publisher Font. Without it the Kindle uses its stock
Hebrew face, which stacks ניקוד and טעמים badly — which is the entire reason this project
embeds a font. If א׳:א׳ looks wrong, check this before anything else.

### Path A — Calibre → KFX → USB (untested fallback)

Most predictable: fonts and RTL survive reliably, but it needs desktop tooling.

1. Install [Kindle Previewer 3](https://www.amazon.com/Kindle-Previewer/b?node=21381691011)
   (macOS/Windows). The KFX plugin drives it.
2. Install [Calibre](https://calibre-ebook.com/), then
   *Preferences → Plugins → Get new plugins* → **KFX Output**. Restart Calibre.
3. Add `output/Genesis_Chapter_1.epub` to the Calibre library.
4. *Convert books* → output format **KFX** → OK.
5. Connect the Paperwhite over USB and *Send to device*, or copy the `.kfx` into
   `documents/` on the Kindle yourself.
6. Eject, open the book, and select **Publisher Font**.

### Path B — Send to Kindle (the chosen path)

No tooling, wireless, but Amazon's server-side converter decides what survives, and it
sometimes drops embedded fonts.

1. Go to [Send to Kindle](https://www.amazon.com/sendtokindle) (or email the file to your
   `@kindle.com` address from an approved sender address).
2. Upload the `.epub`, pick the device, send.
3. Open the book on the Paperwhite and select **Publisher Font**.

### Then check it — on the device, not in a desktop viewer

Work through the checklist in `SPEC.md` §3.3 and record the results in the Phase 1 device
table in `PROGRESS.md`. The short version:

- ניקוד and טעמים stack correctly in בראשית א׳:א׳
- page turns go **right to left**
- verse numbers, geresh and gershayim render correctly
- changing the font size scales verse, verse number and commentary together
- **Go to** lists בראשית → פרק א׳, and the link lands in the right place
- verses without Rashi (א׳:ג׳ in the POC) show no empty רש״י block

---

## How it fits together

```
Sefaria export / API        fetch only: whole books, never single verses
      ↓
data/cache/                 the text verbatim, with version, license and Sefaria's counts
      ↓
providers/local.py          everything after fetch reads the cache
      ↓
processing/markup.py        explicit rules; unknown markup fails the build
processing/normalize.py     NFC only — never strips ניקוד or טעמים
      ↓
models.py                   Verse · CommentaryEntry · StudyUnit
      ↓
processing/study_units.py   verse + the Rashi entries on that verse
      ↓
rendering/                  one XHTML file per chapter, RTL, generated CSS
      ↓
epub/                       OPF · nav.xhtml · toc.ncx · zip
```

| Path | What it holds |
|---|---|
| `config/books.yaml` | the 39 books: Sefaria title, Hebrew title, slug, section |
| `config/default.yaml` | fonts, typography, spacing, page-break hints, layout profiles, sources — every tunable |
| `config/commentators.yaml` | Hebrew label, slug and Sefaria prefix per commentator |
| `data/cache/` | fetched books (git-ignored) |
| `tests/fixtures/` | real Sefaria data, captured once by `scripts/capture_fixtures.py` |
| `fonts/` | only fonts whose license has been read and recorded |
| `docs/` | notes that outlive a session |

Reading order for anyone picking this up: `CLAUDE.md` (how to work) → `PROGRESS.md` (where
we are) → `SPEC.md` and `SPEC_DATA_SOURCE.md` (what to build).

---

## Content and licensing

Texts come from Sefaria under the versions named in `config/default.yaml`, and the built
EPUB reproduces those names and licenses on its מקורות page:

| | Version | License | Books |
|---|---|---|---|
| Tanakh | *Miqra according to the Masorah* | CC BY-SA | all 39 |
| Rashi | *Rosenbaum & Silbermann, 1929–1934* (Numbers: *corrected vocalization*) | Public Domain | Torah |
| Rashi | Metsudah editions | CC BY | Joshua, Kings, the five Megillot |
| Rashi | *Sefaria vocalized edition* | **unknown** (as Sefaria lists it) | the other 26 books |

The last license is not recorded by Sefaria, so the book is for personal reading: do not
redistribute it without clearing that with Sefaria. Why each version was chosen is in
`docs/VERSION_SELECTION.md`.

Two fonts are embedded, each with its license read and recorded in `fonts/README.md`:
**Taamey Frank CLM** for the biblical text (GPL-2.0 with the Culmus font-embedding
exception) and **Noto Rashi Hebrew** for the commentary (SIL OFL 1.1). The generator code
itself is MIT.

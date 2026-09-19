# תנ״ך עם פירוש רש״י — the Tanakh with Rashi, for the Kindle

Builds the whole Hebrew Tanakh with Rashi's commentary as **one EPUB** for a Kindle
Paperwhite. Every verse is followed by its Rashi, in Rashi script. The text has full ניקוד
and טעמים and is set in a font that stacks them correctly. All text comes from
[Sefaria](https://www.sefaria.org/).

- all 39 books, 929 chapters, 23,206 verses, 28,228 Rashi entries, in one ~5.5 MB file
- "Go to" lists every book, and every chapter under it
- pages turn right to left; the book itself is Hebrew only
- built and tested on a Kindle Paperwhite (12th generation, 2024)

The book is not distributed here: you build it yourself from Sefaria's data, in two
commands. Why is under [Licensing](#licensing).

---

## Build it

You need **Python 3.12+**, [**uv**](https://docs.astral.sh/uv/), and an internet
connection for the one-time download.

```sh
git clone https://github.com/almo2988/tanakh_in_kindle.git
cd tanakh_in_kindle
uv sync
uv run python -m tanakh_epub fetch     # download the text once, ~5 minutes
uv run python -m tanakh_epub build     # → output/Tanakh_with_Rashi.epub, ~1 minute
```

`fetch` downloads all 39 books and their Rashi from Sefaria into `data/cache/` (about 230
polite requests, one second apart). It only needs to run once; after that every build
works offline. If you run `build` before `fetch`, it stops and tells you what to download
— it never produces a partial book.

<details>
<summary>Without uv</summary>

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m tanakh_epub fetch
.venv/bin/python -m tanakh_epub build
```
</details>

---

## Put it on the Kindle

1. Go to **[amazon.com/sendtokindle](https://www.amazon.com/sendtokindle)**, drag in
   `output/Tanakh_with_Rashi.epub`, pick your Kindle and send. (Emailing the file to your
   `@kindle.com` address works too.)
2. When it arrives, open it and tap **Aa → Font → Publisher Font**.

**Publisher Font matters.** It is what shows the verses in the embedded biblical font, which
stacks ניקוד and טעמים correctly; the Kindle's own Hebrew fonts do not. Rashi is always in
Rashi script, whichever font you pick.

**Updating.** A rebuilt book keeps the same identity, so sending it again replaces the copy
on the Kindle rather than adding a second one. To keep both, build with
`--new-identifier`.

<details>
<summary>Alternative: Calibre over USB (untested)</summary>

Install [Calibre](https://calibre-ebook.com/) with the **KFX Output** plugin (which needs
[Kindle Previewer](https://www.amazon.com/Kindle-Previewer/b?node=21381691011)), convert the
EPUB to KFX, and copy it to the Kindle's `documents/` folder over USB. Send to Kindle is the
path that was tested; this one is not.
</details>

---

## Other things you can do

```sh
uv run python -m tanakh_epub validate            # check the downloaded text before building
uv run python -m tanakh_epub build --book Psalms # one book
uv run python -m tanakh_epub build --books Genesis Exodus
uv run python -m tanakh_epub check output/Tanakh_with_Rashi.epub
```

- **`validate`** checks that every chapter and verse is present against Sefaria's own
  counts, that every piece of markup has a rule, that nothing is lost in Unicode
  normalization, and that both fonts can draw every character. It lists anything worth a
  look as a warning.
- **`check`** runs [EPUBCheck](https://www.w3.org/publishing/epubcheck/) and, if
  installed, Kindle Previewer's conversion. EPUBCheck needs Java; on a Mac without one it
  uses the Java inside Kindle Previewer. A missing tool is reported as skipped, never as
  passed.
- **`build`** also writes `Tanakh_with_Rashi.build_manifest.json` (exactly what went into
  the book) and `Tanakh_with_Rashi.SOURCES_AND_LICENSES.md` next to the EPUB.
- **Offline demo:** `build --chapter Genesis 1 --max-verse 10` builds בראשית א׳:א׳–י׳ from
  the test data in the repo, with no download.

Settings live in `config/default.yaml`: text versions, fonts, sizes and spacing, and the
layout profile. `experiment-layout` builds the same chapter once per layout profile for
comparing on a device (`docs/LAYOUT_EXPERIMENT.md`).

---

## How it works

```
Sefaria export / API       fetch: whole books, never single verses; stored verbatim
      ↓
data/cache/                the text, with its version, license and Sefaria's counts
      ↓
processing/                Sefaria markup → a small internal markup, by explicit rules;
                           unknown markup stops the build; Unicode NFC, nothing else
      ↓
models.py                  Verse · CommentaryEntry · StudyUnit (a verse and its Rashi)
      ↓
rendering/                 one XHTML file per chapter, right to left, generated CSS
      ↓
epub/                      OPF · nav · NCX · cover · sources page · build manifest → zip
```

| Path | What it holds |
|---|---|
| `config/default.yaml` | versions, fonts, typography, spacing, layout profiles, cover |
| `config/books.yaml` | the 39 books: Sefaria title, Hebrew title, file slug, section |
| `config/commentators.yaml` | Hebrew label and Sefaria prefix per commentator |
| `fonts/` | the two embedded fonts and their licenses |
| `docs/DECISIONS.md` | every design decision, and what testing on the Kindle taught |
| `docs/MARKUP_RULES.md` | how each piece of Sefaria markup is handled |
| `docs/VERSION_SELECTION.md` | why these Tanakh and Rashi versions |
| `SPEC.md`, `SPEC_DATA_SOURCE.md` | the full specification |
| `tests/fixtures/` | real Sefaria data for בראשית א׳, so the tests run offline |

Rules the code keeps: the Hebrew text is never altered (Unicode NFC only, never stripping
ניקוד or טעמים); Sefaria markup without a rule fails the build rather than being dropped;
Sefaria is read only through its API and public export, never by scraping the website;
the CSS stays within what the Kindle reliably supports.

### Development

```sh
uv sync --extra dev
uv run pytest                              # offline
RUN_NETWORK_TESTS=1 uv run pytest          # also checks the live Sefaria endpoints
uv run ruff check . && uv run ruff format .
```

`CLAUDE.md` holds the working rules for AI-assisted changes; they apply to people too.
Anything that changes what the reader sees needs a test on a real Kindle before it counts
as done.

---

## Licensing

**The code** is MIT-licensed (`LICENSE`).

**The fonts** in `fonts/` are redistributable and embedded under their own licenses:
Taamey Frank CLM (GPL-2.0 with the Culmus font-embedding exception) and Noto Rashi Hebrew
(SIL OFL 1.1). See `fonts/README.md`.

**The texts** are not in this repository. `fetch` downloads them from Sefaria, and the built
book names each version and its license on its last page (מקורות):

| | Version | License | Books |
|---|---|---|---|
| Tanakh | *Miqra according to the Masorah* | CC BY-SA | all 39 |
| Rashi | *Rosenbaum & Silbermann, 1929–1934* | Public Domain | the Torah |
| Rashi | Metsudah editions | CC BY | Joshua, Kings, the five Megillot |
| Rashi | *Sefaria vocalized edition* | not stated by Sefaria | the other 26 books |

Sefaria does not state a license for the vocalized Rashi used in most of the Prophets and
Writings. It was chosen for its vowel points. So **build the book for your own reading and
do not redistribute the EPUB** unless you have cleared that edition with Sefaria. The
reasoning, and the alternative (an unvocalized Public Domain edition), are in
`docs/VERSION_SELECTION.md`.

This project is not affiliated with Sefaria or Amazon.

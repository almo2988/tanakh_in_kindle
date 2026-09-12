# תנ״ך עם פירוש רש״י — a Hebrew Tanakh + Rashi EPUB for the Kindle Paperwhite

A Python generator that builds a reflowable Hebrew EPUB 3 of the Tanakh with Rashi's
commentary, for reading on a **Kindle Paperwhite (12th gen, 2024)**. All content comes from
[Sefaria](https://www.sefaria.org/).

Reading content is **Hebrew only**. English appears in filenames, logs, config and the
version identifiers the source licenses require you to name — never in the book itself.

> **Status: Phase 1 (proof of concept).** The build runs from checked-in fixtures —
> בראשית פרק א׳ with רש״י — and needs no network. Fetching the real Tanakh from Sefaria is
> Phase 2. `PROGRESS.md` is the authority on what is done and what is next.

---

## Quick start

```sh
uv sync                       # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
python -m tanakh_epub build --chapter Genesis 1 --max-verse 10 \
    --output output/Genesis_Chapter_1.epub
python -m tanakh_epub check output/Genesis_Chapter_1.epub
```

### Collapsible commentary

`commentary.mode` decides how Rashi sits on the page:

| Mode | Result |
|---|---|
| `inline` (default) | every entry in the reading flow, under a רש״י divider |
| `details` | collapsed behind a רש״י bar; tap to open, tap to close |

```sh
python -m tanakh_epub build --chapter Genesis 1 --max-verse 10 \
    --commentary-mode details --output output/Genesis_Chapter_1_Details.epub
```

`details` uses native HTML5 `<details>`/`<summary>` — no JavaScript. It works in Apple
Books, Kobo and Thorium; **Amazon documents no support for it**, so whether a Kindle
collapses it, renders it permanently expanded, or drops it has to be established on the
device. `inline` stays the default until it is.

`check` runs EPUBCheck, and Kindle Previewer 3 as well if it is installed. Neither is
required to build; both say "SKIPPED" rather than quietly passing when absent.

Requires Python 3.12+. `scripts/epubcheck.sh` downloads EPUBCheck into `tools/` on first
use (needs Java); `scripts/kindle_previewer.sh` cannot install Kindle Previewer, which is
macOS/Windows only.

```sh
pytest                        # offline; network tests skipped unless RUN_NETWORK_TESTS=1
ruff check . && ruff format .
```

---

## Getting the book onto the Kindle

The Kindle does not read EPUB directly — it converts to KFX. **Which path you use changes
what survives**, so the proof of concept is tested through both before one is frozen
(decision D1 in `PROGRESS.md`).

### First, on the device — this is not optional

Open the book, tap **Aa** → **Font** → select **Publisher Font**.

Embedded fonts apply *only* under Publisher Font. Without it the Kindle uses its stock
Hebrew face, which stacks ניקוד and טעמים badly — which is the entire reason this project
embeds a font. If א׳:א׳ looks wrong, check this before anything else.

### Path A — Calibre → KFX → USB (the default assumption)

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

### Path B — Send to Kindle

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
Sefaria API                 (Phase 2; Phase 1 uses the captured fixtures)
      ↓
providers/                  whole books in, never single verses
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
| `config/default.yaml` | fonts, typography scales, layout, sources — every tunable |
| `config/commentators.yaml` | Hebrew label, slug and Sefaria prefix per commentator |
| `tests/fixtures/` | real Sefaria data, captured once by `scripts/capture_fixtures.py` |
| `fonts/` | only fonts whose license has been read and recorded |
| `docs/` | notes that outlive a session |

Reading order for anyone picking this up: `CLAUDE.md` (how to work) → `PROGRESS.md` (where
we are) → `SPEC.md` and `SPEC_DATA_SOURCE.md` (what to build).

---

## Content and licensing

Texts come from Sefaria under the versions named in `config/default.yaml`, and the built
EPUB reproduces those names and licenses on its מקורות page. The Phase 1 fixtures hold:

| | Version | License |
|---|---|---|
| Tanakh | *Miqra according to the Masorah* | CC BY-SA |
| Rashi | *Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929–1934* | Public Domain |

Both are provisional until decisions D5 and D6 in `PROGRESS.md`.

Two fonts are embedded, each with its license read and recorded in `fonts/README.md`:
**Taamey Frank CLM** for the biblical text (GPL-2.0 with the Culmus font-embedding
exception) and **Noto Rashi Hebrew** for the commentary (SIL OFL 1.1). The generator code
itself is MIT.

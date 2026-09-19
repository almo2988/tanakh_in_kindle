# CLAUDE.md — Tanakh + Rashi EPUB for Kindle

## What this is
A Python generator that builds a reflowable Hebrew EPUB 3 of the Tanakh with Rashi, to be read on a **Kindle Paperwhite (12th gen, 2024)**. Content comes from Sefaria only.

## Read first
1. `docs/DECISIONS.md` — what was decided (D1–D10) and what the device taught us. Read before changing fonts, CSS, versions or delivery.
2. `SPEC.md` — system spec: reading model, Kindle constraints, markup, typography, fonts, EPUB structure, tests.
3. `SPEC_DATA_SOURCE.md` — Sefaria provider: fetching, caching, version selection, markup rules, licensing.
4. `docs/MARKUP_RULES.md` and `docs/VERSION_SELECTION.md` — the markup rules table and the source versions.

Where the device disagrees with the spec, the device wins (SPEC §0); `docs/DECISIONS.md` records each such case.

## Non-negotiables
1. **The Kindle Paperwhite is the target.** When anything conflicts, choose what works on the device.
2. Reading content is **Hebrew only** — no English in anything the reader sees.
3. **No scraping** of sefaria.org HTML. API and Sefaria-Export only.
4. **Never alter the Hebrew text**: NFC only, no stripping ניקוד or טעמים, no respelling.
5. **No JavaScript, no viewport tricks, no px-based layout.** Only conservative EPUB CSS (SPEC §26).
6. **Unknown Sefaria markup fails the build** — never silently strip a tag.
7. **Fetch whole books, never single verses.**
8. **One XHTML file per chapter**, TOC depth = 2 (book → chapter).
9. Do not embed a font whose license has not been checked and recorded.

## Working rules
- **Anything that changes what the reader sees needs a device test** on the Paperwhite before it is called done. Claude prepares the build and a short checklist; the human tests and decides. Kindle Previewer and EPUBCheck passing is necessary, not sufficient.
- Font, version and layout choices are the human's. Record each new decision in `docs/DECISIONS.md` *and* in the config file it belongs to.
- New Sefaria markup: run `inventory-markup`, add a rule to `processing/markup.py` and a row to `docs/MARKUP_RULES.md`, with a test using the real string.

## Commands
```
uv sync                                    # or: pip install -e ".[dev]"
python -m tanakh_epub fetch                                   # all 39 books + Rashi into data/cache/
python -m tanakh_epub inventory-markup                        # must report 0 unknown patterns
python -m tanakh_epub validate
python -m tanakh_epub build                                   # → output/Tanakh_with_Rashi.epub
python -m tanakh_epub build --chapter Genesis 1              # offline, from the test fixture
python -m tanakh_epub check output/Tanakh_with_Rashi.epub     # EPUBCheck (+ Kindle Previewer if installed)
python -m tanakh_epub experiment-layout --chapter Genesis 1   # one EPUB per layout profile (docs/LAYOUT_EXPERIMENT.md)
pytest                                     # network tests skipped unless RUN_NETWORK_TESTS=1
ruff check . && ruff format .
```

## Conventions
- Python 3.12+, `uv`, `pytest`, `ruff`, type hints everywhere, frozen dataclasses for the model.
- English identifiers and references internally; Hebrew only in rendered output.
- Book names/slugs come from `config/books.yaml` — never hard-code them.
- `data/cache/`, `data/processed/`, `output/` are git-ignored. Only redistributable fonts go in `fonts/`.
- Small hand-rolled EPUB writer (zipfile + Jinja2) unless `ebooklib` output passes EPUBCheck and Kindle Previewer unmodified (decision D8).
- Hebrew numerals use real geresh (U+05F3) and gershayim (U+05F4).

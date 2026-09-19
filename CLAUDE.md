# CLAUDE.md — Tanakh + Rashi EPUB for Kindle

## What this is
A Python generator that builds a reflowable Hebrew EPUB 3 of the Tanakh with Rashi, to be read on a **Kindle Paperwhite (12th gen, 2024)**. Content comes from Sefaria only.

## Read first, every session
1. `PROGRESS.md` — current phase, what is done, what is next, what is blocked. **Read first, update last.**
2. `SPEC.md` — system spec: reading model, Kindle constraints, markup, typography, fonts, EPUB structure, tests.
3. `SPEC_DATA_SOURCE.md` — Sefaria provider: fetching, caching, version selection, markup rules, licensing.

`CLAUDE.md` says how to work. `PROGRESS.md` says where we are. The specs say what to build. Do not duplicate state from `PROGRESS.md` into this file.

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

## Working in phases
The work is split into phases in `PROGRESS.md` (Phase 1 POC scaffold → 2 Sefaria provider → 3 full Tanakh → 4 device hardening). Rules:

- **Start of session:** read `PROGRESS.md` → "Current state" → work on the current phase only, starting from "Next action".
- **During:** tick tasks and exit criteria as they are met; record any decision in the Decisions table *and* in the config file it belongs to, the moment it is made.
- **End of session:** update "Current state" (status, blocked on, next action), add a row to the Session log, list anything the human needs to do or decide.
- **Never start the next phase** until every exit criterion of the current one is ticked and the human has ticked the human gate. Human gates are device tests and font/version choices — Claude prepares candidates and instructions; the human executes and decides.
- Items marked **(human)** in `PROGRESS.md` are not for Claude Code to tick.

## Commands
```
uv sync                                    # or: pip install -e ".[dev]"
python -m tanakh_epub fetch --book Genesis
python -m tanakh_epub inventory-markup
python -m tanakh_epub validate
python -m tanakh_epub build --chapter Genesis 1 --output output/Genesis_Chapter_1.epub
python -m tanakh_epub check output/Genesis_Chapter_1.epub     # EPUBCheck (+ Kindle Previewer if installed)
python -m tanakh_epub experiment-layout --chapter Genesis 1   # 4 layout variants, same content (docs/LAYOUT_EXPERIMENT.md)
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

## Open decisions
Tracked in `PROGRESS.md` → Decisions (D1–D8). Not duplicated here.

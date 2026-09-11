# PROGRESS.md — Phase Plan and Current State

**This file is the single source of truth for where the project stands.** `CLAUDE.md` says *how* to work; this file says *what is done, what is next, and what is blocked*. Claude Code reads it at the start of every session and updates it at the end.

---

## Current state

| | |
|---|---|
| **Current phase** | 1 — POC scaffold |
| **Status** | not started |
| **Blocked on** | nothing |
| **Last session** | — |
| **Next action** | Phase 1, task 1.1: create repo layout and `pyproject.toml` |

---

## How to use this file

- Work only on the **current phase**. Do not start the next phase until every exit criterion is ticked **and** the human has ticked the human gate.
- Tick tasks and exit criteria as they are completed. Add a session-log line at the end of every session and update "Current state".
- Record a decision in the **Decisions** table the moment it is made (and in the config file it belongs to).
- If a task turns out wrong or unnecessary, ~~strike it~~ and explain in the log — never silently delete.
- Items marked **(human)** are done by the human, not by Claude Code.

---

## Phase 1 — POC scaffold (offline, fixture-based)

**Goal:** `Genesis_Chapter_1.epub` (בראשית א׳:א׳–י׳ with רש״י) built from checked-in fixtures, valid, and on the Paperwhite. No Sefaria network code yet beyond capturing the fixtures.

**Tasks**
- [ ] 1.1 Repo layout per `SPEC.md` §32; `pyproject.toml` (uv, pytest, ruff); `.gitignore` for `data/`, `output/`
- [ ] 1.2 `config/default.yaml`, `config/books.yaml` (all 39 books, `SPEC.md` §9), `config/commentators.yaml`
- [ ] 1.3 `models.py` — `Verse`, `CommentaryEntry`, `StudyUnit` (`SPEC.md` §19)
- [ ] 1.4 `hebrew_numbers.py` + tests (real geresh/gershayim; 15/16 rule; 115, 316)
- [ ] 1.5 `books.py` — load `books.yaml`, slug/title lookups + slug tests
- [ ] 1.6 Fixtures: `tests/fixtures/genesis_1.json`, `tests/fixtures/rashi_genesis_1.json` — captured once from the Sefaria API (one request each, command recorded in the fixture header), markup left untouched
- [ ] 1.7 `providers/local.py` — reads fixtures / processed JSON
- [ ] 1.8 `processing/markup.py` — minimal rules covering only patterns present in the fixtures; **fail loudly** on anything else (full rules table in Phase 2)
- [ ] 1.9 `processing/study_units.py`
- [ ] 1.10 Jinja2 templates: `chapter.xhtml`, `nav.xhtml`, `toc.ncx`, `content.opf`, `container.xml`, `sources.xhtml` (stub)
- [ ] 1.11 `rendering/html_renderer.py` — one file per chapter, stable ids, `keep-together` wrapper, book heading on first chapter
- [ ] 1.12 `main.css` with typography scales from config and both `@font-face` declarations
- [ ] 1.13 Fonts: biblical candidate(s) in `fonts/` with license files; Rashi placeholder (square) until D3 is decided
- [ ] 1.14 `epub/builder.py`, `epub/navigation.py` (nav + NCX, depth 2), `epub/metadata.py` (`page-progression-direction="rtl"`)
- [ ] 1.15 CLI: `build --chapter Genesis 1 --output …`, `check` (EPUBCheck wrapper; Kindle Previewer if present; clear skip message otherwise)
- [ ] 1.16 `README.md`: select **Publisher Font** on Kindle; Path A (Calibre KFX + USB) and Path B (Send to Kindle) steps
- [ ] 1.17 Tests: numerals, slugs, RTL attributes, nav/NCX completeness and depth, commentary order, no empty commentary block, fonts in manifest, EPUBCheck

**Exit criteria**
- [ ] `python -m tanakh_epub build --chapter Genesis 1` produces `output/Genesis_Chapter_1.epub`
- [ ] EPUBCheck: 0 errors (warnings listed in the log with a reason)
- [ ] Kindle Previewer conversion: 0 errors — or "not installed" noted in the log
- [ ] `pytest` green, `ruff` clean

**Human gate (human)**
- [ ] Path A: converted with Calibre KFX plugin, sideloaded, checklist below filled
- [ ] Path B: sent via Send to Kindle, checklist below filled
- [ ] Decisions D1–D4 recorded

**Device results — Phase 1** (✓ / ✗ / note)

| Check (`SPEC.md` §3.3) | Path A (Calibre KFX) | Path B (Send to Kindle) |
|---|---|---|
| Opens; cover in library | | |
| Biblical font applied under Publisher Font | | |
| ניקוד + טעמים stacked correctly (א׳:א׳) | | |
| Rashi font applied / legible at default size | | |
| Page turns right-to-left | | |
| Verse numbers, geresh/gershayim, parentheses correct | | |
| Font size change scales everything proportionally | | |
| "Go to" shows book → chapter; links land correctly | | |
| No empty commentary blocks | | |

**Status:** not started
**Notes:**

---

## Phase 2 — Sefaria provider

**Goal:** Real data. Whole-book fetching with cache, explicit versions, inventoried markup rules, validation report. Full Genesis builds cleanly.

**Tasks**
- [ ] 2.1 `providers/sefaria.py` — `list_versions`, `get_book_text`, `get_book_commentary` via API; Sefaria-Export raw-file path for bulk; polite User-Agent, delay, backoff
- [ ] 2.2 Cache with metadata (`fetched_at`, `source`, `version_title`, `license`); version mismatch = cache miss
- [ ] 2.3 CLI `fetch` with `--book`, `--refresh`, `--refresh-all`
- [ ] 2.4 `docs/VERSION_SELECTION.md` — candidate Hebrew Tanakh and Rashi versions with license, טעמים presence, notes → for D5/D6
- [ ] 2.5 CLI `inventory-markup` — tag/attribute/class counts with one example ref each → `docs/MARKUP_RULES.md`
- [ ] 2.6 `processing/markup.py` — full rules table (`SPEC_DATA_SOURCE.md` §9), fail-loud on unknown; internal-markup-only assertion; tests per pattern
- [ ] 2.7 `processing/normalize.py` — NFC + lossless round-trip test on the chosen version
- [ ] 2.8 `processing/validation.py` + CLI `validate` report (`SPEC_DATA_SOURCE.md` §18); expected counts from the Sefaria index shape
- [ ] 2.9 Network tests (`@pytest.mark.network`, skipped unless `RUN_NETWORK_TESTS=1`)
- [ ] 2.10 Switch `build` to the cache-backed provider; `local.py` stays for fixtures

**Exit criteria**
- [ ] `fetch --book Genesis` fills cache for the chosen Tanakh + Rashi versions
- [ ] `inventory-markup`: 0 unknown patterns for Genesis and Rashi on Genesis
- [ ] `validate`: clean for Genesis
- [ ] `build --book Genesis`: EPUBCheck clean; 50 chapter files; none over 300 KB
- [ ] `pytest` green (network tests pass when enabled)

**Human gate (human)**
- [ ] D5 Tanakh version and D6 Rashi version chosen from `docs/VERSION_SELECTION.md`, recorded in config + Decisions
- [ ] Full Genesis on the Paperwhite via the frozen delivery path — quick check of a long-Rashi verse (א׳:א׳), a verse without Rashi, and chapter navigation

**Status:** not started
**Notes:**

---

## Phase 3 — Full Tanakh build

**Goal:** `Tanakh_with_Rashi.epub` — all 39 books, valid, complete, attributed.

**Tasks**
- [ ] 3.1 `fetch` all 39 books and every available Rashi index; log books without Rashi
- [ ] 3.2 `inventory-markup` over the full dataset; extend rules until 0 unknown
- [ ] 3.3 Chunking size guard (`layout.max_file_kb`) + split-at-study-unit fallback
- [ ] 3.4 `layout.page_break_before_book`
- [ ] 3.5 `epub/cover.py` — generated black-and-white cover, `properties="cover-image"`
- [ ] 3.6 `epub/manifest.py` — `build_manifest.json` (output + embedded), `SOURCES_AND_LICENSES.md`
- [ ] 3.7 `sources.xhtml` (מקורות) — full Hebrew attribution: versions, licenses, fonts, build date
- [ ] 3.8 Landmarks nav; stable `dc:identifier` (`--new-identifier` flag)
- [ ] 3.9 Optional `include_sections` as flat entries (default off)
- [ ] 3.10 Tests: chunking, manifest, sources page present, full-nav completeness

**Exit criteria**
- [ ] Full build passes EPUBCheck (0 errors) and Kindle Previewer (0 errors)
- [ ] Validation report: all books / chapters / verses present; 0 empty verses; 0 unknown markup; books-without-Rashi listed
- [ ] No chapter file over 300 KB
- [ ] Full test suite green

**Human gate (human)**
- [ ] Full book on the Paperwhite; checklist below filled
- [ ] Spot checks: תהלים (150 chapters), ישעיהו, שמואל א׳, דברי הימים ב׳, one book without Rashi

**Device results — Phase 3** (✓ / ✗ / note)

| Check | Result |
|---|---|
| Opens; cover in library; file size acceptable | |
| Biblical font under Publisher Font, all spot-checked books | |
| ניקוד + טעמים correct in spot-checked books | |
| Rashi legible; long entries flow across pages sensibly | |
| Page turns RTL throughout | |
| "Go to": all books listed; chapters under each; links correct | |
| New book starts on a new page | |
| Books without Rashi render verses only | |
| מקורות page renders in Hebrew | |
| Font scaling proportional at smallest and largest sizes | |

**Status:** not started
**Notes:**

---

## Phase 4 — Device hardening

**Goal:** Everything the Paperwhite revealed is fixed, with regression tests. Runs as short sessions until the checklist is fully green.

**Issues** (add one line per finding; tick when fixed + tested)
- [ ] _(none yet)_

**Exit criteria**
- [ ] Phase 3 device checklist fully ✓ on a rebuilt full EPUB
- [ ] All decisions D1–D8 recorded
- [ ] README complete for a second reader to reproduce the build and sideload

**Status:** not started
**Notes:**

---

## Later (not scheduled)

- Additional commentators (Ramban, Ibn Ezra, Sforno, Steinsaltz) via `config/commentators.yaml`
- Kobo-tuned config (`config/kobo.yaml`)
- Section landing pages (תורה / נביאים / כתובים)

---

## Decisions

| ID | Decision | Answer | Date | Recorded in |
|---|---|---|---|---|
| D1 | Delivery path (`calibre-kfx` / `send-to-kindle`) | — | | `config/default.yaml` `target.delivery`, README |
| D2 | Biblical font (Taamey Frank CLM / Taamey David CLM / Ezra SIL) | — | | `fonts.biblical`, `sources.xhtml` |
| D3 | Rashi-script font + verified license, or `rashi_script: false` | — | | `fonts.rashi`, `typography.rashi_script` |
| D4 | `rashi_scale` after legibility check | 0.85 (default, unverified) | | `typography.rashi_scale` |
| D5 | Sefaria Tanakh version (must include טעמים) | — | | `sources.tanakh`, `docs/VERSION_SELECTION.md` |
| D6 | Sefaria Rashi version | — | | `sources.commentaries.Rashi` |
| D7 | Sefaria index titles in `books.yaml` verified via API | — | | `config/books.yaml` |
| D8 | EPUB writer: hand-rolled (zipfile + Jinja2) vs `ebooklib` | — | | `epub/builder.py` docstring |

---

## Session log

| Date | Phase | Done | Next | Open questions for the human |
|---|---|---|---|---|
| | | | | |

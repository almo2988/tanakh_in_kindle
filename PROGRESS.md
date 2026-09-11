# PROGRESS.md — Phase Plan and Current State

**This file is the single source of truth for where the project stands.** `CLAUDE.md` says *how* to work; this file says *what is done, what is next, and what is blocked*. Claude Code reads it at the start of every session and updates it at the end.

---

## Current state

| | |
|---|---|
| **Current phase** | 1 — POC scaffold |
| **Status** | code complete; all Claude-side tasks and exit criteria met. Waiting on the **human gate**. |
| **Blocked on** | the human: put `output/Genesis_Chapter_1.epub` on the Paperwhite through **both** delivery paths, fill the device table below, and decide D1–D4. Nothing further can be built until then. |
| **Last session** | 2026-09-11 |
| **Next action** | **(human)** build with `python -m tanakh_epub build --chapter Genesis 1 --max-verse 10 --output output/Genesis_Chapter_1.epub`, then follow README → "Getting the book onto the Kindle" for Path A and Path B. |

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
- [x] 1.1 Repo layout per `SPEC.md` §32; `pyproject.toml` (uv, pytest, ruff); `.gitignore` for `data/`, `output/`
- [x] 1.2 `config/default.yaml`, `config/books.yaml` (all 39 books, `SPEC.md` §9), `config/commentators.yaml`
- [x] 1.3 `models.py` — `Verse`, `CommentaryEntry`, `StudyUnit` (`SPEC.md` §19)
- [x] 1.4 `hebrew_numbers.py` + tests (real geresh/gershayim; 15/16 rule; 115, 316)
- [x] 1.5 `books.py` — load `books.yaml`, slug/title lookups + slug tests
- [x] 1.6 Fixtures: `tests/fixtures/genesis_1.json`, `tests/fixtures/rashi_genesis_1.json` — captured once from the Sefaria API (one request each, command recorded in the fixture header), markup left untouched
- [x] 1.7 `providers/local.py` — reads fixtures / processed JSON
- [x] 1.8 `processing/markup.py` — minimal rules covering only patterns present in the fixtures; **fail loudly** on anything else (full rules table in Phase 2)
- [x] 1.9 `processing/study_units.py`
- [x] 1.10 Jinja2 templates: `chapter.xhtml`, `nav.xhtml`, `toc.ncx`, `content.opf`, `container.xml`, `sources.xhtml` (stub)
- [x] 1.11 `rendering/html_renderer.py` — one file per chapter, stable ids, `keep-together` wrapper, book heading on first chapter
- [x] 1.12 `main.css` with typography scales from config and both `@font-face` declarations
- [x] 1.13 Fonts: biblical candidate(s) in `fonts/` with license files; Rashi placeholder (square) until D3 is decided
- [x] 1.14 `epub/builder.py`, `epub/navigation.py` (nav + NCX, depth 2), `epub/metadata.py` (`page-progression-direction="rtl"`)
- [x] 1.15 CLI: `build --chapter Genesis 1 --output …`, `check` (EPUBCheck wrapper; Kindle Previewer if present; clear skip message otherwise)
- [x] 1.16 `README.md`: select **Publisher Font** on Kindle; Path A (Calibre KFX + USB) and Path B (Send to Kindle) steps
- [x] 1.17 Tests: numerals, slugs, RTL attributes, nav/NCX completeness and depth, commentary order, no empty commentary block, fonts in manifest, EPUBCheck

**Exit criteria**
- [x] `python -m tanakh_epub build --chapter Genesis 1` produces `output/Genesis_Chapter_1.epub`
- [x] EPUBCheck: **0 errors, 0 warnings** (EPUBCheck 5.2.1)
- [x] Kindle Previewer conversion: **not installed** — it is macOS/Windows only and this session ran on Linux. `check` reports it as SKIPPED, never as a pass. Kindle-specific rendering is therefore unverified; the device test is the human gate below.
- [x] `pytest` green (150 passed, 1 skipped — the Kindle Previewer test), `ruff check` and `ruff format --check` clean

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

**Status:** code complete — awaiting the human gate.

**Notes:**

*Four things the human should know before testing on the device.*

1. **`direction` was removed from the CSS.** EPUB 3 forbids `direction` and `unicode-bidi`
   in a style sheet and EPUBCheck rejects them (CSS-001), so `SPEC.md` §17's literal
   `body { direction: rtl }` and its presence in §26's allowed list cannot both hold with
   "EPUBCheck: 0 errors". Direction now comes from `dir="rtl"` on `<html>` and `<body>` in
   every document, plus `page-progression-direction="rtl"` in the OPF. The rendered result
   is the same and the attribute is the more robust of the two — but **RTL page turns still
   need confirming on the device**, which is already on the checklist. Worth a line in
   `SPEC.md` §17/§26 if the device test passes.

2. **NFC reorders the Hebrew combining marks.** Sefaria stores them in *typing* order
   (dagesh before vowel); NFC sorts them by canonical combining class. Nothing is lost —
   same characters, same count, canonically equivalent text, and there is a test pinning
   that. But Taamey Frank's own README says mark *positioning* depends on typing order, so
   if ניקוד and טעמים stack wrongly in בראשית א׳:א׳ on the device, **this is the first thing
   to suspect**, not the font choice. `SPEC.md` §7 mandates NFC, so it was not second-guessed
   here.

3. **The Rashi font is a square placeholder, not Rashi script** (Hadasim CLM), so
   `typography.rashi_script` is `false`. D3 is still open. The commentary is still clearly
   separated — divider, smaller size, bold dibur hamatchil — so the legibility question for
   D4 can be answered from this build; the script question cannot.

4. **`tools/` and `.venv/` are git-ignored.** `scripts/epubcheck.sh` downloads EPUBCheck
   into `tools/` on first use (needs Java). Kindle Previewer cannot be scripted in.

*What the POC actually contains:* בראשית א׳:א׳–י׳, 10 verses, 17 Rashi entries across 9
verses, and א׳:ג׳ deliberately has no Rashi — that is the "no empty commentary block" case
on the checklist. One chapter file of 18 KB — comfortably under the 300 KB guideline — in a
70 KB EPUB that is mostly the two embedded fonts (153 KB before compression).

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
| D1 | Delivery path (`calibre-kfx` / `send-to-kindle`) | **open (human)** — `calibre-kfx` is configured as SPEC §3.1's default assumption; both paths must be tested before it is frozen | | `config/default.yaml` `target.delivery`, README |
| D2 | Biblical font (Taamey Frank CLM / Taamey David CLM / Ezra SIL) | **candidate prepared (human decides)** — Taamey Frank CLM Medium 0.110 is embedded and built. It carries the Hancock/Hudson Biblical Hebrew OpenType layout logic, which is what positions ניקוד and טעמים. Whether it stacks correctly **on the Paperwhite** is the open question. | | `fonts.biblical`, `fonts/README.md`, `sources.xhtml` |
| D3 | Rashi-script font + verified license, or `rashi_script: false` | **open (human)** — no Rashi-script font with a verified license was found, so `rashi_script: false` and Hadasim CLM Regular 0.140 stands in as the configured second square font (SPEC §15.2). Nothing is blocked by this. | | `fonts.rashi`, `typography.rashi_script` |
| D4 | `rashi_scale` after legibility check | 0.85 (default, **unverified on device**) — answerable from this POC even with the placeholder font | | `typography.rashi_scale` |
| D5 | Sefaria Tanakh version (must include טעמים) | **provisional** — *Miqra according to the Masorah* (CC BY-SA), which the fixtures were captured from. Phase 2 compares it against *Tanach with Ta'amei Hamikra* (Public Domain) in `docs/VERSION_SELECTION.md`. | 2026-09-11 | `sources.tanakh`, `tests/fixtures/genesis_1.json` |
| D6 | Sefaria Rashi version | **provisional** — *Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934* (Public Domain), Sefaria's primary Hebrew Rashi | 2026-09-11 | `sources.commentaries.Rashi`, `tests/fixtures/rashi_genesis_1.json` |
| D7 | Sefaria index titles in `books.yaml` verified via API | **partial** — `Genesis` and `Rashi on Genesis` confirmed against the live API during fixture capture; the other 38 are still from SPEC §9 and are verified in Phase 2 | 2026-09-11 | `config/books.yaml` |
| D8 | EPUB writer: hand-rolled (zipfile + Jinja2) vs `ebooklib` | **hand-rolled** — SPEC §32 admits `ebooklib` only if its output passes EPUBCheck *and* Kindle Previewer unmodified. Every file that matters here (OPF spine with `page-progression-direction`, the NCX kept beside the nav document, exact font media types) is one Kindle quirk away from needing a hand edit, and `zipfile` gives that control in ~100 lines. Passing EPUBCheck with 0 errors/0 warnings. | 2026-09-11 | `epub/builder.py` docstring |

---

## Session log

| Date | Phase | Done | Next | Open questions for the human |
|---|---|---|---|---|
| 2026-09-11 | 1 | All 17 Phase 1 tasks and all four Claude-side exit criteria. `build --chapter Genesis 1 --max-verse 10` produces a 70 KB EPUB that EPUBCheck 5.2.1 passes with 0 errors and 0 warnings; 150 tests pass, `ruff` clean. Fixtures captured from the live Sefaria API in two whole-book requests (`scripts/capture_fixtures.py`). Fonts embedded with licenses verified from their own name tables. D8 decided; D5–D7 recorded as provisional. | **(human)** the Phase 1 device gate: both delivery paths onto the Paperwhite, fill the device table, decide D1–D4. Phase 2 does not start until every box above is ticked. | 1. D1: which delivery path survives — test A **and** B. 2. D2: do ניקוד + טעמים stack correctly in בראשית א׳:א׳ under Publisher Font? If not, read Phase 1 note 2 (NFC reordering) before blaming the font. 3. D3: accept `rashi_script: false` with a square font, or should a Rashi-script font with a checkable license be hunted down? 4. D4: is 0.85em legible at the Paperwhite's default size? 5. Should `SPEC.md` §17/§26 be amended to say direction comes from `dir="rtl"`, not CSS (Phase 1 note 1)? |

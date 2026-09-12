# PROGRESS.md — Phase Plan and Current State

**This file is the single source of truth for where the project stands.** `CLAUDE.md` says *how* to work; this file says *what is done, what is next, and what is blocked*. Claude Code reads it at the start of every session and updates it at the end.

---

## Current state

| | |
|---|---|
| **Current phase** | 1 — POC scaffold |
| **Status** | Phase 1 merged (PR #1). **Phase 1b: page layout settled.** Collapsible commentary abandoned — `<details>` was rejected by the device and the popup route was dropped before testing. Replaced by a **two-stream מקראות גדולות layout**: a run of verses, then the Rashi on that whole run. |
| **Blocked on** | the device: does the two-stream layout read well on the Paperwhite, and is the block size right? |
| **Last session** | 2026-09-12 |
| **Next action** | **(human)** sideload `output/Genesis_Chapter_1.epub` via Calibre KFX. Is a block of 3–5 verses followed by its Rashi the right rhythm, or should `commentary.block_chars` go up or down? |

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

Round 1, 2026-09-11: the human reported "it renders okay on the kindle" and one defect —
the commentary was in a square Hebrew face, not Rashi script. The delivery path used was
not recorded, so no per-path cell is claimed below; the ✗ is the one thing explicitly
reported.

| Check (`SPEC.md` §3.3) | Path A (Calibre KFX) | Path B (Send to Kindle) |
|---|---|---|
| Opens; cover in library | | |
| Biblical font applied under Publisher Font | | |
| ניקוד + טעמים stacked correctly (א׳:א׳) | | |
| Rashi font applied / legible at default size | ✗ round 1 — square, not Rashi script. Fixed (D3); **needs re-test** | |
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

3. ~~**The Rashi font is a square placeholder, not Rashi script** (Hadasim CLM).~~
   **Fixed 2026-09-11 after round 1 of the device test.** The commentary is now set in
   **Noto Rashi Hebrew** 1.007 (SIL OFL, static TTF, `fsType 0`), `rashi_script: true`, and
   the Hadasim placeholder is gone from the repo. `rashi_scale` went 0.85 → 0.9, because
   Rashi script carries less weight than a square face at the same nominal em. D4 is still
   the human's to confirm on the screen.

4. **`tools/` and `.venv/` are git-ignored.** `scripts/epubcheck.sh` downloads EPUBCheck
   into `tools/` on first use (needs Java). Kindle Previewer cannot be scripted in.

**The embedded commentary font — found, rounds 2–7 (2026-09-11).**

**Cause: a `font-family` stack naming two embedded families.** The Paperwhite honours
`"Noto Rashi Hebrew", serif` and does not honour
`"Noto Rashi Hebrew", "Taamey Frank CLM", serif`. `.commentary-text` was the only rule in
the stylesheet naming two embedded families, and the only rule that failed; every other
rule names one plus a generic and worked throughout. That single fact fits every
observation from every round, including the ones that looked contradictory at the time.

**The fix.** `render_css` now emits one embedded family per stack, always followed by a
generic. Two tests hold it there: no stack may name two embedded families, and every stack
must end in a generic.

Nothing is lost by dropping the middle entry. It was there so a character missing from the
Rashi font would fall back to the biblical one, and `tests/test_fonts.py` already proves no
such character exists — it checks the embedded font's cmap against the actual text on every
run, which is what makes the intermediate fallback redundant rather than merely absent.

**This contradicts `SPEC.md` §16**, which writes the stack as
`"Rashi", "BiblicalHebrew", serif`. SPEC §0 settles it in the device's favour, and §16
should be amended to say: one embedded family per stack, then a generic.

*What the hunt cost, and why.* Six rounds, three of them spent on fixes that were free but
not the cause — the manifest media type, the `format()` hint, the family names. All three
are defensible and stay. Two things went wrong in the method and are worth not repeating:

1. **Round 4's diagnostic was reported as proving more than it did.** Its `<body>` font was
   the Rashi font, so every line inherited a pass regardless of its own rule. A diagnostic
   whose default already satisfies the thing under test cannot fail informatively.
2. **The CSS bisect varied everything except the one line that mattered.** All six pages
   kept `.commentary-text` verbatim, which is exactly why all six looked identical — the
   result that read as "nothing helps" was really "the variable was never varied".

What finally worked was inverting the question — asking a rule that *did* work to do the
job, rather than asking the failing rule to stop failing — and reducing the report to one
yes/no per page. The earlier per-line formats asked more of a device test than anyone
should have to give, and that is where the flaw hid.

**Still open:** bold runs. `.verse-number` and `.dibur-hamatchil` ask for `font-weight:
bold` with only Regular faces embedded, which on Kindle can fall back for those runs. If
bold faces are ever added, note that Taamey Frank CLM's Bold variant has its **טעמים made
transparent** by design — harmless only as long as no vocalised biblical text is ever bold.

**Expandable commentary (D9) — unparked 2026-09-12, built, awaiting the device.** See the
Phase 1b section below. Of the three approaches researched while it was parked, the author
chose `<details>`/`<summary>`; the popup route stays on record there if this one fails on
the device.

*What the POC actually contains:* בראשית א׳:א׳–י׳, 10 verses, 17 Rashi entries across 9
verses, and א׳:ג׳ deliberately has no Rashi — that is the "no empty commentary block" case
on the checklist. One chapter file of 18 KB — comfortably under the 300 KB guideline — in a
70 KB EPUB that is mostly the two embedded fonts (153 KB before compression).

---

## Phase 1b — Page layout (D9)

**Goal:** the visual organisation of a printed תנ״ך עם רש״י / מקראות גדולות page — a run of
consecutive biblical verses, then the Rashi on that whole run — while staying a reflowable
EPUB with no fixed heights and no screen-size assumptions.

**How the design arrived here.** D9 began as "make Rashi expandable, like the Sefaria app"
and went through two rejected attempts before the author redirected it to layout:

1. **`<details>`/`<summary>`** — native HTML5, no JavaScript, correct in Apple Books.
   **The Kindle renders it permanently expanded**; the same build also lost its table of
   contents and its font-size control. Rejected on the device (2026-09-12).
2. **Popup (`epub:type="noteref"` + `<aside epub:type="footnote">`)** — Amazon's documented
   mechanism, built and validated offline, **never tested**: the author dropped the
   collapsible idea before it reached the device. The code was removed with `details`;
   both remain in git history if the idea returns.
3. **Two streams** — the current design, and not a workaround for the first two: it is how
   the printed page has always solved the same problem.

**The layout**

```
א׳ בְּרֵאשִׁית…  ב׳ וְהָאָרֶץ…  ג׳ וַיֹּאמֶר…  ד׳ וַיַּרְא…  ה׳ וַיִּקְרָא…
──────────────────── רש״י ────────────────────
בראשית. אמר רבי יצחק…  ברא. …  תהו ובהו. …  יום אחד. …
```

Each region is **one continuous paragraph**: verses are inline spans inside it, not a
container apiece, and so are the commentary entries. Neither stream is chopped up by the
structure of the other, which is what the author asked for and what the per-verse layout
could not give.

**The association lives in the data, not the grouping.** Every verse carries its id and
`data-ref="Genesis 1:2"`; every commentary segment carries its id and
`data-ref="Rashi on Genesis 1:2:5"`. Regrouping is presentation only — nothing downstream
has to infer which verse a passage explains from where it happens to sit on the page.

**Tasks**
- [x] 1b.1 `commentary.mode: blocks | interleaved`, default `blocks`; `interleaved` keeps the
      Phase 1 verse-by-verse layout
- [x] 1b.2 `commentary.block_chars` (default 420) — how much biblical text fills a block
- [x] 1b.3 Two-stream template: `.biblical-flow` and `.commentary-flow`, verses and entries as
      inline runs
- [x] 1b.4 `data-ref` on every verse and every commentary segment
- [x] 1b.5 CSS emitted only for the block layout, inside SPEC §26 — no height, no column, no
      `display`, no `vh`/`px`
- [x] 1b.6 `--commentary-mode` and `--block-chars` on `build`
- [x] 1b.7 `details` and `popup` removed
- [x] 1b.8 Entry ids from `BookInfo.slug` rather than a lower-cased Sefaria title (a latent
      bug: `I Samuel` gave `i-samuel` in ids against `samuel-1` in file names)
- [x] 1b.9 `tests/test_commentary_modes.py` — 22 tests on the layout, the canonical
      references, the block budget and the stylesheet

**Why a character budget rather than a verse count.** "As many consecutive verses as
naturally fit" has no exact answer in a reflowable document: the reader's screen and font
size decide what fits, and the generator can see neither. What it *can* hold constant is the
amount of text per block, which is what a printed page holds constant. A count would be
uneven across books — a verse of תהלים against one of אסתר — so the budget counts characters.
420 gives 3–5 verses in בראשית א׳, about a printed page. A block always takes at least one
verse.

**On "~50% / ~50%".** Not directly settable, and worth being honest about: it is a property
of the content, not of the block size. Both regions grow together as a block takes more
verses, so the ratio between them does not move. In בראשית א׳ the Rashi runs 3.1× the
biblical text by character count, set at 0.9em against 1.25em — about 0.52× the area per
character — which lands near **40% Tanakh / 60% Rashi**. Close to the target, and close to a
real מקראות גדולות page. Changing `block_chars` changes how often the page alternates, not
the proportion.

**This contradicts `SPEC.md` §2**, which requires commentary "immediately after the verse it
belongs to". The author has specified otherwise, so §2 wants amending: commentary follows a
*run* of verses, and the canonical association is carried by ids and `data-ref` rather than
by adjacency. §2's other prohibition still holds — a whole chapter followed by all its
commentary — and `block_chars` is what keeps a block well short of that. §13's
`keep-together` applies only to `interleaved` now.

**Exit criteria**
- [x] `build` produces a valid EPUB in both layouts; EPUBCheck 0 errors, 0 warnings
- [x] Two continuous streams; no verse-and-its-Rashi visual unit
- [x] Canonical references preserved on every verse and every segment
- [x] No `vh`, `px`, height, column or `display` anywhere in the stylesheet
- [x] Biblical text identical in both layouts; navigation identical
- [x] `pytest` green (185 passed), `ruff` clean
- [ ] **(human)** reads well on the Paperwhite; block size confirmed

**Human gate (human)**
- [ ] Sideloaded via Calibre KFX; the rhythm of verses-then-Rashi is right
- [ ] `block_chars` confirmed or adjusted
- [ ] D9 closed and `SPEC.md` §2 amended

**Device results — Phase 1b**

| Round | What was tested | Result |
|---|---|---|
| 1 (2026-09-12) | `<details>`, via Send to Kindle | ✗ renders permanently expanded; no table of contents; font very small and not adjustable. Correct in Apple Books. |
| 2 | two-stream layout, via Calibre KFX | pending |

*Two symptoms from round 1 were never attributed.* The missing TOC and the frozen font size
have no obvious connection to a disclosure element, and nothing in the generated stylesheet
explained them — its smallest size is 0.75em. Either one unsupported element derailed the
conversion, or it was **Send to Kindle**, which that round was the first use of in this
project (every earlier device test went through Kindle Previewer, and SPEC §3.1 warns that
Amazon's server-side converter decides what survives). The control that would separate them —
the same content sent the same way, without `<details>` — was not run before the layout
changed. **If round 2 goes through Calibre KFX and the TOC and font controls are fine, that
is evidence for Path B and D1 answers itself.**

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
| D3 | Rashi-script font + verified license, or `rashi_script: false` | **decided — Noto Rashi Hebrew Regular 1.007**, SIL OFL 1.1, `fsType 0`, static TTF. Genuine Rashi script. Covers every character in the Rashi fixture (asserted by `tests/test_fonts.py`). Round 1 on the device rejected the square placeholder, which is now removed from the repo. `rashi_script: true`. | 2026-09-11 | `fonts.rashi`, `typography.rashi_script`, `fonts/README.md` |
| D4 | `rashi_scale` after legibility check | 0.9 — raised from 0.85 with the font swap, since Rashi script reads lighter than a square face at the same em. **Still unverified on the device.** | 2026-09-11 | `typography.rashi_scale` |
| D5 | Sefaria Tanakh version (must include טעמים) | **provisional** — *Miqra according to the Masorah* (CC BY-SA), which the fixtures were captured from. Phase 2 compares it against *Tanach with Ta'amei Hamikra* (Public Domain) in `docs/VERSION_SELECTION.md`. | 2026-09-11 | `sources.tanakh`, `tests/fixtures/genesis_1.json` |
| D6 | Sefaria Rashi version | **provisional** — *Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934* (Public Domain), Sefaria's primary Hebrew Rashi | 2026-09-11 | `sources.commentaries.Rashi`, `tests/fixtures/rashi_genesis_1.json` |
| D7 | Sefaria index titles in `books.yaml` verified via API | **partial** — `Genesis` and `Rashi on Genesis` confirmed against the live API during fixture capture; the other 38 are still from SPEC §9 and are verified in Phase 2 | 2026-09-11 | `config/books.yaml` |
| D8 | EPUB writer: hand-rolled (zipfile + Jinja2) vs `ebooklib` | **hand-rolled** — SPEC §32 admits `ebooklib` only if its output passes EPUBCheck *and* Kindle Previewer unmodified. Every file that matters here (OPF spine with `page-progression-direction`, the NCX kept beside the nav document, exact font media types) is one Kindle quirk away from needing a hand edit, and `zipfile` gives that control in ~100 lines. Passing EPUBCheck with 0 errors/0 warnings. | 2026-09-11 | `epub/builder.py` docstring |
| D9 | How commentary sits on the page | **two-stream מקראות גדולות layout** — a run of consecutive verses, then the Rashi on that whole run (`commentary.mode: blocks`, `block_chars: 420`). Collapsible commentary abandoned: `<details>` rejected by the device, popup dropped before testing. Contradicts SPEC §2, which wants amending. | 2026-09-12 | `commentary.mode`, `chapter.xhtml.j2`, Phase 1b |

---

## Session log

| Date | Phase | Done | Next | Open questions for the human |
|---|---|---|---|---|
| 2026-09-12 (3) | 1b | Collapsible commentary abandoned and replaced by the layout the author specified: a run of consecutive verses, then the Rashi on that whole run, after a printed מקראות גדולות page. Each region is one continuous paragraph with verses and entries as inline runs, so neither stream is chopped up by the other. Every verse and every segment carries `data-ref` with its exact Sefaria reference, so the association lives in the data rather than in the visual grouping. Block size is a character budget (`block_chars`, default 420 → 3–5 verses) rather than a verse count, because verse lengths vary enormously between books. `details` and `popup` removed. EPUBCheck 0/0 in both layouts; 185 tests pass. | **(human)** sideload via Calibre KFX and judge the rhythm and the block size. | 1. Is 3–5 verses per block right, or should `block_chars` move? 2. SPEC §2 now contradicts the code — amend it? 3. If the TOC and font controls are fine via Calibre KFX, that points at Send to Kindle as the cause of round 1's other two symptoms. |
| 2026-09-12 (2) | 1b | `<details>` **fails on the Kindle**: renders permanently expanded, and the same build showed no table of contents and an unchangeable, very small font. Apple Books renders it exactly as intended, so the markup is right and the device is the constraint. Built `popup` as the successor — `<a epub:type="noteref">` into an `<aside epub:type="footnote">`, linked both ways with a Hebrew backlink, which is the mechanism Amazon documents and whose failure mode is the inline layout rather than a broken book. Ruled the stylesheet out of the font symptom: its smallest size is 0.75em and the details rules set none. EPUBCheck 0/0 on all three modes; 186 tests pass. | **(human)** Send to Kindle the popup POC **and** the inline control. | 1. Does the popup open on a tap? 2. Does the inline control also lose its TOC and font controls? If yes, those two symptoms are Send to Kindle (Path B), not `<details>`, and D1 answers itself. |
| 2026-09-12 | 1b | Unparked D9 and built the collapsible commentary the author specified: native `<details>`/`<summary>`, no JavaScript, collapsed by default, behind a new `commentary.mode` whose default stays `inline` so nothing that works can regress. `<summary>` takes over the divider's role and keeps its classes; `keep-together` is dropped when collapsed. CSS is emitted only in that mode and stays inside SPEC §26 — no `display`, no `list-style`. Also fixed a latent bug found on the way: entry ids were built by lower-casing the Sefaria title, so `I Samuel` gave `i-samuel` in ids against `samuel-1` in file names; they now come from `BookInfo.slug`. 17 new tests, including that the verse markup is byte-identical across modes and nav + NCX are unchanged. EPUBCheck 0/0 on both modes; 180 tests pass. | **(human)** Send to Kindle the details POC and report whether the רש״י bars start collapsed and open on a tap. | 1. Does `<details>` collapse on the Paperwhite? Amazon documents no support, so this is genuinely unknown. 2. If the fonts look wrong in this test, that is Send to Kindle (Path B), not `<details>` — sideload the same file via Calibre KFX to tell them apart. |
| 2026-09-11 (8) | 1 | **Cause found.** Round 7's two-paragraph diagnostic applies a second embedded font correctly on the device. Its rule names one embedded family plus a generic; `.commentary-text` named two — the only such rule in the stylesheet, and the only one that failed. `render_css` now emits one embedded family per stack followed by a generic, with two tests holding it there. Contradicts SPEC §16, which §0 settles in the device's favour. Rebuilt: EPUBCheck 0/0, 163 tests pass. | **(human)** confirm on the device that the commentary is now Rashi script; then D2/D3/D4 and the Phase 1 device table can all be closed. | 1. Is the commentary Rashi script now? 2. Amend SPEC §16 to "one embedded family per stack, then a generic"? 3. D9, the expandable commentary, is still parked — say when. |
| 2026-09-11 (7) | 1 | Round 6 produced the fact that reframes the whole hunt: Hebrew rendered in an embedded font while Bookerly was selected and "Publisher Font" was not offered. Bookerly has no Hebrew, so the device was falling back to an embedded font to draw the script at all — font choice for Hebrew looks like its fallback logic, not our CSS, which would explain every earlier result (Rashi appeared exactly when Rashi was the `body` font). Cut the diagnostic down from ten mechanisms to two pages of two paragraphs and one yes/no question each, because the per-line format is what let round 4's flaw hide. EPUBCheck 0/0; 161 tests pass. | **(human)** sideload `output/Font_Diagnostic.epub`; report per page whether the two paragraphs look the same or different. | Same on both pages means one font for all Hebrew: D3 becomes `rashi_script: false`, SPEC §15's two-font premise needs rewording, and the unused Rashi font should stop being embedded rather than sit there as a second fallback candidate. |
| 2026-09-11 (6) | 1 | Round 5: all six bisect pages square, the minimal stylesheet included — clearing comments, non-ASCII, `break-*`, borders and sheet size. One difference survives: every build that rendered Rashi set it on `body`; every build that failed sets it on a class. Recorded a correction — round 4's diagnostic put the Rashi font on `<body>`, so its lines could inherit a pass regardless of their class rules, and it did not prove what I reported it proved. Rewrote it: body is now the biblical font, ten mechanisms are tried against it, line 7 separates "class rules dropped" from "font-family overridden", and a second page sets Rashi on `body` to separate "only body works" from "one font per book". EPUBCheck 0/0; 161 tests pass. | **(human)** sideload the rewritten `output/Font_Diagnostic.epub` and report per line: Rashi or square, and big or not for 7 and 8. | 1. Line 7 — big and square, or big and cursive? 2. Page 2 — Rashi or square? 3. Do lines 0 and 9 look different from each other? If the answer is one font per book, D3 becomes `rashi_script: false` and SPEC §15 needs rewording. |
| 2026-09-11 (5) | 1 | Round 4 was decisive by elimination: `Font_Diagnostic.epub` renders both fonts correctly on the Paperwhite while `Genesis_Chapter_1.epub` does not — identical fonts, media types, `@font-face` names and delivery path, differing only in the stylesheet. So the fault is the generated CSS, and the fonts, manifest and pipeline are all cleared. Built `scripts/css_bisect.py`: six pages of the identical real study unit, differing only in which stylesheet they link, one suspect removed per page. Leading candidate is the 26 non-ASCII characters in the production stylesheet's comments — the working diagnostic has none, and the first such comment sits above the `@font-face` blocks. EPUBCheck 0/0; 161 tests pass. | **(human)** sideload `output/CSS_Bisect.epub` and report, per page, whether the commentary is Rashi script or square. | Which of the six pages render the commentary in Rashi script? Page 3 passing would be both the diagnosis and the fix. |
| 2026-09-11 (4) | 1 | Round 3 narrowed the font failure: "Publisher Font" is offered and selected, and the glyphs are still wrong — so the fonts reached the device and the renderer is not matching them. Ruled out both cheap explanations. Third free fix shipped: CSS family names now equal the fonts' own internal names rather than invented labels, enforced by a test. Built `scripts/font_diagnostic.py`, a one-page EPUB that applies the same font eight different ways so one device test names the mechanism instead of another guessing round. Both EPUBs EPUBCheck 0/0; 161 tests pass. | **(human)** sideload `output/Font_Diagnostic.epub` and report which numbered lines are not in Rashi script. | Which lines fail? That answers it — and tells us whether class-on-span styling survives KFX at all, which decides how the chapter template has to be written. |
| 2026-09-11 (3) | 1 | Round 2 of the device test: correct in Apple Books, wrong font on the Kindle — so the EPUB is sound and the loss is in conversion or delivery. Shipped the two Kindle-compatibility fixes that are free either way: font manifest entries now use `application/vnd.ms-opentype` rather than `font/ttf`, and `@font-face src` carries `format("truetype")`. EPUBCheck still 0/0; 161 tests pass. Cause not yet identified — see "Font not reaching the Kindle" under Phase 1 notes. | **(human)** the two free checks: is "Publisher Font" offered and selected, and which delivery path was used. If Kindle Previewer can be run locally, that settles it in one go. | 1. Does Aa → Font list "Publisher Font"? If it is not even offered, the fonts were dropped in conversion. 2. Calibre KFX or Send to Kindle? |
| 2026-09-11 (2) | 1 | Round 1 of the device test came back: it renders on the Paperwhite, but the commentary was square Hebrew, not Rashi script. Replaced the placeholder with **Noto Rashi Hebrew 1.007** (SIL OFL, static TTF, fsType 0), `rashi_script: true`, `rashi_scale` 0.85 → 0.9; removed Hadasim CLM. Added `tests/test_fonts.py`, which checks each embedded font's cmap against the actual fixture text so a missing glyph fails a test instead of appearing as a blank box on the device — and fixed a real bug it exposed: `rashi_script: false` was not actually falling back to the biblical font. EPUBCheck still 0/0; 160 tests pass. | **(human)** re-sideload and judge the Rashi script (D3/D4), then finish the device table and decide D1–D2. Then unpark D9. | 1. Is Noto Rashi Hebrew legible at 0.9em on the 7″ screen, or should `rashi_script` go back to `false`? 2. D9 is parked at your request — say when. 3. Which delivery path did you use in round 1? The device table has a column per path and I did not want to guess. |
| 2026-09-11 | 1 | All 17 Phase 1 tasks and all four Claude-side exit criteria. `build --chapter Genesis 1 --max-verse 10` produces a 70 KB EPUB that EPUBCheck 5.2.1 passes with 0 errors and 0 warnings; 150 tests pass, `ruff` clean. Fixtures captured from the live Sefaria API in two whole-book requests (`scripts/capture_fixtures.py`). Fonts embedded with licenses verified from their own name tables. D8 decided; D5–D7 recorded as provisional. | **(human)** the Phase 1 device gate: both delivery paths onto the Paperwhite, fill the device table, decide D1–D4. Phase 2 does not start until every box above is ticked. | 1. D1: which delivery path survives — test A **and** B. 2. D2: do ניקוד + טעמים stack correctly in בראשית א׳:א׳ under Publisher Font? If not, read Phase 1 note 2 (NFC reordering) before blaming the font. 3. D3: accept `rashi_script: false` with a square font, or should a Rashi-script font with a checkable license be hunted down? 4. D4: is 0.85em legible at the Paperwhite's default size? 5. Should `SPEC.md` §17/§26 be amended to say direction comes from `dir="rtl"`, not CSS (Phase 1 note 1)? |

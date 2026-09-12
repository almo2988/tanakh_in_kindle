# PROGRESS.md — Phase Plan and Current State

**This file is the single source of truth for where the project stands.** `CLAUDE.md` says *how* to work; this file says *what is done, what is next, and what is blocked*. Claude Code reads it at the start of every session and updates it at the end.

---

## Current state

| | |
|---|---|
| **Current phase** | 1 — POC scaffold |
| **Status** | Phase 1 merged (PR #1). **Phase 1b:** `<details>` **fails on the Kindle** — correct in Apple Books, does not collapse on the device. Popup mode (Amazon's documented mechanism) built as the successor; a control build is needed to attribute two other symptoms. |
| **Blocked on** | one device round: the popup POC, plus an inline control sent the same way. |
| **Last session** | 2026-09-12 |
| **Next action** | **(human)** Send to Kindle **both** `Genesis_Chapter_1_Popup.epub` and `Genesis_Chapter_1_Inline.epub`. Does the popup open on a tap? And does the control also lose its TOC and font controls? |

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

## Phase 1b — Collapsible commentary (D9)

**Goal:** Rashi collapsed by default so the biblical text runs continuously, opening on a
tap of רש״י — the reading experience the author asked for after round 1 on the device.

Native HTML5 `<details>`/`<summary>`, no JavaScript. Chosen by the author from the three
approaches researched while D9 was parked; the `epub:type="noteref"` popup remains the
fallback if this fails on the device (see the Phase 1 notes for that research).

**Tasks**
- [x] 1b.1 `commentary.mode: inline | details` in `config/default.yaml` and `Config`, validated
- [x] 1b.2 Chapter template branch: `<details class="commentary rashi">` with
      `<summary class="commentary-divider">רש״י</summary>`, no `open` attribute, `keep-together`
      dropped (nothing to hold when the commentary starts closed)
- [x] 1b.3 CSS emitted only in `details` mode, inside SPEC §26 — no `display`, no `list-style`;
      the disclosure marker is left to the user agent
- [x] 1b.4 `--commentary-mode` on `build`, so the POC needs no config edit
- [x] 1b.5 Entry ids now come from `BookInfo.slug` rather than a lower-cased Sefaria title
      (a latent bug: `I Samuel` gave `i-samuel` in ids and `samuel-1` in file names)
- [x] 1b.6 `tests/test_commentary_modes.py` — 23 tests, including that the verse markup is
      byte-identical across modes and that nav + NCX are unchanged
- [x] 1b.7 `popup` mode after `details` failed on the device: `<a epub:type="noteref">` in the
      verse into an `<aside epub:type="footnote">`, linked both ways, with a Hebrew backlink

**Exit criteria**
- [x] `build --commentary-mode details` produces a valid EPUB; EPUBCheck 0 errors, 0 warnings
- [x] Collapsed by default (no `open` attribute), Hebrew RTL, Rashi font and `rashi_scale` intact
- [x] Biblical text and navigation structure untouched — asserted, not assumed
- [x] `pytest` green (180 passed), `ruff` clean
- [ ] **(human)** works on the Paperwhite after Send to Kindle conversion

**Human gate (human)**
- [x] ~~Sent via Send to Kindle; the רש״י bars start **collapsed**~~ — ✗, `details` does not collapse
- [ ] `popup`: tapping רש״י opens the commentary as an overlay
- [ ] The inline control, sent the same way, establishes whether the missing TOC and frozen
      font size are Path B or were caused by `<details>`
- [ ] D9 recorded, and `commentary.mode` default set to whichever mode the device accepts

**Device results — Phase 1b** (✓ / ✗ / note)

| Check | Send to Kindle | Calibre KFX |
|---|---|---|
| Commentary starts collapsed | | |
| Tapping רש״י expands it | | |
| Tapping again collapses it | | |
| Rashi font still applied when open | | |
| Biblical text unchanged; ניקוד + טעמים intact | | |
| Verse without Rashi (א׳:ג׳) shows no bar | | |
| "Go to" still lists בראשית → פרק א׳ | | |

**Status:** `<details>` rejected by the device; `popup` built as its successor and awaiting test.

> **A two-stream מקראות גדולות layout was built on 2026-09-12 and rolled back the same day at
> the author's request** (`git revert` of 4942932 — the work is intact in history and restoring
> it is one `git revert` away). It replaced the verse-and-its-Rashi unit with a run of
> consecutive verses followed by the Rashi on that whole run, each region one continuous
> paragraph, with `data-ref` carrying the canonical Sefaria reference on every verse and
> segment so the association survived the regrouping. Block size was a character budget
> (`block_chars`, 420 → 3–5 verses) rather than a verse count. Recorded here so it is not
> rebuilt by accident, and because the two findings it produced still stand: the ~50/50 split
> the brief asked for is a property of the content rather than something block size can set
> (בראשית א׳ lands near 40/60), and the layout contradicted SPEC §2.

**Device results — Phase 1b, round 1 (`details`, via Send to Kindle, 2026-09-12)**

| Check | Send to Kindle | Calibre KFX |
|---|---|---|
| Commentary starts collapsed | ✗ renders permanently expanded | |
| Tapping רש״י expands it | ✗ n/a | |
| Table of contents in the "Go to" menu | ✗ missing | |
| Font size adjustable from the Aa menu | ✗ text very small, control does nothing | |

Apple Books renders it exactly as intended, so the markup is right and the Kindle is the
constraint — which is the answer SPEC §0 defers to. **`<details>` is not viable on the
target device.** The mode stays in the codebase because it is correct elsewhere and costs
nothing, but it will never be the default.

*Two of those symptoms are not yet attributable.* The missing TOC and the frozen font size
have nothing to do with `<details>` in principle, and nothing in the generated stylesheet
explains them — its smallest size is 0.75em and the `details`/`summary` rules set no size
at all. Two candidates, and they need separating before either is believed:

1. **One unsupported element derailed the conversion.** A converter that cannot place
   `<details>` may fall back to a degraded rendering path, losing the navigation document
   and the reflow controls along with the collapse. That would make all three symptoms one
   bug.
2. **It is Send to Kindle.** This is the first file ever delivered by Path B in this
   project — every previous device test went through Kindle Previewer. SPEC §3.1 warns that
   Amazon's server-side converter decides what survives, and a missing TOC and frozen font
   size are exactly the kind of thing it decides.

The control that separates them is one file: the **inline** build, sent the same way. If it
also has no TOC and no font control, the cause is Path B and D1 answers itself. If it is
fine, `<details>` poisoned the conversion.

*Next: `popup`.* Where `<details>` is undocumented on Kindle, `<a epub:type="noteref">` into
an `<aside epub:type="footnote">` is the mechanism Amazon documents and commercial Kindle
books use — the marker becomes a tap target and the aside opens as an overlay, so the reader
never leaves the page, which is what SPEC §2 requires. The links are bidirectional, without
which the popup may not appear at all. Readers with no popup support render the aside in
place, which is the `inline` layout — so unlike `<details>`, its failure mode is something
already known to work.

**Notes:**

*The risk, stated plainly, before the test.* `<details>` is native HTML5 and EPUBCheck passes it with 0/0,
and it works in Apple Books, Kobo and Thorium. **Amazon documents no support for it**, and
the community compatibility grids do not cover it, so the Kindle outcome is genuinely
unknown. The three plausible results: it collapses (what we want); it renders permanently
expanded, which degrades to exactly the current inline layout and loses nothing; or the
converter drops it. Only the device can say which.

*If fonts look wrong in this test, suspect the path, not the feature.* This POC goes via
**Send to Kindle**, which SPEC §3.1 warns can drop embedded fonts — the previous six rounds
of font debugging all went through Kindle Previewer instead. A font regression here is a
Path B symptom and says nothing about `<details>`. Build the same file with
`--commentary-mode details` and sideload it through Calibre KFX to separate the two.

*The default is unchanged.* `commentary.mode` stays `inline` until the device says
otherwise, so nothing that already works can regress while this is being decided.

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
| D9 | How commentary sits in the page: inline / tap-to-open popup / `<details>` | **`<details>` ruled out on the device** — correct in Apple Books, does not collapse on the Paperwhite, and the same build lost its TOC and font controls. `popup` (`epub:type="noteref"` + `<aside epub:type="footnote">`), the mechanism Amazon documents, is built and awaiting test. Default stays `inline` until one passes. | 2026-09-12 | `commentary.mode`, `chapter.xhtml.j2`, Phase 1b |

---

## Session log

| Date | Phase | Done | Next | Open questions for the human |
|---|---|---|---|---|
| 2026-09-12 (3) | 1b | Built the two-stream מקראות גדולות layout, then reverted it the same day at the author's request. `git revert` rather than a force-push, since the branch was already pushed and the work is worth keeping recoverable. The tree is back to exactly the state that was delivered with the popup and inline POCs; a note under Phase 1b records what the layout was and what it found, so it is neither rebuilt by accident nor silently lost. | **(human)** the device round that is still outstanding: the popup POC and the inline control, sent the same way. | Unchanged: does the popup open on a tap, and does the inline control also lose its TOC and font controls? |
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

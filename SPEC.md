# Tanakh + Rashi EPUB Generator — System Specification

**Version 2 — 2026-09-11.** Supersedes *Formal Specification: Responsive Hebrew Tanakh + Rashi EPUB Generator (v1)*.
Companion document: `SPEC_DATA_SOURCE.md` (Sefaria as the required content source). Read both before implementing.

---

## 0. Primary Target: Kindle Paperwhite (12th generation)

This is the single most important constraint in the project.

- The author owns a **Kindle Paperwhite, 12th gen (2024)**: 7″ E-Ink, 300 ppi, KFX-capable.
- Every design decision is resolved in favor of what works on **this device**.
- Kobo, PocketBook, Apple Books, Google Play Books and Calibre viewers are **secondary**: the EPUB must stay valid and readable there, but no Kindle compromise is made for them.
- "Works" means **verified on the physical device**, not in a desktop EPUB viewer.

Known Kindle behaviour that shapes this spec:

| Kindle behaviour | Consequence in this spec |
|---|---|
| Kindle does not read EPUB directly; it is converted to KFX (Send to Kindle, or Kindle Previewer / Calibre) | The delivery path is part of the build (§3) |
| Embedded fonts apply only when the reader selects **Publisher Font** in the Aa menu | Fonts must be embedded; README must tell the reader to select Publisher Font |
| The stock Kindle Hebrew font stacks ניקוד + טעמים poorly | Embedding a mark-aware biblical font is mandatory, not optional |
| `break-inside: avoid` is ignored | Study units **will** split across pages; design for it (§13, §27) |
| Amazon recommends ≤ ~300 KB per HTML file | One XHTML file per **chapter**, not per book (§11) |
| The "Go to" menu shows two nested TOC levels | Navigation is book → chapter; no deeper nesting (§10) |
| Page-turn direction reverses for books whose `dc:language` is `he` | Set language + `dir="rtl"`; verify page turns on device (§17) |

---

## 1. Project Overview

Build a Python-based system that generates a standards-compliant, reflowable **EPUB 3** containing the complete Hebrew Tanakh together with Rashi's commentary, designed to be read on a Kindle Paperwhite while remaining compatible with standard EPUB readers.

The book must be fully responsive to user-selected font sizes and screen dimensions.

The content language is **Hebrew only**. No English translations, transliterations, or English reference labels appear in the reading content.

---

## 2. Primary Reading Model

The EPUB uses a **verse–commentary unit** model. Each reading unit consists of:

1. One Biblical verse.
2. The Rashi commentary entries associated with that verse.

```
Biblical verse
──────── רש״י ────────
Rashi commentary for the preceding verse
```

- Commentary appears **immediately after** the verse it belongs to.
- The EPUB must **not** use a layout where a whole chapter is followed by all of its commentary.
- The EPUB must **not** require navigating away from the Biblical text to read Rashi.
- Commentary is **always inline**. Tap-to-open (`<details>`, or `epub:type="noteref"` popups) was tested on the Paperwhite and cannot work: a tap anywhere on the page turns it. Do not revisit without new evidence from the device (PROGRESS.md D9).
- On Kindle the unit may be split across a page boundary by the renderer; the רש״י divider is what keeps verse and commentary visually attached. This is acceptable and expected.

---

## 3. Delivery Path and Development Loop

### 3.1 Delivery to the device

The generator produces an EPUB. Getting it onto the Kindle is part of the project, not an afterthought. Two candidate paths:

| Path | How | Pros | Risks |
|---|---|---|---|
| **A. Calibre → KFX → USB** | Calibre with the *KFX Output* plugin (which wraps Kindle Previewer), then copy the `.kfx` to the device over USB | Most predictable; fonts and RTL survive reliably | Requires Calibre + Kindle Previewer installed (macOS/Windows) |
| **B. Send to Kindle** | Email / web / app upload of the EPUB; Amazon converts server-side | Zero tooling; wireless | Amazon's converter controls what survives; embedded fonts are sometimes dropped |

Rules:

- The POC (§34) must be tested through **both** paths.
- After the POC, standardize on the path that preserves ניקוד, טעמים, embedded fonts and RTL page turns. Record the choice in `config/default.yaml` (`target.delivery`) and in the README.
- Default assumption until tested: **Path A**.

### 3.2 Development loop tools

| Tool | Role | Automated? |
|---|---|---|
| **EPUBCheck** | Structural validity of every build | Yes — runs in tests/CI |
| **Kindle Previewer 3** | Converts EPUB → KPF and previews on Kindle device profiles (Paperwhite etc.); catches Kindle-specific rendering problems before the device | Semi — macOS/Windows only; run via its CLI (`kindlepreviewer <file.epub> -convert -output <dir>`) when available, skipped otherwise |
| **Calibre + KFX Output plugin** | Produces the sideloadable file for Path A | Manual / scripted |
| **Physical Paperwhite** | Final acceptance | Manual, using the checklist in §3.3 |

### 3.3 On-device checklist

Every milestone build (POC, full Genesis, full Torah, full Tanakh) is checked on the Paperwhite:

- [ ] Book opens; cover shows in the library.
- [ ] With **Publisher Font** selected, biblical text uses the embedded biblical font.
- [ ] ניקוד and טעמים render correctly stacked (בראשית א׳:א׳ is the reference verse).
- [ ] Rashi text uses the embedded Rashi font (if `rashi_script: true`) and is legible at the default Kindle size.
- [ ] Page turns go right-to-left.
- [ ] Verse numbers, gershayim, geresh, parentheses render correctly in RTL.
- [ ] Font size changes scale biblical text, verse numbers and Rashi proportionally.
- [ ] "Go to" menu shows books and chapters; links land on the right chapter.
- [ ] Verses without Rashi show no empty commentary block.

---

## 4. Target Output

Primary output: `Tanakh_with_Rashi.epub`

The EPUB must:

- Be EPUB 3 compliant and pass EPUBCheck.
- Use reflowable layout.
- Support RTL Hebrew.
- Embed fonts.
- Support dynamic font resizing.
- Contain an EPUB 3 Navigation Document **and** an EPUB 2 NCX (Kindle conversion tools and older readers benefit from the NCX).
- Contain internal navigation anchors per chapter and per verse.
- Be usable on E-Ink screens.

Use only the subset of EPUB features that survives Kindle conversion. Avoid proprietary Kindle-only markup (no `.azw3`-specific CSS, no Amazon `-kindle-` properties); the goal is a clean EPUB that converts well.

---

## 5. Content Scope

The architecture supports the complete Tanakh: תורה, נביאים, כתובים.

The generator must support building subsets for testing (Genesis only, Torah only, Tanakh without commentary, Tanakh + Rashi). It must not hard-code Genesis-specific logic.

---

## 6. Language Requirements

All reading content is Hebrew.

Allowed: `בראשית`, `פרק א׳`, `בְּרֵאשִׁית בָּרָא אֱלֹהִים`, `רש״י`
Disallowed in reading content: `Genesis`, `Chapter 1`, `Verse 1`, `In the beginning`

Technical metadata, Python identifiers, filenames, internal references and log output use English.

---

## 7. Hebrew Text Requirements

The Biblical text must preserve Hebrew letters, ניקוד, טעמי המקרא (when present in the selected source version), סוף פסוק, and Hebrew punctuation.

The implementation must **not** strip Unicode combining marks, normalize away ניקוד or טעמים, or replace Hebrew with transliteration.

Unicode normalization: store and process text in **NFC**. Never apply NFKC/NFKD. Verify (test) that NFC round-trips the source text without loss for the selected version.

---

## 8. Hebrew Chapter and Verse Numbers

Chapter and verse numbers are displayed as Hebrew numerals: `פרק א׳`, `פרק י״א`, `פרק ט״ו`, `פרק ט״ז`, `פרק ק׳`.

### 8.1 `int_to_hebrew_numeral(number: int) -> str`

- Standard Hebrew numeral conventions.
- 15 → `ט״ו`, 16 → `ט״ז` (also inside larger numbers, e.g. 115 → `קט״ו`).
- Geresh (`׳`, U+05F3) for single-letter numerals; gershayim (`״`, U+05F4) before the last letter for multi-letter numerals.
- Use the real Hebrew geresh/gershayim characters, never ASCII `'` / `"`.

```
1 → א׳    2 → ב׳    9 → ט׳    10 → י׳    11 → י״א
15 → ט״ו  16 → ט״ז  20 → כ׳   21 → כ״א   50 → נ׳   100 → ק׳
```

### 8.2 Numbering scheme

Sefaria already uses the **Hebrew** chapter/verse scheme (which differs from KJV numbering in places). Use Sefaria's numbers as-is. Do not remap to any other scheme.

---

## 9. Book Structure and Canonical Book Table

Logical hierarchy:

```
Tanakh
├── תורה      בראשית שמות ויקרא במדבר דברים
├── נביאים    יהושע … מלאכי
└── כתובים    תהלים … דברי הימים ב׳
```

Books are defined in one place, `config/books.yaml`, with an explicit slug — **never** derived by lower-casing the English name (I/II Samuel, Kings, Chronicles and "Song of Songs" would break naive slugging). Order in this table is the canonical Tanakh order.

| # | Section | Sefaria title (internal) | Hebrew title (rendered) | Slug |
|---|---|---|---|---|
| 1 | torah | Genesis | בראשית | genesis |
| 2 | torah | Exodus | שמות | exodus |
| 3 | torah | Leviticus | ויקרא | leviticus |
| 4 | torah | Numbers | במדבר | numbers |
| 5 | torah | Deuteronomy | דברים | deuteronomy |
| 6 | neviim | Joshua | יהושע | joshua |
| 7 | neviim | Judges | שופטים | judges |
| 8 | neviim | I Samuel | שמואל א׳ | samuel-1 |
| 9 | neviim | II Samuel | שמואל ב׳ | samuel-2 |
| 10 | neviim | I Kings | מלכים א׳ | kings-1 |
| 11 | neviim | II Kings | מלכים ב׳ | kings-2 |
| 12 | neviim | Isaiah | ישעיהו | isaiah |
| 13 | neviim | Jeremiah | ירמיהו | jeremiah |
| 14 | neviim | Ezekiel | יחזקאל | ezekiel |
| 15 | neviim | Hosea | הושע | hosea |
| 16 | neviim | Joel | יואל | joel |
| 17 | neviim | Amos | עמוס | amos |
| 18 | neviim | Obadiah | עובדיה | obadiah |
| 19 | neviim | Jonah | יונה | jonah |
| 20 | neviim | Micah | מיכה | micah |
| 21 | neviim | Nahum | נחום | nahum |
| 22 | neviim | Habakkuk | חבקוק | habakkuk |
| 23 | neviim | Zephaniah | צפניה | zephaniah |
| 24 | neviim | Haggai | חגי | haggai |
| 25 | neviim | Zechariah | זכריה | zechariah |
| 26 | neviim | Malachi | מלאכי | malachi |
| 27 | ketuvim | Psalms | תהלים | psalms |
| 28 | ketuvim | Proverbs | משלי | proverbs |
| 29 | ketuvim | Job | איוב | job |
| 30 | ketuvim | Song of Songs | שיר השירים | song-of-songs |
| 31 | ketuvim | Ruth | רות | ruth |
| 32 | ketuvim | Lamentations | איכה | lamentations |
| 33 | ketuvim | Ecclesiastes | קהלת | ecclesiastes |
| 34 | ketuvim | Esther | אסתר | esther |
| 35 | ketuvim | Daniel | דניאל | daniel |
| 36 | ketuvim | Ezra | עזרא | ezra |
| 37 | ketuvim | Nehemiah | נחמיה | nehemiah |
| 38 | ketuvim | I Chronicles | דברי הימים א׳ | chronicles-1 |
| 39 | ketuvim | II Chronicles | דברי הימים ב׳ | chronicles-2 |

Verify the exact Sefaria index titles against the API before relying on this table; the table is the contract, the API is the source of truth for spelling.

---

## 10. Navigation (TOC)

The EPUB contains a valid EPUB 3 Navigation Document (`nav.xhtml`) and an NCX (`toc.ncx`).

**Depth is exactly two levels: book → chapter.** Kindle's "Go to" menu shows two nested levels; a third level (section → book → chapter) would hide chapters.

```xml
<nav epub:type="toc" id="toc">
  <ol>
    <li><a href="text/genesis-001.xhtml">בראשית</a>
      <ol>
        <li><a href="text/genesis-001.xhtml#chapter-1">פרק א׳</a></li>
        <li><a href="text/genesis-002.xhtml#chapter-2">פרק ב׳</a></li>
      </ol>
    </li>
  </ol>
</nav>
```

Requirements:

- Every book and every chapter is directly accessible from the TOC.
- Each chapter link points to a stable anchor.
- Hebrew titles only; the nav document is `lang="he" dir="rtl"`.
- `navigation.include_sections` defaults to **false**. When true, sections (תורה / נביאים / כתובים) are inserted as **flat** top-level entries pointing at a section landing page — never as parents of books, so the two-level limit holds.
- Optionally add `<nav epub:type="landmarks">` with the start of reading content and the מקורות page.

---

## 11. File Layout: One XHTML per Chapter

```
OEBPS/
├── text/
│   ├── genesis-001.xhtml
│   ├── genesis-002.xhtml
│   ├── …
│   ├── exodus-001.xhtml
│   ├── …
│   └── sources.xhtml          (מקורות — attribution, see SPEC_DATA_SOURCE §13)
├── styles/main.css
├── fonts/
│   ├── biblical_hebrew.ttf
│   └── rashi.ttf
├── images/cover.jpg            (if a cover is included)
├── nav.xhtml
├── toc.ncx
└── content.opf
```

Rules:

- **One XHTML file per chapter**: `{slug}-{chapter:03d}.xhtml`. One file per book (v1 spec) is withdrawn: Psalms, Isaiah, Jeremiah and Genesis+Rashi far exceed Amazon's ~300 KB guideline and degrade rendering/navigation.
- `layout.max_file_kb` (default 300) is enforced by a test; if a single chapter with commentary exceeds it (rare), the renderer splits the chapter file at a study-unit boundary (`{slug}-{chapter:03d}-b.xhtml`) and keeps the chapter anchor in the first part.
- The first chapter file of each book carries the book heading; the TOC book entry links to it.
- Spine order = canonical book order × chapter order.
- Do not create one XHTML file for the entire Tanakh.

---

## 12. Reading Unit Markup

### 12.1 Verse

```xml
<div class="verse" id="genesis-1-1">
  <span class="verse-number">א׳</span>
  <span class="biblical-text">בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ׃</span>
</div>
```

Stable verse ID format: `{slug}-{chapter}-{verse}` (e.g. `genesis-1-1`, `samuel-1-3-14`).

### 12.2 Commentary

```xml
<section class="study-unit">
  <div class="verse" id="genesis-1-1">…</div>
  <section class="commentary rashi">
    <div class="commentary-divider">רש״י</div>
    <div class="commentary-entry">
      <span class="dibur-hamatchil">בראשית</span>
      <span class="commentary-text">אמר רבי יצחק…</span>
    </div>
    <div class="commentary-entry">…</div>
  </section>
</section>
```

Rendering is driven by `commentator`, not hard-coded to Rashi: the class list is `commentary {commentator-slug}` and the divider label comes from the commentator's Hebrew name in config.

---

## 13. Commentary Granularity and Grouping

- Multiple commentary entries per verse are the norm; each stays a separate `commentary-entry` in source order.
- Each entry may carry a `dibur_hamatchil` (see SPEC_DATA_SOURCE §9 for how it is obtained). If present it is rendered first, visually distinguished (bold/spacing, no color), followed by the entry text.
- Page-break hints (`break-inside: avoid`) are applied to a small "keep-together" wrapper: the verse + the רש״י divider + the first commentary entry. Wrapping the whole study unit (v1 spec) is withdrawn: Rashi on בראשית א׳:א׳ alone spans several screens, and readers that honor the hint (Kobo, Apple Books) would leave large blank pages.
- A layout profile may also ask **each individual entry** after the first not to split (`breaks.keep_each_entry_together`). Each entry is its own element for exactly this reason. The request is made one entry at a time and never for the run of entries, so the study unit as a whole always stays free to split.
- Whether the Paperwhite honours any of these hints is not established. It is being tested (`docs/LAYOUT_EXPERIMENT.md`, D10). Either way, nothing may depend on a hint being honoured.

```xml
<section class="study-unit">
  <div class="keep-together">
    <div class="verse">…</div>
    <div class="commentary-divider">רש״י</div>
    <div class="commentary-entry">…first entry…</div>
  </div>
  <div class="commentary-entry">…second entry…</div>
  …
</section>
```

Do not use JavaScript to measure the screen.

---

## 14. Responsive Typography

The layout must respond correctly when the reader changes the base font size. Core layout uses only `em`, `rem` and `%`. No `px`, `vh`, `vw` for reading layout.

Default hierarchy (configurable via `typography.*_scale`):

| Element | Size |
|---|---|
| Biblical text | 1.25em |
| Verse number | 0.75em |
| Commentary divider (רש״י) | 0.85em |
| Rashi text | 0.85em |

When Kindle's font size changes, all of these scale together and the ratios stay intact. Kindle respects relative `font-size` and `line-height`.

Line heights (`typography.*_line_height`), vertical spacing (`spacing.*`) and the optional page-break hints (`breaks.*`) are configurable too. A **layout profile** (`layout_profiles.*`, chosen by `layout.profile`) overrides any of them, but never a font or the content. Four profiles are defined for the device comparison in `docs/LAYOUT_EXPERIMENT.md` (decision D10); until D10 is settled, a normal build uses the control, `current`, which has the values in the table above.

Note for the Paperwhite (7″): Rashi script at 0.85em is a legibility gamble. The POC must include a legibility check on the device; if it fails, raise `rashi_scale` (0.9–0.95) or set `rashi_script: false` (§15.2) before scaling to the full Tanakh.

---

## 15. Fonts

Two independent embedded fonts. Fonts are embedded as TTF/OTF (WOFF is not reliably supported through Kindle conversion). Both `@font-face` families are declared in `main.css`; Kindle applies them under **Publisher Font**.

### 15.1 Biblical text font

Used for verses, book titles, chapter titles, verse numbers.

Requirements: full Hebrew coverage, ניקוד, טעמי המקרא with correct mark positioning (stacked marks must not collide), RTL, and a license permitting embedding and redistribution inside an EPUB.

Candidates (all embeddable; pick one after an on-device test of בראשית א׳):

- **Taamey Frank CLM** or **Taamey David CLM** (Culmus project; GPL with font-embedding exception)
- **Ezra SIL** / **Ezra SIL SR** (SIL Open Font License)

Record the chosen font, version and license in `config/default.yaml` and in the sources page.

### 15.2 Rashi font

Used exclusively for commentary body text (not the dibur hamatchil label, which may use the biblical font for scanability — configurable).

Requirements: Rashi script (or, as fallback, a highly legible square Hebrew), Hebrew coverage, license permitting embedding.

Rules:

- **Selecting a Rashi-script font with a verified license is a blocking task** (tracked in `CLAUDE.md` → Open decisions). Do not embed any font whose license has not been checked.
- `typography.rashi_script: true | false`. When `false`, Rashi text uses the biblical font (or a configured second square font); the divider, size and dibur-hamatchil styling still distinguish it. This keeps the build unblocked if no suitable Rashi-script font is found, and gives a readability escape hatch on the Paperwhite.

```css
@font-face { font-family: "BiblicalHebrew"; src: url("../fonts/biblical_hebrew.ttf"); }
@font-face { font-family: "Rashi";          src: url("../fonts/rashi.ttf"); }
```

---

## 16. Font Fallbacks

Every custom family declares fallbacks; the book stays readable with embedded fonts disabled (Kindle's default when Publisher Font is not selected).

```css
.biblical-text { font-family: "BiblicalHebrew", serif; }
.commentary-text { font-family: "Rashi", "BiblicalHebrew", serif; }
```

---

## 17. RTL Requirements

Root element of every XHTML file:

```xml
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
```

```css
body { direction: rtl; text-align: right; }
```

OPF: `<dc:language>he</dc:language>` and `<spine page-progression-direction="rtl">`. Kindle uses the language to flip page-turn direction; the POC verifies this on device.

All reading content must render correctly: Hebrew punctuation, verse numbers, gershayim, geresh, parentheses, ניקוד, טעמים.

---

## 18. Chapter Structure

Each chapter file:

```xml
<section id="chapter-1" epub:type="chapter">
  <h1 class="book-heading">בראשית</h1>        <!-- first chapter of the book only -->
  <h2 class="chapter-heading">פרק א׳</h2>
  …study units…
</section>
```

Headings must not consume excessive vertical space. No full-page chapter title pages.

---

## 19. Data Model (canonical — supersedes both v1 documents)

```python
@dataclass(frozen=True)
class Verse:
    book: str                 # Sefaria English title, e.g. "Genesis"
    chapter: int
    verse: int
    hebrew_text: str          # NFC, source markup already converted to internal markup
    source_provider: str      # "Sefaria"
    source_version: str       # exact Sefaria versionTitle

@dataclass(frozen=True)
class CommentaryEntry:
    commentator: str          # "Rashi"
    book: str
    chapter: int
    verse: int
    entry_number: int         # 1-based, source order
    dibur_hamatchil: str | None
    text: str                 # NFC, internal markup
    source_provider: str
    source_version: str
    source_reference: str     # e.g. "Rashi on Genesis 1:1:1"

@dataclass(frozen=True)
class StudyUnit:
    verse: Verse
    commentaries: list[CommentaryEntry]   # may be empty; source order
```

Multiple commentators are supported by design (Rashi first; Ramban, Ibn Ezra, Sforno, Steinsaltz later). Nothing in rendering assumes exactly one commentator or one entry per verse.

---

## 20. Provider Abstraction

Content retrieval is separated from rendering. Providers fetch **whole books**, never single verses (see SPEC_DATA_SOURCE §2). The renderer consumes only the internal data model; it never sees provider response formats and never performs HTTP.

```python
class TextProvider(Protocol):
    def get_books(self) -> list[str]: ...
    def get_book_text(self, book: str) -> list[list[str]]: ...      # [chapter][verse]

class CommentaryProvider(Protocol):
    def get_book_commentary(self, commentator: str, book: str) -> list[list[list[str]]]: ...  # [chapter][verse][entry]
```

Per-verse lookups are in-memory over the loaded book.

---

## 21. Content Validation (before rendering)

Biblical text: book exists · chapter valid · verse valid · text not empty · Hebrew preserved (NFC, marks present where the version has them).
Commentary: reference resolves · book/chapter/verse match the verse · text not empty.
Markup: no unknown tags remain (SPEC_DATA_SOURCE §9).
Layout: no chapter file exceeds `layout.max_file_kb`.

---

## 22. Missing Commentary

Verses without Rashi render the verse only. Never render an empty רש״י block, unless `debug.show_empty_commentary: true`.

---

## 23. Commentary Ordering

Entries keep their original source order. Never sort alphabetically, by length, or by dibur hamatchil.

---

## 24. Visual Separation

Subtle and E-Ink friendly: **one** thin rule above the label `רש״י`, and no second rule below it. The label is centred or at the start of the line, depending on the layout profile. It is a compact label, not a band between two lines.

Avoid colors, background images, heavy borders, icons, decorative graphics. Must look right in black-and-white, dark mode, inverted mode and on color E-Ink.

---

## 25. Accessibility / Semantics

Use `<h1>`, `<h2>`, `<section>`, `<p>`, `<nav>` where appropriate; not a pure `<div>/<span>` soup. `<aside epub:type="annotation">` for commentary may be tried, but **compatibility with Kindle conversion wins** over semantic sophistication — if Kindle Previewer renders `<aside>` oddly, use `<section>`.

---

## 26. CSS Compatibility

Use only: `direction`, `text-align`, `font-family`, `font-size`, `font-weight`, `line-height`, `margin`, `padding`, `border`, `text-indent`, `break-*` / `page-break-*` (as hints).

Avoid: CSS Grid, complex Flexbox, JavaScript, `position: fixed/sticky`, `vh`/`vw`, viewport calculations, `@page` tricks, dynamic screen measurement.

The book must remain usable when all advanced CSS is ignored (which is close to what Kindle does).

---

## 27. Page Break Behaviour

- Never force each verse or each commentary entry onto its own page.
- The reader reflows freely. `break-inside: avoid` on `.keep-together` and `break-after: avoid` on headings are soft hints only. Layout profiles may add three more: each commentary entry, the divider with its neighbours, and the book heading with the chapter heading (§13, `docs/LAYOUT_EXPERIMENT.md`).
- Every hint is written in both spellings: `break-*` and the CSS 2.1 `page-break-*`.
- Chapter headings: `.chapter-heading { break-after: avoid; page-break-after: avoid; }`.
- Optionally `break-before: page` on each **book's** first chapter so a new book starts on a fresh page. Chapters do not force a page break.

---

## 28. EPUB Metadata

| Field | Value |
|---|---|
| `dc:title` | `תנ״ך עם פירוש רש״י` |
| `dc:language` | `he` |
| `dc:identifier` | UUID (stable per build config; regenerated only on `--new-identifier`) |
| `dc:publisher` / `dc:creator` | Configurable |
| `dcterms:modified` | ISO 8601 UTC |
| Custom `meta` | Sefaria version titles for Tanakh and each commentator; build manifest id |

---

## 29. Cover

`cover.mode: none | generated | custom`. Default **generated**: a minimal black-and-white JPEG with `תנ״ך / עם פירוש רש״י` in the biblical font, declared with `properties="cover-image"` in the OPF. Kindle shows the cover in the library, so a cover is on by default, but the core build must not depend on it.

---

## 30. Configuration (`config/default.yaml`)

```yaml
title: "תנ״ך עם פירוש רש״י"

target:
  device: kindle-paperwhite-12     # documentation only; nothing branches on it
  delivery: calibre-kfx            # calibre-kfx | send-to-kindle  (decided after POC)

include:
  tanakh: true
  commentaries: [Rashi]            # commentator names as in config/commentators.yaml

sources:                           # see SPEC_DATA_SOURCE
  tanakh:
    provider: sefaria
    version_title: "<SELECTED_SEFARIA_VERSION>"
    language: he
  commentaries:
    Rashi:
      provider: sefaria
      version_title: "<SELECTED_SEFARIA_VERSION>"
      language: he

fonts:
  biblical: { file: fonts/biblical_hebrew.ttf, family: BiblicalHebrew, license: "<recorded>" }
  rashi:    { file: fonts/rashi.ttf,           family: Rashi,          license: "<recorded>" }

typography:
  biblical_scale: 1.25
  rashi_scale: 0.85
  verse_number_scale: 0.75
  divider_scale: 0.85
  rashi_script: true               # false → commentary uses the biblical font

navigation:
  include_sections: false          # flat entries only if true (Kindle: max 2 nested levels)
  include_books: true
  include_chapters: true

layout:
  file_per: chapter
  max_file_kb: 300
  page_break_before_book: true

cover:
  mode: generated                  # none | generated | custom
  path: null

debug:
  show_empty_commentary: false

output:
  dir: output
  filename: Tanakh_with_Rashi.epub
```

`config/books.yaml` holds the book table (§9); `config/commentators.yaml` holds `{Rashi: {hebrew: "רש״י", slug: rashi, sefaria_prefix: "Rashi on "}}`.

---

## 31. Command Line Interface

```
python -m tanakh_epub build                          # full build from config/default.yaml
python -m tanakh_epub build --book Genesis
python -m tanakh_epub build --books Genesis Exodus
python -m tanakh_epub build --chapter Genesis 1      # POC-sized build
python -m tanakh_epub build --no-commentary
python -m tanakh_epub build --output output/tanakh.epub
python -m tanakh_epub build --config config/kobo.yaml
python -m tanakh_epub fetch  [--book Genesis] [--refresh | --refresh-all]
python -m tanakh_epub validate                       # data completeness + markup report, no EPUB
python -m tanakh_epub inventory-markup               # tag/class inventory of cached data
python -m tanakh_epub check output/Tanakh_with_Rashi.epub   # EPUBCheck (+ Kindle Previewer if installed)
python -m tanakh_epub build --layout-profile dense   # any key under layout_profiles
python -m tanakh_epub experiment-layout [--chapter Genesis 1] [--profiles …] [--kpf]
                                                     # one EPUB per layout profile, same content
```

---

## 32. Project Structure

```
tanakh_epub/
├── CLAUDE.md
├── SPEC.md
├── SPEC_DATA_SOURCE.md
├── README.md                     # includes "select Publisher Font on Kindle" and the delivery steps
├── pyproject.toml
├── config/
│   ├── default.yaml
│   ├── books.yaml
│   └── commentators.yaml
├── data/
│   ├── cache/                    # Sefaria downloads (git-ignored)
│   │   ├── tanakh/<slug>.json
│   │   └── rashi/<slug>.json
│   └── processed/                # normalized internal model (git-ignored)
├── fonts/                        # only fonts whose license permits redistribution
├── src/tanakh_epub/
│   ├── __main__.py               # CLI
│   ├── models.py                 # Verse, CommentaryEntry, StudyUnit
│   ├── books.py                  # loads books.yaml; slug/title lookups
│   ├── providers/
│   │   ├── base.py
│   │   ├── sefaria.py            # API + Sefaria-Export access, caching
│   │   └── local.py              # processed JSON, for offline/test builds
│   ├── processing/
│   │   ├── normalize.py          # NFC, whitespace
│   │   ├── markup.py             # Sefaria markup → internal markup (explicit rules)
│   │   ├── hebrew_numbers.py
│   │   ├── study_units.py
│   │   └── validation.py
│   ├── rendering/
│   │   ├── html_renderer.py      # Jinja2 templates → XHTML per chapter
│   │   ├── css.py
│   │   └── templates/
│   └── epub/
│       ├── builder.py            # container.xml, OPF, spine, zip
│       ├── navigation.py         # nav.xhtml + toc.ncx
│       ├── metadata.py
│       ├── cover.py
│       └── manifest.py           # build manifest + SOURCES_AND_LICENSES.md
├── tests/
├── scripts/
│   ├── epubcheck.sh
│   └── kindle_previewer.sh       # no-op with a message if the tool is absent
└── output/
```

Implementation note: prefer a small hand-rolled EPUB writer (`zipfile` + Jinja2 templates) for full control over OPF/nav/NCX. `ebooklib` is acceptable only if its output passes EPUBCheck **and** Kindle Previewer without patching.

---

## 33. Required Tests

- **Hebrew numerals**: 1, 10, 11, 15, 16, 22, 100, 115, 316 → expected strings with real geresh/gershayim.
- **Slugs**: every entry in `books.yaml` has a unique slug; `I Samuel` → `samuel-1`; slugs are URL/ID-safe.
- **NFC round-trip**: normalizing the source text is lossless for the selected version (no marks dropped).
- **Markup rules**: each documented Sefaria pattern converts as specified; an unknown tag raises.
- **RTL**: every generated XHTML has `lang="he"` and `dir="rtl"`; OPF has `page-progression-direction="rtl"`.
- **Navigation**: every book and chapter appears in both nav.xhtml and toc.ncx; every anchor exists; nesting depth ≤ 2.
- **Commentary**: Rashi follows the correct verse; multiple entries keep order; verses without Rashi have no commentary block.
- **Chunking**: one file per chapter; no file exceeds `max_file_kb`.
- **Fonts**: both `@font-face` families declared; font files present in the OPF manifest.
- **EPUBCheck**: every build passes (test skipped with a clear message if `epubcheck` is not installed).
- **Kindle Previewer** (optional, skipped if absent): conversion of the POC succeeds with zero errors.

---

## 34. Proof of Concept

Build **בראשית פרק א׳, פסוקים א׳–י׳ with רש״י** → `Genesis_Chapter_1.epub`.

Must demonstrate: Hebrew text with ניקוד and טעמים · RTL · Hebrew verse and chapter numbers · embedded biblical font · embedded Rashi font (or documented fallback) · verse–commentary units with multiple entries · TOC · dynamic font resizing.

Must be **verified on the Paperwhite** through **both** delivery paths (§3.1) using the checklist in §3.3. The delivery path, font choices and `rashi_scale` are frozen only after this. Nothing beyond Genesis is built before the POC passes on the device.

---

## 35. Acceptance Criteria

**Content**: Hebrew only · ניקוד preserved · טעמים preserved when present · Hebrew verse/chapter numerals · Rashi directly after its verse · entries in source order · no empty commentary blocks.

**Typography**: biblical font and Rashi font embedded and applied under Publisher Font · scaling proportional at small and large Kindle sizes · Rashi legible on the Paperwhite at the default size.

**Navigation**: every book and chapter in nav + NCX · links work in Kindle's "Go to" · two levels.

**Kindle**: passes Kindle Previewer with no errors · on-device checklist (§3.3) fully green on the full Tanakh build · RTL page turns.

**Compatibility**: passes EPUBCheck · reflowable · no fixed dimensions · no JavaScript · still readable in Kobo / Apple Books.

**Architecture**: providers separated from rendering · commentary abstracted · multiple commentators possible · source data replaceable without touching rendering.

---

## 36. Explicit Non-Goals (v1)

English translations · transliteration · audio · JavaScript · fixed-layout · exact 50/50 screen splitting · screen-size detection · user accounts · cloud sync · note-taking · highlighting · custom search.

---

## 37. Core Design Principle

The Biblical text and its commentary must remain visually and logically connected while the e-reader — first and foremost the Kindle Paperwhite — freely reflows the content to its screen and the reader's chosen font size.

Priorities, in order:

1. Hebrew text accuracy.
2. Reading comfort on the Paperwhite.
3. E-Ink and Kindle-conversion compatibility.
4. Font-size responsiveness.
5. Cross-device EPUB compatibility.
6. Semantic navigation.
7. Clean separation between content acquisition and rendering.

A genuine responsive study book — not a PDF inside an EPUB.

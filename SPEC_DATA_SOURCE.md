# Data Source Specification — Sefaria as the Required Content Source

**Version 2 — 2026-09-11.** Supersedes *Specification Amendment: Sefaria as the Required Content Source (v1)*.
Companion document: `SPEC.md`. The data model in `SPEC.md` §19 is canonical; this document defines how it is populated.

---

## 1. Authoritative Content Source

All Biblical text and commentary content is retrieved from **Sefaria**. No alternative Biblical text provider is used unless explicitly configured for development or testing.

Content: תנ״ך, פירוש רש״י (further commentators later).

The implementation uses Sefaria's official data access mechanisms only:

- the **Sefaria API** (developers.sefaria.org), and/or
- the **Sefaria-Export** repository on GitHub (structured JSON dumps of the same texts).

The implementation must **not** scrape the rendered sefaria.org website: no downloading of rendered pages, no parsing of UI HTML, no dependence on sefaria.org CSS classes.

---

## 2. Fetch Granularity: Whole Books, Never Verses

The v1 provider interface (`get_verse`, `get_rashi(book, chapter, verse)`) is withdrawn: it implies tens of thousands of HTTP requests (23,206 verses plus every Rashi entry).

Rules:

- The provider fetches **one whole book per request** (`Genesis`, `Rashi on Genesis`). Sefaria returns a book as nested JSON `[chapter][verse]` (text) or `[chapter][verse][entry]` (commentary).
- Per-verse access is an in-memory lookup over the cached book.
- For the **bulk build** of the full Tanakh, prefer the Sefaria-Export repository (one raw JSON file per book/version) over the API. Do not clone the whole repository (it is several GB); download the specific raw files needed, or use a sparse checkout.
- The API is used for version discovery, for refreshing single books, and as a fallback if a file is absent from the export.
- API requests are polite: a descriptive `User-Agent`, a small delay between requests, and exponential backoff on 429/5xx.

```python
class SefariaProvider:
    def list_versions(self, index_title: str) -> list[VersionInfo]: ...
    def get_book_text(self, book: str, *, version_title: str) -> list[list[str]]: ...
    def get_book_commentary(self, commentator: str, book: str, *, version_title: str) -> list[list[list[str]]]: ...
```

The EPUB generation layer never performs HTTP.

```
Sefaria API / Sefaria-Export
        ↓
SefariaProvider  (fetch whole books, cache)
        ↓
Markup + normalization layer  (§8–§9)
        ↓
Internal data model  (SPEC.md §19)
        ↓
Study-unit builder → XHTML renderer → EPUB generator
```

---

## 3. Sefaria Data Layout

Nested list conventions (verify against the live API before coding):

- Text index `Genesis`: `text[chapter_idx][verse_idx]` → Hebrew string with inline markup.
- Commentary index `Rashi on Genesis`: `text[chapter_idx][verse_idx][entry_idx]` → Hebrew string with inline markup. Indices align **structurally** with the base text: `Rashi on Genesis 1:1:2` is the second Rashi entry on Genesis 1:1.
- Empty lists / empty strings mean "no text here" (e.g. a verse with no Rashi).

Commentary → verse mapping therefore comes from Sefaria's **reference structure** (index alignment / `Rashi on Genesis 1:1:n`). Never infer the relationship by matching Hebrew text, dibur hamatchil, or fuzzy string search.

Sefaria uses the **Hebrew** chapter/verse numbering scheme. Use it as-is (SPEC.md §8.2).

---

## 4. Biblical Text Version — Explicit Selection

The Hebrew Biblical version is chosen explicitly and recorded; the build never silently uses whatever the API returns by default.

Selection procedure (a one-time task, output recorded in `config/default.yaml` and `docs/VERSION_SELECTION.md`):

1. List available Hebrew versions of a sample book via the API (`list_versions("Genesis")`).
2. Evaluate each candidate for: Hebrew text completeness · ניקוד · טעמי המקרא · Unicode quality (NFC-clean, no private-use characters) · consistency across all 39 books · license compatibility with an EPUB you can share · a stable `versionTitle`.
3. Pick one. Record `versionTitle`, `language`, `license`, `versionSource` and the date checked.

Known candidates as of this writing (verify names against the API — they may have changed):

- *Tanach with Ta'amei Hamikra* — with cantillation.
- *Tanach with Nikkud* — vowels only, no cantillation.
- *Miqra according to the Masorah* (MAM) — with cantillation, CC BY-SA; Sefaria's current default Hebrew Tanakh in many contexts.

Requirement from `SPEC.md` §7: the chosen version must carry טעמים. A nikud-only version is acceptable only as an explicitly configured fallback.

```yaml
sources:
  tanakh:
    provider: sefaria
    version_title: "<exact versionTitle>"
    language: he
    license: "<from version metadata>"
    checked: 2026-09-11
```

---

## 5. Rashi Version — Explicit Selection

Same procedure for `Rashi on Genesis` … `Rashi on II Chronicles`. Rashi versions on Sefaria vary in markup style (bold dibur hamatchil, footnotes) — the markup inventory (§9) is run on the chosen version.

Coverage varies: not every book of the Tanakh has Rashi on Sefaria, and some are attributed/pseudo-Rashi. The provider treats a missing commentary index as "no commentary for this book" (logged, reported in the validation report), not as a failure.

---

## 6. Commentary References

Preserve the mapping `Genesis 1:1 → Rashi on Genesis 1:1:1, 1:1:2, …`. Each `CommentaryEntry.source_reference` stores the full Sefaria reference string so any entry can be traced back.

```python
@dataclass(frozen=True)
class VerseReference:
    book: str; chapter: int; verse: int
    def canonical_ref(self) -> str:        # "Genesis 1:1"
        return f"{self.book} {self.chapter}:{self.verse}"
    def commentary_ref(self, prefix: str, entry: int) -> str:   # "Rashi on Genesis 1:1:1"
        return f"{prefix}{self.canonical_ref()}:{entry}"
```

---

## 7. Preserve Original Sefaria Content

The generator never translates, rewrites, modernizes, respells, corrects, summarizes, or strips ניקוד/טעמים.

Allowed transformations only: markup conversion per §9 · Unicode NFC normalization · whitespace normalization (collapse runs of spaces; trim) · removal of technical markup per §9 · conversion into valid XHTML.

---

## 8. HTML Handling — Never Insert Raw Sefaria Strings

Sefaria strings contain inline HTML. The pipeline is: parse with an HTML parser (not regex) → apply the explicit rules in §9 → emit internal markup → renderer escapes/serializes to XHTML. `html = response["text"]` pasted into a template is forbidden.

---

## 9. Markup Rules (explicit, inventoried, fail-loud)

### 9.1 Inventory first

Before writing conversion rules, run `python -m tanakh_epub inventory-markup` over the cached data for the selected versions. It prints every tag, attribute and class combination with counts and one example reference per combination. The rules table below is completed from that inventory and kept in `docs/MARKUP_RULES.md`.

### 9.2 Rules table (initial — extend from the inventory)

| Sefaria markup | Found in | Rule |
|---|---|---|
| `<b>…</b>` as the leading element of a commentary entry | Rashi | Extract as `dibur_hamatchil`; remove from `text`. Rendered as `<span class="dibur-hamatchil">`. This is structural extraction from Sefaria's own markup, not text matching. |
| `<b>` elsewhere | Rashi | Keep as `<b>` |
| `<i>…</i>` | both | Keep as `<em>` |
| `<br>` | Rashi | Paragraph break inside the entry |
| `<big>` / `<small>` | Tanakh | `<span class="letter-large">` / `<span class="letter-small">` (e.g. enlarged/reduced letters in the Masoretic text) |
| Parasha markers `{פ}` / `{ס}` (plain or inside a `<span>`) | Tanakh | Keep as text in `<span class="parasha-marker">`; a `{פ}` ends the paragraph |
| `<sup>`, footnote markers, `<i class="footnote">` | both | Drop, including their content |
| Other `<span class="mam-…">` (MAM structural spans) | Tanakh | Decided per class from the inventory: keep text, map to an internal class, or drop |
| Anything not in this table | both | **Build fails** with the tag, class and a reference. Never silently strip. |

### 9.3 Internal markup

After conversion, `Verse.hebrew_text` and `CommentaryEntry.text` contain only the internal subset: `<b>`, `<em>`, `<span class="letter-large|letter-small|parasha-marker">`, and paragraph breaks. A test asserts nothing else is present before rendering.

---

## 10. Internal Data Model

Defined once, in `SPEC.md` §19 (`Verse`, `CommentaryEntry`, `StudyUnit`). The provider layer produces exactly those objects; `source_provider`, `source_version` and `source_reference` are always populated.

---

## 11. Local Caching

```
data/cache/
├── tanakh/
│   ├── genesis.json          {"index": "Genesis", "version_title": "...", "fetched_at": "...",
│   ├── exodus.json            "source": "api|export", "license": "...", "text": [[...]]}
│   └── …
└── rashi/
    ├── genesis.json
    └── …
```

Requirements: use the cache by default · offline builds work once cached · explicit refresh · each file records `fetched_at`, `source`, `version_title`, `license` · a cache file whose `version_title` differs from config is treated as missing (never mixed silently).

---

## 12. Cache Refresh (CLI)

```
python -m tanakh_epub fetch                     # fill cache, skip existing
python -m tanakh_epub fetch --book Genesis --refresh
python -m tanakh_epub fetch --refresh-all
```

Default behaviour: use cache if available.

---

## 13. Source Attribution Page (מקורות)

The EPUB contains a final XHTML page `sources.xhtml`, in Hebrew, listing: content provider (ספריא / Sefaria) · exact version title and license for the Tanakh text · exact version title and license for each commentator · fonts and their licenses · build date.

Example lead-in:

```
הטקסטים בפרסום זה מבוססים על נתונים שהתקבלו מספריא (Sefaria).
גרסאות הטקסט והרישיונות מפורטים להלן.
```

The exact wording of each attribution follows the license of the version used (e.g. CC BY-SA requires naming the source and license).

---

## 14. License Metadata and Source Report

For every source used, store provider · version title · language · license · source URL. The build writes `output/SOURCES_AND_LICENSES.md` from the same data that feeds `sources.xhtml`.

---

## 15. Build Manifest

Every build writes `output/build_manifest.json` (and embeds a copy in the EPUB as `OEBPS/build_manifest.json`):

```json
{
  "build_date": "2026-09-11T10:00:00Z",
  "generator_version": "0.1.0",
  "config_hash": "sha256:…",
  "content_provider": "Sefaria",
  "tanakh_version": "…",
  "commentary_versions": {"Rashi": "…"},
  "fonts": {"biblical": "…", "rashi": "…"},
  "books": ["Genesis", "Exodus"],
  "delivery_target": "calibre-kfx"
}
```

The manifest must allow reproducing the exact build from the cache.

---

## 16. Reference Normalization

Internal: English canonical references using Sefaria titles from `config/books.yaml` (`Genesis 1:1`, `I Samuel 3:14`).
Rendered: Hebrew only (`בראשית א׳:א׳`, `שמואל א׳ ג׳:י״ד`).

The rendering layer is the only place where English references become Hebrew.

---

## 17. Error Handling

The provider handles network failure · timeout · invalid JSON · missing version · missing index · missing chapter/verse · missing commentary index · rate limits · malformed HTML.

Rules: retry transient failures with backoff · never silently generate an incomplete book · log every missing item · fail clearly when required content is unavailable:

```
ERROR: Could not retrieve "Rashi on Genesis" (version "…"): HTTP timeout after 3 retries
```

---

## 18. Data Completeness Validation

Run by `python -m tanakh_epub validate` and before every build:

```
VALIDATION REPORT  (tanakh version: …, Rashi version: …)
Books:            39 / 39
Chapters:        929 / 929
Verses:       23,206 / 23,206
Empty verses:      0
Unknown markup:    0
Books with Rashi: N / 39   (books without: …)
Verses with Rashi: X
Verses without:    Y
Chapter files > 300 KB: 0
```

Expected counts are computed from the fetched dataset (chapter/verse counts per book from the Sefaria index/shape), not hard-coded.

---

## 19. Testing Strategy

Integration test (network, marked `@pytest.mark.network`, skipped offline): fetch `Genesis` and `Rashi on Genesis` for the configured versions and assert: Hebrew text retrieved · `[chapter][verse]` structure · ניקוד and טעמים present in 1:1 · version recorded · Rashi retrieved · Genesis 1:1 has multiple entries · references map correctly · markup inventory contains only known patterns.

Unit tests run against a checked-in fixture (`tests/fixtures/genesis_1.json`, `tests/fixtures/rashi_genesis_1.json`) captured from the real data so the rest of the suite is offline.

Then build `Genesis_Chapter_1.epub` and put it on the Paperwhite (SPEC.md §34). Only after that passes on the device does the generator process the complete Tanakh.

---

## 20. Core Requirement

Sefaria is the required source. The EPUB generator operates on the normalized internal model, never on raw Sefaria responses. This gives: a trusted source · reproducible local builds · cached, polite API use · clean rendering · exact source versions recorded in the book itself.

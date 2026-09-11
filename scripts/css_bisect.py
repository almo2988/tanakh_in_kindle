#!/usr/bin/env python3
"""Find which part of the production stylesheet the Kindle chokes on.

    python3 scripts/css_bisect.py
    python -m tanakh_epub check output/CSS_Bisect.epub

Round 4 of the device loop established the useful pair of facts: the small, ASCII-only
stylesheet in `font_diagnostic.py` applies both embedded fonts correctly on the Paperwhite,
and the production stylesheet does not — same fonts, same media types, same `@font-face`
family names, same delivery path. So the fault is in the production CSS (or in what the
converter does with it), not in the fonts, the manifest or the pipeline.

This builds one book whose pages all carry the **same real chapter markup** — the actual
`<section class="study-unit">` the generator emits for בראשית א׳:א׳ — and differ only in
which stylesheet they link. Each stylesheet is the production one with a single suspect
removed.

The tell is the commentary, and it needs no close reading: `.commentary-text` is the only
rule that asks for Rashi script. If it survives, the commentary is slanted and cursive; if
it is dropped, the commentary inherits the body font and comes out square. One page per
suspect, one sideload, and the pages that come out right name the culprit.
"""

from __future__ import annotations

import html
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tanakh_epub.books import default_books  # noqa: E402
from tanakh_epub.config import load_config  # noqa: E402
from tanakh_epub.epub.builder import MIMETYPE, OEBPS, ZIP_TIMESTAMP  # noqa: E402
from tanakh_epub.processing.study_units import ChapterSelection, load_chapters  # noqa: E402
from tanakh_epub.providers.local import LocalProvider  # noqa: E402
from tanakh_epub.rendering.css import font_media_type, render_css  # noqa: E402
from tanakh_epub.rendering.html_renderer import ChapterRenderer  # noqa: E402

COMMENT = re.compile(r"/\*.*?\*/", re.S)


def strip_comments(css: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", COMMENT.sub("", css))


def asciify_comments(css: str) -> str:
    """Keep every comment, but drop the non-ASCII characters inside them."""

    def scrub(match: re.Match[str]) -> str:
        return "".join(c if ord(c) < 128 else "?" for c in match.group(0))

    return COMMENT.sub(scrub, css)


def drop_declarations(css: str, properties: tuple[str, ...]) -> str:
    keep = [
        line
        for line in css.splitlines()
        if not any(re.match(rf"\s*{re.escape(p)}\s*:", line) for p in properties)
    ]
    return "\n".join(keep)


def minimal_css(config) -> str:
    """Only what is needed to put the two fonts on the page — the shape already proven to
    work in font_diagnostic.py, applied to the real markup."""
    biblical, rashi = config.biblical_font, config.rashi_font
    return f"""@charset "utf-8";

@font-face {{
  font-family: "{biblical.family}";
  font-weight: normal; font-style: normal;
  src: url("../fonts/biblical_hebrew.ttf") format("truetype");
}}
@font-face {{
  font-family: "{rashi.family}";
  font-weight: normal; font-style: normal;
  src: url("../fonts/rashi.ttf") format("truetype");
}}

body {{ text-align: right; font-family: "{biblical.family}", serif; }}
.biblical-text {{ font-family: "{biblical.family}", serif; font-size: 1.25em; }}
.verse-number {{ font-size: 0.75em; }}
.commentary-divider {{ font-size: 0.85em; text-align: center; }}
.commentary-text {{ font-family: "{rashi.family}", "{biblical.family}", serif; font-size: 0.9em; }}
.dibur-hamatchil {{ font-family: "{biblical.family}", serif; }}
"""


def variants(config) -> list[tuple[str, str, str]]:
    """(slug, what it proves, css)"""
    production = render_css(config)
    return [
        ("a-production", "the production stylesheet, unchanged (expected to FAIL)", production),
        ("b-nocomments", "production minus every comment", strip_comments(production)),
        (
            "c-asciicomments",
            "production with comments kept but their non-ASCII stripped",
            asciify_comments(production),
        ),
        (
            "d-nobreaks",
            "production minus break-inside / break-before / break-after",
            drop_declarations(
                production,
                (
                    "break-inside",
                    "page-break-inside",
                    "break-after",
                    "page-break-after",
                    "break-before",
                    "page-break-before",
                ),
            ),
        ),
        (
            "e-noborders",
            'production minus the "thin solid" borders on the divider',
            drop_declarations(production, ("border-top", "border-bottom")),
        ),
        ("f-minimal", "fonts and sizes only, nothing else (expected to PASS)", minimal_css(config)),
    ]


def sample_markup() -> str:
    config, books = load_config(), default_books()
    chapters, _, _ = load_chapters(
        LocalProvider(), config, [ChapterSelection(books.by_title("Genesis"), (1,), max_verse=1)]
    )
    rendered = ChapterRenderer(config, books).render(chapters[0], book_start=False)
    match = re.search(r'<section class="study-unit">.*?\n    </section>', rendered.xhtml, re.S)
    if match is None:
        raise SystemExit("could not find a study unit in the rendered chapter")
    return match.group(0)


def page(slug: str, label: str, index: int, total: int, markup: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <title>{index} / {total}</title>
  <link rel="stylesheet" type="text/css" href="../styles/{slug}.css"/>
</head>
<body dir="rtl">
  <section epub:type="chapter" id="page-{index}">
    <p dir="ltr" lang="en" xml:lang="en" style="font-family: serif; font-size: 0.75em; text-align: left;">
      PAGE {index} of {total} &#8212; {html.escape(label)}.
      Is the commentary below in Rashi script (slanted, cursive) or square?
    </p>
{markup}
  </section>
</body>
</html>
"""


def build() -> Path:
    config = load_config()
    markup = sample_markup()
    cases = variants(config)
    total = len(cases)

    manifest, spine, nav_items, files = [], [], [], {}
    for index, (slug, label, css) in enumerate(cases, start=1):
        files[f"{OEBPS}/styles/{slug}.css"] = css.encode("utf-8")
        files[f"{OEBPS}/text/{slug}.xhtml"] = page(slug, label, index, total, markup).encode(
            "utf-8"
        )
        manifest.append(
            f'    <item id="css-{slug}" href="styles/{slug}.css" media-type="text/css"/>'
        )
        manifest.append(
            f'    <item id="p-{slug}" href="text/{slug}.xhtml" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'    <itemref idref="p-{slug}"/>')
        nav_items.append(
            f'      <li><a href="text/{slug}.xhtml">{index}. {html.escape(label)}</a></li>'
        )

    biblical, rashi = config.biblical_font, config.rashi_font
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         unique-identifier="book-id" xml:lang="he" dir="rtl">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:00000000-0000-5000-8000-0000000c55b1</dc:identifier>
    <dc:title>בדיקת גיליון סגנונות</dc:title>
    <dc:language>he</dc:language>
    <meta property="dcterms:modified">{datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="f1" href="fonts/biblical_hebrew.ttf" media-type="{font_media_type(biblical.suffix)}"/>
    <item id="f2" href="fonts/rashi.ttf" media-type="{font_media_type(rashi.suffix)}"/>
{chr(10).join(manifest)}
  </manifest>
  <spine page-progression-direction="rtl">
{chr(10).join(spine)}
  </spine>
</package>
"""

    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head><meta charset="utf-8"/><title>תוכן</title></head>
<body dir="rtl">
  <nav epub:type="toc" id="toc">
    <ol>
{chr(10).join(nav_items)}
    </ol>
  </nav>
</body>
</html>
"""

    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    output = ROOT / "output" / "CSS_Bisect.epub"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        info = zipfile.ZipInfo("mimetype", date_time=ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, MIMETYPE)

        def write(name: str, payload: bytes) -> None:
            entry = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, payload)

        write("META-INF/container.xml", container.encode())
        write(f"{OEBPS}/content.opf", opf.encode("utf-8"))
        write(f"{OEBPS}/nav.xhtml", nav.encode("utf-8"))
        write(f"{OEBPS}/fonts/biblical_hebrew.ttf", biblical.file.read_bytes())
        write(f"{OEBPS}/fonts/rashi.ttf", rashi.file.read_bytes())
        for name, payload in files.items():
            write(name, payload)

    print(f"{output}  ({output.stat().st_size / 1024:.0f} KB)")
    for index, (slug, label, css) in enumerate(cases, start=1):
        non_ascii = sum(1 for c in css if ord(c) > 127)
        print(
            f"  {index}. {slug:16s} {len(css.encode()):5d} bytes, "
            f"{non_ascii:3d} non-ASCII chars — {label}"
        )
    return output


if __name__ == "__main__":
    build()

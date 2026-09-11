#!/usr/bin/env python3
"""Two pages, four paragraphs, two yes/no questions: can this Kindle use two fonts at once?

    python3 scripts/font_diagnostic.py
    python -m tanakh_epub check output/Font_Diagnostic.epub

Rounds 2-6 cleared the fonts, the manifest, the media types, the delivery path, the
stylesheet's comments, its non-ASCII characters, its break properties, its borders and its
size. Round 6 then produced the fact that reframes all of it: Hebrew rendered in an
embedded font while **Bookerly** was the selected font and "Publisher Font" was not even
offered. Bookerly has no Hebrew glyphs, so the device was falling back to an embedded font
to draw Hebrew at all. Font choice for Hebrew may therefore never have been ours to make
through CSS -- the renderer picks one font that covers the script and uses it.

If that is what is happening, no stylesheet can give the commentary its own face, and the
project has to stop trying. This asks that one question directly, in the smallest form that
can answer it.

Earlier diagnostics asked for a per-line reading of ten mechanisms, which is more than a
device test should demand of anyone and is how round 4's flawed result slipped through.
This asks two questions whose answers are unmistakable: on each page, do the two paragraphs
look the *same* or *different*?

    same on both pages  -> one font for all Hebrew in the book; CSS cannot change it
    different on both   -> two fonts work per element, and the fault is elsewhere

Rashi script against square Hebrew needs no font expertise to tell apart, and the
paragraphs sit directly above each other for comparison.

This is a diagnostic, not reading content, so its labels are in English; the Hebrew-only
rule (SPEC §6) governs the book being produced, not the instrument measuring it.
"""

from __future__ import annotations

import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tanakh_epub.config import load_config  # noqa: E402
from tanakh_epub.epub.builder import MIMETYPE, OEBPS, ZIP_TIMESTAMP  # noqa: E402
from tanakh_epub.rendering.css import font_media_type  # noqa: E402

SAMPLE = "אָמַר רַבִּי יִצְחָק לֹא הָיָה צָרִיךְ לְהַתְחִיל אֶת הַתּוֹרָה"


def internal_family(path: Path) -> str:
    from fontTools.ttLib import TTFont

    for record in TTFont(path)["name"].names:
        if record.nameID == 1:
            try:
                return record.toUnicode()
            except UnicodeDecodeError:
                continue
    raise SystemExit(f"{path} has no family name")


def stylesheet(body_family: str, other_family: str) -> str:
    return f"""@charset "utf-8";

@font-face {{
  font-family: "Taamey Frank CLM";
  font-weight: normal; font-style: normal;
  src: url("../fonts/biblical.ttf") format("truetype");
}}
@font-face {{
  font-family: "Noto Rashi Hebrew";
  font-weight: normal; font-style: normal;
  src: url("../fonts/rashi.ttf") format("truetype");
}}

body {{ text-align: right; font-family: "{body_family}", serif; }}
.label {{ font-family: serif; font-size: 0.8em; text-align: left; margin: 0 0 0.6em 0; }}
.a {{ font-size: 1.3em; line-height: 1.9; margin: 0 0 1.2em 0; }}
.b {{ font-size: 1.3em; line-height: 1.9; margin: 0; font-family: "{other_family}", serif; }}
"""


def page(number: int, sheet: str, body_label: str, other_label: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <title>Page {number}</title>
  <link rel="stylesheet" type="text/css" href="../styles/{sheet}.css"/>
</head>
<body dir="rtl">
  <section id="page-{number}" epub:type="chapter">
    <p class="label" dir="ltr" lang="en" xml:lang="en">PAGE {number} of 2.
      The two paragraphs below are the same words. The first asks for no font and takes the
      page default, which is {body_label}. The second asks for {other_label}.
      <strong>Do they look the same as each other, or different?</strong>
      That is the only thing to report. Ignore which font is selected in the Aa menu.</p>
    <p class="a" dir="rtl">{SAMPLE}</p>
    <p class="b" dir="rtl">{SAMPLE}</p>
  </section>
</body>
</html>
"""


def build() -> Path:
    config = load_config()
    biblical, rashi = config.biblical_font, config.rashi_font
    square = internal_family(biblical.file)
    cursive = internal_family(rashi.file)

    sheets = {
        "one": stylesheet(body_family=cursive, other_family=square),
        "two": stylesheet(body_family=square, other_family=cursive),
    }
    pages = {
        "one": page(1, "one", "RASHI SCRIPT (slanted)", "the SQUARE font"),
        "two": page(2, "two", "the SQUARE font", "RASHI SCRIPT (slanted)"),
    }

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         unique-identifier="book-id" xml:lang="he" dir="rtl">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:00000000-0000-5000-8000-000000000f0f</dc:identifier>
    <dc:title>שני גופנים</dc:title>
    <dc:language>he</dc:language>
    <meta property="dcterms:modified">{datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="p1" href="text/one.xhtml" media-type="application/xhtml+xml"/>
    <item id="p2" href="text/two.xhtml" media-type="application/xhtml+xml"/>
    <item id="c1" href="styles/one.css" media-type="text/css"/>
    <item id="c2" href="styles/two.css" media-type="text/css"/>
    <item id="f1" href="fonts/biblical.ttf" media-type="{font_media_type(biblical.suffix)}"/>
    <item id="f2" href="fonts/rashi.ttf" media-type="{font_media_type(rashi.suffix)}"/>
  </manifest>
  <spine page-progression-direction="rtl">
    <itemref idref="p1"/>
    <itemref idref="p2"/>
  </spine>
</package>
"""

    nav = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head><meta charset="utf-8"/><title>תוכן</title></head>
<body dir="rtl">
  <nav epub:type="toc" id="toc"><ol>
    <li><a href="text/one.xhtml">עמוד 1</a></li>
    <li><a href="text/two.xhtml">עמוד 2</a></li>
  </ol></nav>
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

    output = ROOT / "output" / "Font_Diagnostic.epub"
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
        for key, css in sheets.items():
            write(f"{OEBPS}/styles/{key}.css", css.encode("utf-8"))
        for key, markup in pages.items():
            write(f"{OEBPS}/text/{key}.xhtml", markup.encode("utf-8"))
        write(f"{OEBPS}/fonts/biblical.ttf", biblical.file.read_bytes())
        write(f"{OEBPS}/fonts/rashi.ttf", rashi.file.read_bytes())

    print(f"{output}  ({output.stat().st_size / 1024:.0f} KB)")
    print(f'  page 1: default = "{cursive}", second paragraph asks for "{square}"')
    print(f'  page 2: default = "{square}", second paragraph asks for "{cursive}"')
    print("  Report only: on each page, do the two paragraphs look the same or different?")
    return output


if __name__ == "__main__":
    build()

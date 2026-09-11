#!/usr/bin/env python3
"""Build a one-page EPUB that isolates *why* Kindle is ignoring the embedded fonts.

    python3 scripts/font_diagnostic.py
    python -m tanakh_epub check output/Font_Diagnostic.epub

Round 2 of the device test left two live hypotheses and no way to choose between them
from here: either the Kindle will not match a `@font-face` family name that differs from
the font's own internal name, or its converter drops font declarations attached to some
kinds of element. Both produce exactly the symptom reported — "Publisher Font" offered,
and the wrong glyphs on screen.

Rather than ship another speculative fix and wait a round to find out, this builds a book
whose every line applies the *same* font by a *different* mechanism. One look at the
device says which mechanisms survive.

Each line is set in Rashi script on purpose: Rashi script against any square fallback is
unmistakable at a glance, which a subtler pairing would not be. Line 0 is the control —
no font-family at all — so the reader knows what "Kindle default" looks like.

This is a diagnostic, not reading content, so its labels are in English; the Hebrew-only
rule (SPEC §6) governs the book being produced, not the instrument measuring it.
"""

from __future__ import annotations

import html
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tanakh_epub.config import load_config  # noqa: E402
from tanakh_epub.epub.builder import MIMETYPE, OEBPS, ZIP_TIMESTAMP  # noqa: E402
from tanakh_epub.rendering.css import font_media_type  # noqa: E402

SAMPLE = "אָמַר רַבִּי יִצְחָק לֹא הָיָה צָרִיךְ לְהַתְחִיל אֶת הַתּוֹרָה"
"""The opening of Rashi on בראשית א׳:א׳ — real content, so the answer is about real text."""

# (id, label, how the font is applied, the CSS rule or inline style)
CASES = [
    ("0", "CONTROL — no font-family at all", "control", ""),
    ("1", "class on a <p>, family = the font's own internal name", "class", "rashi-real"),
    ("2", "class on a <p>, family = an invented name", "class", "rashi-alias"),
    ("3", "class on a <span> inside a <p>", "span", "rashi-real"),
    ("4", "style attribute on the <p>, no class", "inline", ""),
    ("5", "inherited from <body>, not set on the element", "inherit", ""),
    ("6", "bold, with only a regular face embedded", "class", "rashi-bold"),
    ("7", "the biblical font, internal name (should look square)", "class", "biblical-real"),
]


def build() -> Path:
    config = load_config()
    biblical, rashi = config.biblical_font, config.rashi_font

    # The real family names, read from the files rather than trusted from config.
    from fontTools.ttLib import TTFont

    def internal_family(path: Path) -> str:
        for record in TTFont(path)["name"].names:
            if record.nameID == 1:
                try:
                    return record.toUnicode()
                except UnicodeDecodeError:
                    continue
        raise SystemExit(f"{path} has no family name")

    real_biblical = internal_family(biblical.file)
    real_rashi = internal_family(rashi.file)

    css = f"""@charset "utf-8";

@font-face {{
  font-family: "{real_biblical}";
  font-weight: normal; font-style: normal;
  src: url("../fonts/biblical.ttf") format("truetype");
}}
@font-face {{
  font-family: "{real_rashi}";
  font-weight: normal; font-style: normal;
  src: url("../fonts/rashi.ttf") format("truetype");
}}
@font-face {{
  font-family: "InventedRashiAlias";
  font-weight: normal; font-style: normal;
  src: url("../fonts/rashi.ttf") format("truetype");
}}

body {{ text-align: right; font-family: "{real_rashi}", serif; }}
.label {{ font-family: serif; font-size: 0.7em; text-align: left; margin: 1.1em 0 0.1em 0; }}
.sample {{ font-size: 1.1em; line-height: 1.8; margin: 0; }}
.control {{ font-family: serif; }}
.rashi-real {{ font-family: "{real_rashi}", serif; }}
.rashi-alias {{ font-family: "InventedRashiAlias", serif; }}
.rashi-bold {{ font-family: "{real_rashi}", serif; font-weight: bold; }}
.biblical-real {{ font-family: "{real_biblical}", serif; }}
"""

    rows = []
    for number, label, mechanism, css_class in CASES:
        classes = ["sample"]
        style = ""
        body = SAMPLE
        if mechanism == "span":
            body = f'<span class="{css_class}">{SAMPLE}</span>'
        elif mechanism == "inline":
            style = f' style="font-family: &#34;{real_rashi}&#34;, serif;"'
        elif mechanism == "class":
            classes.append(css_class)
        # "inherit" deliberately adds nothing: it must pick the family up from <body>.
        rows.append(
            f'    <p class="label" dir="ltr" lang="en" xml:lang="en">{number} — {html.escape(label)}</p>\n'
            f'    <p class="{" ".join(classes)}"{style} dir="rtl">{body}</p>'
        )

    page = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <title>Font diagnostic</title>
  <link rel="stylesheet" type="text/css" href="../styles/main.css"/>
</head>
<body dir="rtl">
  <section id="diagnostic" epub:type="chapter">
    <p class="label" dir="ltr" lang="en" xml:lang="en">Select Aa &#8594; Font &#8594; Publisher Font first.
       Lines 1-6 should all be in Rashi script (slanted, cursive). Line 0 and line 7 should be square.
       Report which line numbers are NOT in the expected font.</p>
{chr(10).join(rows)}
  </section>
</body>
</html>
"""

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         unique-identifier="book-id" xml:lang="he" dir="rtl">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:00000000-0000-5000-8000-000000000f0d</dc:identifier>
    <dc:title>בדיקת גופנים</dc:title>
    <dc:language>he</dc:language>
    <meta property="dcterms:modified">{datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="page" href="text/diagnostic.xhtml" media-type="application/xhtml+xml"/>
    <item id="css" href="styles/main.css" media-type="text/css"/>
    <item id="f1" href="fonts/biblical.ttf" media-type="{font_media_type(biblical.suffix)}"/>
    <item id="f2" href="fonts/rashi.ttf" media-type="{font_media_type(rashi.suffix)}"/>
  </manifest>
  <spine page-progression-direction="rtl">
    <itemref idref="page"/>
  </spine>
</package>
"""

    nav = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head><meta charset="utf-8"/><title>תוכן</title></head>
<body dir="rtl">
  <nav epub:type="toc" id="toc"><ol><li><a href="text/diagnostic.xhtml">בדיקת גופנים</a></li></ol></nav>
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

    import zipfile

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
        write(f"{OEBPS}/content.opf", opf.encode())
        write(f"{OEBPS}/nav.xhtml", nav.encode())
        write(f"{OEBPS}/styles/main.css", css.encode())
        write(f"{OEBPS}/text/diagnostic.xhtml", page.encode())
        write(f"{OEBPS}/fonts/biblical.ttf", biblical.file.read_bytes())
        write(f"{OEBPS}/fonts/rashi.ttf", rashi.file.read_bytes())

    print(f"{output}  ({output.stat().st_size / 1024:.0f} KB)")
    print(f'  biblical family in the file: "{real_biblical}"')
    print(f'  rashi family in the file:    "{real_rashi}"')
    return output


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""Find out whether this Kindle will apply a *second* embedded font at all.

    python3 scripts/font_diagnostic.py
    python -m tanakh_epub check output/Font_Diagnostic.epub

Rounds 2–5 of the device loop cleared the fonts, the manifest, the media types and the
delivery path, then cleared the stylesheet's comments, break properties and borders too —
all six pages of `css_bisect.py` came out square, the minimal one included. What survived
that elimination is a single difference between the book that works on the device and every
one that does not:

    works:  body { font-family: "Noto Rashi Hebrew"; }      <- set on body
    fails:  .commentary-text { font-family: "Noto Rashi Hebrew"; }   <- set on a class

So the question is no longer "which font" or "which stylesheet" but **whether a second
embedded font can be applied to part of a book at all**, and if so, by what mechanism.

Every line below tries to reach the Rashi font from a body whose font is the *biblical*
one. Any line that comes out slanted and cursive is a mechanism that works; any line that
comes out square is one that does not.

Two lines carry the weight:

* **Line 7** asks for `font-size: 2em` and the Rashi font in the same class rule. Big and
  cursive means everything works. **Big and square means class rules are applied but
  `font-family` alone is being overridden** — i.e. the device forces one font per book, and
  no amount of CSS will give the commentary its own. Small and square means class rules are
  dropped wholesale.
* **Line 9** asks for plain `serif`, no embedded font. If it looks different from line 0,
  the biblical font really is being applied at body level and the embedding works; if they
  look identical, even that is not landing.

This is a diagnostic, not reading content, so its labels are in English; the Hebrew-only
rule (SPEC §6) governs the book being produced, not the instrument measuring it.
"""

from __future__ import annotations

import html
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
"""The opening of Rashi on בראשית א׳:א׳ — real content, so the answer is about real text."""

# (number, expectation if everything works, label, element, how the font is applied)
CASES = [
    ("0", "SQUARE", "control - nothing set, inherits the biblical font from <body>", "p", None),
    ("1", "RASHI", "class on a <p>", "p", "class"),
    ("2", "RASHI", "class on a <span> inside a <p>", "p", "span-class"),
    ("3", "RASHI", "style attribute on the <p>", "p", "inline"),
    ("4", "RASHI", "style attribute on a <span> inside a <p>", "p", "span-inline"),
    ("5", "RASHI", "id selector", "p", "id"),
    ("6", "RASHI", "element selector on <blockquote>", "blockquote", "element"),
    ("7", "BIG + RASHI", "class setting font-size 2em AND the Rashi font", "p", "big-rashi"),
    ("8", "BIG + SQUARE", "class setting font-size 2em only, no font change", "p", "big-only"),
    ("9", "KINDLE DEFAULT", "class setting plain serif - no embedded font at all", "p", "noembed"),
]


def internal_family(path: Path) -> str:
    from fontTools.ttLib import TTFont

    for record in TTFont(path)["name"].names:
        if record.nameID == 1:
            try:
                return record.toUnicode()
            except UnicodeDecodeError:
                continue
    raise SystemExit(f"{path} has no family name")


def build() -> Path:
    config = load_config()
    biblical, rashi = config.biblical_font, config.rashi_font
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

body {{ text-align: right; font-family: "{real_biblical}", serif; }}
.label {{ font-family: serif; font-size: 0.7em; text-align: left; margin: 1.2em 0 0.1em 0; }}
.sample {{ font-size: 1.1em; line-height: 1.8; margin: 0; }}

.t1 {{ font-family: "{real_rashi}", serif; }}
.t2 {{ font-family: "{real_rashi}", serif; }}
#t5 {{ font-family: "{real_rashi}", serif; }}
blockquote {{ font-family: "{real_rashi}", serif; margin: 0; }}
.t7 {{ font-size: 2em; font-family: "{real_rashi}", serif; }}
.t8 {{ font-size: 2em; }}
.t9 {{ font-family: serif; }}
"""

    css_page_two = f"""@charset "utf-8";

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

body {{ text-align: right; font-family: "{real_rashi}", serif; }}
.label {{ font-family: serif; font-size: 0.7em; text-align: left; margin: 1.2em 0 0.1em 0; }}
.sample {{ font-size: 1.1em; line-height: 1.8; margin: 0; }}
"""

    rows = []
    for number, expectation, label, element, mechanism in CASES:
        classes, attrs, body = ["sample"], "", SAMPLE
        if mechanism == "class":
            classes.append("t1")
        elif mechanism == "span-class":
            body = f'<span class="t2">{SAMPLE}</span>'
        elif mechanism == "inline":
            attrs = f' style="font-family: &#34;{real_rashi}&#34;, serif;"'
        elif mechanism == "span-inline":
            body = f'<span style="font-family: &#34;{real_rashi}&#34;, serif;">{SAMPLE}</span>'
        elif mechanism == "id":
            attrs = ' id="t5"'
        elif mechanism == "big-rashi":
            classes.append("t7")
        elif mechanism == "big-only":
            classes.append("t8")
        elif mechanism == "noembed":
            classes.append("t9")
        rows.append(
            f'    <p class="label" dir="ltr" lang="en" xml:lang="en">'
            f"{number} &#8212; expect {expectation} &#8212; {html.escape(label)}</p>\n"
            f'    <{element} class="{" ".join(classes)}"{attrs} dir="rtl">{body}</{element}>'
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
      For each numbered line, report whether it is RASHI (slanted, cursive) or SQUARE, and for
      lines 7 and 8 whether the text is BIG. Line 0 and line 9 are the reference points:
      if they look different from each other, the biblical font is being applied.</p>
{chr(10).join(rows)}
  </section>
</body>
</html>
"""

    page_two = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="he" lang="he" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <title>Page 2</title>
  <link rel="stylesheet" type="text/css" href="../styles/page2.css"/>
</head>
<body dir="rtl">
  <section id="page-two" epub:type="chapter">
    <p class="label" dir="ltr" lang="en" xml:lang="en">PAGE 2 &#8212; expect RASHI &#8212; same book, same
      two embedded fonts, but this page's stylesheet puts the Rashi font on &lt;body&gt; instead of on a
      class. If this is Rashi while every line on page 1 was square, font-family is only honoured on
      &lt;body&gt;. If this is square too, the device is using one embedded font per book and a second
      one is simply not possible.</p>
    <p class="sample" dir="rtl">{SAMPLE}</p>
  </section>
</body>
</html>
"""

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         unique-identifier="book-id" xml:lang="he" dir="rtl">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:00000000-0000-5000-8000-000000000f0e</dc:identifier>
    <dc:title>בדיקת גופנים</dc:title>
    <dc:language>he</dc:language>
    <meta property="dcterms:modified">{datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="page" href="text/diagnostic.xhtml" media-type="application/xhtml+xml"/>
    <item id="page2" href="text/page2.xhtml" media-type="application/xhtml+xml"/>
    <item id="css" href="styles/main.css" media-type="text/css"/>
    <item id="css2" href="styles/page2.css" media-type="text/css"/>
    <item id="f1" href="fonts/biblical.ttf" media-type="{font_media_type(biblical.suffix)}"/>
    <item id="f2" href="fonts/rashi.ttf" media-type="{font_media_type(rashi.suffix)}"/>
  </manifest>
  <spine page-progression-direction="rtl">
    <itemref idref="page"/>
    <itemref idref="page2"/>
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
    <li><a href="text/diagnostic.xhtml">עמוד 1</a></li>
    <li><a href="text/page2.xhtml">עמוד 2</a></li>
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
        write(f"{OEBPS}/styles/main.css", css.encode("utf-8"))
        write(f"{OEBPS}/text/diagnostic.xhtml", page.encode("utf-8"))
        write(f"{OEBPS}/styles/page2.css", css_page_two.encode("utf-8"))
        write(f"{OEBPS}/text/page2.xhtml", page_two.encode("utf-8"))
        write(f"{OEBPS}/fonts/biblical.ttf", biblical.file.read_bytes())
        write(f"{OEBPS}/fonts/rashi.ttf", rashi.file.read_bytes())

    print(f"{output}  ({output.stat().st_size / 1024:.0f} KB)")
    print(f'  body font is the BIBLICAL one: "{real_biblical}"')
    print(f'  every line tries to reach:     "{real_rashi}"')
    for number, expectation, label, _, _ in CASES:
        print(f"  {number}. expect {expectation:16s} {label}")
    print("  PAGE 2. expect RASHI          the Rashi font on <body> of a second page")
    return output


if __name__ == "__main__":
    build()

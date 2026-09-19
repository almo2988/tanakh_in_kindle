"""SPEC.md §12, §13, §14, §17, §18, §22, §23, §24, §26 — the rendered XHTML and CSS."""

from __future__ import annotations

import re
from xml.etree import ElementTree

import pytest

from tanakh_epub.models import CommentaryEntry
from tanakh_epub.rendering.css import render_css
from tanakh_epub.rendering.html_renderer import ChapterRenderer, entry_id, hebrew_date

XHTML = "{http://www.w3.org/1999/xhtml}"


@pytest.fixture(scope="module")
def rendered(config, books, genesis_chapter_1):
    chapters, _, _ = genesis_chapter_1
    return ChapterRenderer(config, books).render_all(chapters)[0]


@pytest.fixture(scope="module")
def tree(rendered):
    return ElementTree.fromstring(rendered.xhtml)


def _class(element) -> str:
    return element.get("class", "")


def _find_all(tree, tag, css_class):
    return [e for e in tree.iter(f"{XHTML}{tag}") if css_class in _class(e).split()]


# ---- RTL ----------------------------------------------------------------


def test_root_element_declares_hebrew_and_rtl(tree) -> None:
    assert tree.get("lang") == "he"
    assert tree.get("{http://www.w3.org/XML/1998/namespace}lang") == "he"
    assert tree.get("dir") == "rtl"


def test_body_declares_rtl(tree) -> None:
    body = tree.find(f"{XHTML}body")
    assert body.get("dir") == "rtl"


# ---- Structure ----------------------------------------------------------


def test_one_file_per_chapter_named_by_slug(rendered) -> None:
    assert rendered.filename == "genesis-001.xhtml"
    assert rendered.anchor == "chapter-1"


def test_book_heading_only_on_the_first_chapter_of_a_book(config, books, genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    renderer = ChapterRenderer(config, books)
    first = renderer.render(chapters[0], book_start=True)
    later = renderer.render(chapters[0], book_start=False)
    assert 'class="book-heading"' in first.xhtml
    assert "book-heading" not in later.xhtml
    assert 'class="chapter-heading"' in later.xhtml


def test_headings_are_hebrew(tree) -> None:
    h1 = tree.find(f".//{XHTML}h1")
    h2 = tree.find(f".//{XHTML}h2")
    assert h1.text == "בראשית"
    assert h2.text == "פרק א׳"


def test_verse_markup_matches_the_spec(tree) -> None:
    verses = _find_all(tree, "div", "verse")
    assert len(verses) == 10
    first = verses[0]
    assert first.get("id") == "genesis-1-1"
    spans = list(first)
    assert _class(spans[0]) == "verse-number"
    assert spans[0].text == "א׳"
    assert _class(spans[1]) == "biblical-text"


def test_verse_ids_are_stable_and_sequential(tree) -> None:
    ids = [v.get("id") for v in _find_all(tree, "div", "verse")]
    assert ids == [f"genesis-1-{n}" for n in range(1, 11)]


def test_commentary_follows_its_verse_inside_the_study_unit(tree) -> None:
    units = _find_all(tree, "section", "study-unit")
    assert len(units) == 10
    for unit in units:
        keep = unit.find(f"{XHTML}div[@class='keep-together']")
        assert keep is not None
        assert _class(next(iter(keep))) == "verse"


def test_keep_together_holds_verse_divider_and_first_entry_only(tree) -> None:
    """SPEC §13: wrapping the whole unit would leave blank pages in readers that honour
    the hint, and Rashi on א׳:א׳ alone runs for several screens."""
    first_unit = _find_all(tree, "section", "study-unit")[0]
    keep = first_unit.find(f"{XHTML}div[@class='keep-together']")
    classes = [_class(child).split()[0] for child in keep]
    assert classes == ["verse", "commentary-divider", "commentary-entry"]
    rest = first_unit.find(f"{XHTML}section")
    assert "commentary" in _class(rest)
    assert len(list(rest)) == 2, "entries 2 and 3 belong outside the keep-together block"


def test_divider_label_comes_from_config_not_hard_coded(tree, config) -> None:
    dividers = _find_all(tree, "div", "commentary-divider")
    assert dividers
    for divider in dividers:
        assert divider.text == config.commentator("Rashi").hebrew == "רש״י"
        assert "rashi-divider" in _class(divider)


def test_commentary_entries_keep_source_order(tree) -> None:
    ids = [
        e.get("id")
        for e in _find_all(tree, "div", "commentary-entry")
        if e.get("id", "").startswith("rashi-genesis-1-1-")
    ]
    assert ids == ["rashi-genesis-1-1-1", "rashi-genesis-1-1-2", "rashi-genesis-1-1-3"]


def test_entry_id_uses_the_book_slug_not_the_sefaria_title(books) -> None:
    entry = CommentaryEntry(
        commentator="Rashi",
        book="I Samuel",
        chapter=1,
        verse=2,
        entry_number=3,
        dibur_hamatchil=None,
        text="",
        source_provider="test",
        source_version="test",
        source_reference="test",
    )
    assert entry_id("rashi", books.by_title("I Samuel"), entry) == "rashi-samuel-1-1-2-3"


def test_verse_without_rashi_renders_no_commentary_block(tree) -> None:
    """בראשית א׳:ג׳ — SPEC §22."""
    third = _find_all(tree, "section", "study-unit")[2]
    assert third.find(f"{XHTML}div[@class='keep-together']/{XHTML}div[@class='verse']") is not None
    assert not _find_all(third, "div", "commentary-divider")
    assert not _find_all(third, "div", "commentary-entry")


def test_dibur_hamatchil_leads_its_entry(tree) -> None:
    entry = tree.find(f".//{XHTML}div[@id='rashi-genesis-1-1-1']")
    paragraph = entry.find(f"{XHTML}p")
    lead = next(iter(paragraph))
    assert _class(lead) == "dibur-hamatchil"
    assert lead.text == "בראשית."


def test_nikkud_and_teamim_survive_into_the_xhtml(rendered) -> None:
    assert "בְּרֵאשִׁ֖ית" in rendered.xhtml or "רֵאשִׁ֖ית" in rendered.xhtml
    assert any(0x0591 <= ord(c) <= 0x05AF for c in rendered.xhtml), "no טעמים in the output"


def test_enlarged_letter_is_preserved_as_a_class(tree) -> None:
    large = _find_all(tree, "span", "letter-large")
    assert len(large) == 1
    assert large[0].text == "בְּ"


def test_no_english_in_the_reading_content(rendered) -> None:
    """SPEC §6 — no English words reach the reader. Attribute values and tag names are
    markup, not reading content, so only text nodes are checked."""
    tree = ElementTree.fromstring(rendered.xhtml)
    body = tree.find(f"{XHTML}body")
    text = "".join(node for node in body.itertext())
    assert not re.search(r"[A-Za-z]{2,}", text), re.findall(r"[A-Za-z]{2,}", text)


def test_no_javascript(rendered) -> None:
    assert "<script" not in rendered.xhtml.lower()
    assert "javascript:" not in rendered.xhtml.lower()


def test_chapter_file_is_well_under_the_size_limit(rendered, config) -> None:
    assert rendered.size_bytes < config.layout.max_file_kb * 1024


# ---- CSS ----------------------------------------------------------------


def test_css_declares_both_font_families(config) -> None:
    css = render_css(config)
    assert f'@font-face {{\n  font-family: "{config.biblical_font.family}";' in css
    assert f'@font-face {{\n  font-family: "{config.rashi_font.family}";' in css


def test_no_font_stack_names_two_embedded_families(config) -> None:
    """The one rule the Paperwhite would not honour, found after six rounds of device
    testing: `.commentary-text` named both embedded families, every other rule named one
    embedded family plus a generic, and it was the only rule that failed. SPEC §16 writes
    the two-family stack; SPEC §0 says the device decides."""
    import dataclasses

    families = {config.biblical_font.family, config.rashi_font.family}
    for rashi_script in (True, False):
        variant = dataclasses.replace(
            config, typography=dataclasses.replace(config.typography, rashi_script=rashi_script)
        )
        for line in render_css(variant).splitlines():
            if "font-family" not in line:
                continue
            named = [family for family in families if f'"{family}"' in line]
            assert len(named) <= 1, f"two embedded families in one stack: {line.strip()}"


def test_every_font_stack_ends_in_a_generic_fallback(config) -> None:
    """A single embedded family is fine only because a generic catches anything it lacks —
    and tests/test_fonts.py proves it lacks nothing in the actual text.

    `@font-face` blocks are skipped: there `font-family` names the face being declared,
    not a stack to fall back through.
    """
    in_font_face = False
    for line in render_css(config).splitlines():
        stripped = line.strip()
        if stripped.startswith("@font-face"):
            in_font_face = True
        elif stripped == "}":
            in_font_face = False
        elif "font-family" in stripped and not in_font_face:
            assert stripped.rstrip(";").endswith(("serif", "sans-serif")), stripped


def test_font_face_src_carries_a_format_hint(config) -> None:
    """Some converters skip a face whose format they would have to guess at."""
    assert render_css(config).count('format("truetype")') == 2


def test_css_uses_no_absolute_or_viewport_units(config) -> None:
    """SPEC §14: everything must scale together when the reader changes the font size."""
    assert not re.search(r"[\d.]+\s*(px|pt|vh|vw|cm|mm|in)\b", render_css(config))


def test_css_scales_come_from_config(config) -> None:
    css = render_css(config)
    assert f"font-size: {config.typography.biblical_scale:g}em" in css
    assert f"font-size: {config.typography.rashi_scale:g}em" in css
    assert f"font-size: {config.typography.verse_number_scale:g}em" in css
    assert f"font-size: {config.typography.divider_scale:g}em" in css


def test_css_uses_only_kindle_safe_properties(config) -> None:
    """SPEC §26 — plus `direction`, which EPUB 3 forbids in a style sheet; the markup's
    dir="rtl" does that job instead."""
    families = ("margin", "padding", "border", "font", "break", "page-break")
    allowed = {"text-align", "line-height", "text-indent", "src", "content"}
    body = re.sub(r"/\*.*?\*/", "", render_css(config), flags=re.S)
    used = {m.group(1).strip() for m in re.finditer(r"(?m)^\s*([a-z-]+)\s*:", body)}
    unexpected = {
        prop
        for prop in used
        if prop not in allowed and not any(prop == f or prop.startswith(f + "-") for f in families)
    }
    assert not unexpected, unexpected


def test_css_has_no_javascript_or_layout_tricks(config) -> None:
    css = render_css(config)
    for forbidden in ("display:", "position:", "grid", "flex", "@page", "vh", "vw", "calc("):
        assert forbidden not in css, forbidden


def test_keep_together_carries_both_break_spellings(config) -> None:
    """Old and new property names, because reader support is uneven — and both are hints."""
    css = render_css(config)
    assert "break-inside: avoid" in css
    assert "page-break-inside: avoid" in css
    assert "break-after: avoid" in css
    assert "page-break-after: avoid" in css


def test_build_date_renders_in_hebrew() -> None:
    from datetime import UTC, datetime

    assert hebrew_date(datetime(2026, 9, 11, tzinfo=UTC)) == "11 בספטמבר 2026"

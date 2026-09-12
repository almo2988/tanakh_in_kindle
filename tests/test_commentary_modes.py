"""Collapsible commentary — `commentary.mode` (decision D9).

`details` collapses each verse's Rashi behind a רש״י summary so the biblical text runs
continuously, using native HTML5 with no JavaScript. The requirement that shapes most of
these tests is that **only** the commentary's presentation changes: the verse markup, the
ids, the navigation and the stylesheet's Kindle-safety must all be identical to `inline`.
"""

from __future__ import annotations

import dataclasses
import re
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree

import pytest

from tanakh_epub.config import COMMENTARY_MODES, Commentary
from tanakh_epub.epub.builder import EpubBuilder
from tanakh_epub.rendering.css import render_css
from tanakh_epub.rendering.html_renderer import ChapterRenderer

XHTML = "{http://www.w3.org/1999/xhtml}"


def _config(config, mode: str):
    return dataclasses.replace(config, commentary=Commentary(mode=mode))


@pytest.fixture(scope="module")
def rendered(config, books, genesis_chapter_1):
    """The same chapter rendered in every mode."""
    chapters, _, _ = genesis_chapter_1
    return {
        mode: ChapterRenderer(_config(config, mode), books).render(chapters[0], book_start=True)
        for mode in COMMENTARY_MODES
    }


@pytest.fixture(scope="module")
def details_epub(tmp_path_factory, config, books, genesis_chapter_1):
    chapters, text_versions, commentary_versions = genesis_chapter_1
    output = tmp_path_factory.mktemp("details") / "details.epub"
    EpubBuilder(_config(config, "details"), books).build(
        chapters,
        output=output,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=datetime(2026, 9, 12, 12, 0, 0, tzinfo=UTC),
    )
    return output


def _tree(rendered, mode):
    return ElementTree.fromstring(rendered[mode].xhtml)


# ---- the collapsible structure ------------------------------------------


def test_details_mode_wraps_commentary_in_details_with_a_summary(rendered) -> None:
    tree = _tree(rendered, "details")
    blocks = tree.iter(f"{XHTML}details")
    count = 0
    for block in blocks:
        summary = block.find(f"{XHTML}summary")
        assert summary is not None, "every <details> needs a <summary>"
        assert "commentary" in block.get("class", "").split()
        count += 1
    assert count == 9, "nine of the ten POC verses have Rashi"


def test_collapsed_by_default(rendered) -> None:
    """No `open` attribute anywhere — that is the whole point of the change."""
    assert "<details" in rendered["details"].xhtml
    for block in _tree(rendered, "details").iter(f"{XHTML}details"):
        assert block.get("open") is None


def test_summary_is_the_hebrew_commentator_label(rendered, config) -> None:
    for summary in _tree(rendered, "details").iter(f"{XHTML}summary"):
        assert summary.text == config.commentator("Rashi").hebrew == "רש״י"
        assert "commentary-divider" in summary.get("class", "").split()


def test_every_entry_sits_inside_the_details_block(rendered) -> None:
    tree = _tree(rendered, "details")
    inside = {
        entry.get("id")
        for block in tree.iter(f"{XHTML}details")
        for entry in block.iter(f"{XHTML}div")
        if "commentary-entry" in entry.get("class", "").split()
    }
    everywhere = {
        entry.get("id")
        for entry in tree.iter(f"{XHTML}div")
        if "commentary-entry" in entry.get("class", "").split()
    }
    assert inside == everywhere
    assert len(everywhere) == 17


def test_a_verse_without_rashi_gets_no_details_block(rendered) -> None:
    """בראשית א׳:ג׳ — SPEC §22 holds in both modes."""
    units = [
        unit
        for unit in _tree(rendered, "details").iter(f"{XHTML}section")
        if "study-unit" in unit.get("class", "").split()
    ]
    third = units[2]
    assert third.find(f".//{XHTML}div[@id='genesis-1-3']") is not None
    assert list(third.iter(f"{XHTML}details")) == []


def test_no_keep_together_wrapper_when_collapsed(rendered) -> None:
    """Nothing to hold beside the verse when the commentary starts closed (SPEC §13)."""
    assert "keep-together" not in rendered["details"].xhtml
    assert "keep-together" in rendered["inline"].xhtml


def test_no_javascript_in_either_mode(rendered) -> None:
    for mode in COMMENTARY_MODES:
        lowered = rendered[mode].xhtml.lower()
        assert "<script" not in lowered
        assert "javascript:" not in lowered
        assert "onclick" not in lowered


# ---- what must NOT change ----------------------------------------------


def test_the_biblical_text_is_byte_identical_across_modes(rendered) -> None:
    """ "Do not modify the Biblical text" — checked literally, on the rendered markup."""
    verses = {
        mode: re.findall(r'<div class="verse".*?</div>', rendered[mode].xhtml, re.S)
        for mode in COMMENTARY_MODES
    }
    inline = [re.sub(r"\s+", " ", v) for v in verses["inline"]]
    details = [re.sub(r"\s+", " ", v) for v in verses["details"]]
    assert inline == details
    assert len(inline) == 10


def test_ids_and_filenames_are_unchanged_across_modes(rendered) -> None:
    for mode in COMMENTARY_MODES:
        assert rendered[mode].filename == "genesis-001.xhtml"
        assert rendered[mode].anchor == "chapter-1"
    ids = {
        mode: sorted(
            element.get("id")
            for element in _tree(rendered, mode).iter()
            if element.get("id") and not element.get("id").startswith("rashi-genesis-1-1-")
        )
        for mode in COMMENTARY_MODES
    }
    # The only new id in details mode is the <details> block itself, one per commented verse.
    extra = set(ids["details"]) - set(ids["inline"])
    assert all(re.fullmatch(r"rashi-genesis-1-\d+", new) for new in extra), extra


def test_navigation_is_identical_across_modes(details_epub, poc_epub) -> None:
    """ "Do not modify the navigation structure."" """

    def nav_and_ncx(path):
        with zipfile.ZipFile(path) as zf:
            return zf.read("OEBPS/nav.xhtml"), zf.read("OEBPS/toc.ncx")

    assert nav_and_ncx(details_epub) == nav_and_ncx(poc_epub)


def test_entry_ids_use_the_book_slug_not_a_lowercased_title(books) -> None:
    """`I Samuel` must give `samuel-1`, matching the file name — not `i-samuel`."""
    from tanakh_epub.models import CommentaryEntry
    from tanakh_epub.rendering.html_renderer import commentary_id, entry_id

    samuel = books.by_title("I Samuel")
    entry = CommentaryEntry(
        commentator="Rashi",
        book="I Samuel",
        chapter=3,
        verse=14,
        entry_number=2,
        dibur_hamatchil=None,
        text="x",
        source_provider="Sefaria",
        source_version="v",
        source_reference="Rashi on I Samuel 3:14:2",
    )
    assert commentary_id("rashi", samuel, 3, 14) == "rashi-samuel-1-3-14"
    assert entry_id("rashi", samuel, entry) == "rashi-samuel-1-3-14-2"


# ---- stylesheet ---------------------------------------------------------


def test_details_css_is_only_emitted_in_details_mode(config) -> None:
    assert "summary.commentary-divider" in render_css(_config(config, "details"))
    assert "summary" not in render_css(_config(config, "inline"))


def test_details_css_stays_within_the_kindle_safe_properties(config) -> None:
    """SPEC §26 — and in particular no `display`, which `<summary>` tempts you to set."""
    families = ("margin", "padding", "border", "font", "break", "page-break")
    allowed = {"text-align", "line-height", "text-indent", "src", "content"}
    body = re.sub(r"/\*.*?\*/", "", render_css(_config(config, "details")), flags=re.S)
    used = {m.group(1).strip() for m in re.finditer(r"(?m)^\s*([a-z-]+)\s*:", body)}
    unexpected = {
        prop
        for prop in used
        if prop not in allowed and not any(prop == f or prop.startswith(f + "-") for f in families)
    }
    assert not unexpected, unexpected
    assert "display" not in used
    assert "list-style" not in used


def test_rashi_font_and_scaling_survive_the_mode(config) -> None:
    """ "Preserve the Rashi font and responsive font sizing."" """
    css = render_css(_config(config, "details"))
    assert f'font-family: "{config.rashi_font.family}", serif;' in css
    assert f"font-size: {config.typography.rashi_scale:g}em" in css
    assert not re.search(r"[\d.]+\s*(px|pt|vh|vw)\b", css)


# ---- the packaged book --------------------------------------------------


def test_details_epub_is_rtl_and_well_formed(details_epub) -> None:
    with zipfile.ZipFile(details_epub) as zf:
        page = zf.read("OEBPS/text/genesis-001.xhtml")
    root = ElementTree.fromstring(page)
    assert root.get("dir") == "rtl"
    assert root.get("lang") == "he"
    assert root.find(f"{XHTML}body").get("dir") == "rtl"
    assert b"<details" in page


def test_details_epub_has_no_oversized_chapter(details_epub, config) -> None:
    with zipfile.ZipFile(details_epub) as zf:
        for name in zf.namelist():
            if name.startswith("OEBPS/text/"):
                assert zf.getinfo(name).file_size <= config.layout.max_file_kb * 1024


def test_an_unknown_mode_is_refused(tmp_path, config) -> None:
    import yaml

    from tanakh_epub.config import load_config
    from tanakh_epub.paths import DEFAULT_CONFIG

    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["commentary"] = {"mode": "accordion"}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match=r"commentary\.mode"):
        load_config(path)

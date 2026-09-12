"""Page layout — `commentary.mode` (decision D9).

`blocks` renders a run of consecutive verses, then the Rashi on that whole run, after the
manner of a printed מקראות גדולות page. `interleaved` keeps each verse with its own Rashi,
which is the Phase 1 layout and what SPEC §2 as written requires.

The property that matters most here is that the visual grouping is *presentation only*: the
canonical verse↔commentary association has to survive in the markup regardless of which
region a passage is rendered in, which is what the ids and `data-ref` attributes are for.
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
from tanakh_epub.rendering.html_renderer import ChapterRenderer, group_into_blocks, visible_length

XHTML = "{http://www.w3.org/1999/xhtml}"
EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"


def _config(config, mode: str, block_chars: int | None = None):
    return dataclasses.replace(
        config,
        commentary=Commentary(mode=mode, block_chars=block_chars or config.commentary.block_chars),
    )


@pytest.fixture(scope="module")
def rendered(config, books, genesis_chapter_1):
    chapters, _, _ = genesis_chapter_1
    return {
        mode: ChapterRenderer(_config(config, mode), books).render(chapters[0], book_start=True)
        for mode in COMMENTARY_MODES
    }


@pytest.fixture(scope="module")
def blocks_epub(tmp_path_factory, config, books, genesis_chapter_1):
    chapters, text_versions, commentary_versions = genesis_chapter_1
    output = tmp_path_factory.mktemp("blocks") / "blocks.epub"
    EpubBuilder(_config(config, "blocks"), books).build(
        chapters,
        output=output,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=datetime(2026, 9, 12, 12, 0, 0, tzinfo=UTC),
    )
    return output


def _tree(rendered, mode):
    return ElementTree.fromstring(rendered[mode].xhtml)


def _by_class(tree, tag, css_class):
    return [e for e in tree.iter(f"{XHTML}{tag}") if css_class in e.get("class", "").split()]


# ---- two continuous streams ---------------------------------------------


def test_blocks_is_the_default(config) -> None:
    assert config.commentary.mode == "blocks"


def test_a_block_holds_several_verses_then_their_commentary(rendered) -> None:
    tree = _tree(rendered, "blocks")
    blocks = _by_class(tree, "section", "study-block")
    assert blocks, "no study blocks rendered"
    for block in blocks:
        verses = _by_class(block, "span", "verse")
        assert verses, "a block with no verses"
    assert any(len(_by_class(b, "span", "verse")) > 1 for b in blocks), (
        "every block held a single verse — that is the interleaved layout, not two streams"
    )


def test_verses_are_a_continuous_run_not_a_container_each(rendered) -> None:
    """"It should not force ... a separate container after every verse.""" ""
    tree = _tree(rendered, "blocks")
    for flow in _by_class(tree, "p", "biblical-flow"):
        for child in flow:
            assert child.tag == f"{XHTML}span", "a verse became a block-level container"
            assert "verse" in child.get("class", "").split()
    assert _by_class(tree, "div", "verse") == [], "no verse should be a <div> in this layout"


def test_commentary_is_a_continuous_run_too(rendered) -> None:
    tree = _tree(rendered, "blocks")
    flows = _by_class(tree, "p", "commentary-flow")
    assert flows
    for flow in flows:
        for child in flow:
            assert child.tag == f"{XHTML}span"
            assert "commentary-entry" in child.get("class", "").split()


def test_the_tanakh_region_comes_before_the_rashi_region(rendered) -> None:
    for block in _by_class(_tree(rendered, "blocks"), "section", "study-block"):
        classes = [child.get("class", "").split()[0] for child in block]
        assert classes[0] == "tanakh"
        assert classes[1:] in ([], ["commentary-divider", "commentary"])


def test_no_verse_and_its_own_rashi_form_a_visual_unit(rendered) -> None:
    """The thing the author explicitly did not want: verse, rashi, verse, rashi."""
    assert "study-unit" not in rendered["blocks"].xhtml
    assert "keep-together" not in rendered["blocks"].xhtml


# ---- the association survives the regrouping ----------------------------


def test_every_verse_keeps_its_id_and_canonical_reference(rendered) -> None:
    verses = _by_class(_tree(rendered, "blocks"), "span", "verse")
    assert [v.get("id") for v in verses] == [f"genesis-1-{n}" for n in range(1, 11)]
    assert [v.get("data-ref") for v in verses] == [f"Genesis 1:{n}" for n in range(1, 11)]


def test_every_commentary_segment_keeps_its_exact_sefaria_reference(rendered) -> None:
    """ "The Rashi stream must preserve the exact canonical Sefaria reference for every
    commentary segment."" """
    entries = _by_class(_tree(rendered, "blocks"), "span", "commentary-entry")
    assert len(entries) == 17
    for entry in entries:
        ref = entry.get("data-ref")
        assert re.fullmatch(r"Rashi on Genesis 1:\d+:\d+", ref), ref
        chapter, verse, number = (int(p) for p in ref.split()[-1].split(":"))
        assert entry.get("id") == f"rashi-genesis-{chapter}-{verse}-{number}"


def test_commentary_keeps_canonical_order_across_the_whole_block(rendered) -> None:
    """Entries stay in verse order and then source order (SPEC §23), even though they are
    no longer grouped by verse."""
    refs = [
        e.get("data-ref") for e in _by_class(_tree(rendered, "blocks"), "span", "commentary-entry")
    ]
    keys = [tuple(int(p) for p in r.split()[-1].split(":")) for r in refs]
    assert keys == sorted(keys)


def test_a_verse_without_rashi_contributes_nothing_to_the_rashi_stream(rendered) -> None:
    """בראשית א׳:ג׳ has no Rashi, and must not produce an empty segment (SPEC §22)."""
    refs = {
        e.get("data-ref") for e in _by_class(_tree(rendered, "blocks"), "span", "commentary-entry")
    }
    assert not any(r.startswith("Rashi on Genesis 1:3:") for r in refs)
    verses = {v.get("id") for v in _by_class(_tree(rendered, "blocks"), "span", "verse")}
    assert "genesis-1-3" in verses, "the verse itself must still be there"


def test_the_biblical_text_is_identical_in_both_layouts(rendered) -> None:
    def texts(mode):
        return [
            re.sub(r"\s+", " ", "".join(span.itertext()))
            for span in _by_class(_tree(rendered, mode), "span", "biblical-text")
        ]

    assert texts("blocks") == texts("interleaved")
    assert len(texts("blocks")) == 10


def test_navigation_is_identical_in_both_layouts(blocks_epub, poc_epub) -> None:
    def nav_and_ncx(path):
        with zipfile.ZipFile(path) as zf:
            return zf.read("OEBPS/nav.xhtml"), zf.read("OEBPS/toc.ncx")

    assert nav_and_ncx(blocks_epub) == nav_and_ncx(poc_epub)


# ---- how blocks are sized -----------------------------------------------


def test_a_block_fills_to_the_character_budget() -> None:
    units = [{"verse_length": 100, "verse_id": f"v{i}", "commentary": None} for i in range(6)]
    blocks = group_into_blocks(units, 250)
    assert [len(b["verses"]) for b in blocks] == [3, 3]


def test_a_verse_longer_than_the_budget_still_gets_a_block() -> None:
    units = [{"verse_length": 9999, "verse_id": "v0", "commentary": None}]
    assert len(group_into_blocks(units, 100)) == 1


def test_a_smaller_budget_makes_more_blocks(config, books, genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    counts = {}
    for budget in (200, 900):
        xhtml = (
            ChapterRenderer(_config(config, "blocks", budget), books)
            .render(chapters[0], book_start=False)
            .xhtml
        )
        counts[budget] = xhtml.count('class="study-block"')
    assert counts[200] > counts[900] >= 1


def test_block_budget_counts_visible_characters_not_markup() -> None:
    assert visible_length('<span class="letter-large">בְּ</span>רֵאשִׁית') == len("בְּרֵאשִׁית")


# ---- stylesheet ---------------------------------------------------------


def test_block_css_is_only_emitted_for_the_block_layout(config) -> None:
    assert ".biblical-flow" in render_css(_config(config, "blocks"))
    assert ".biblical-flow" not in render_css(_config(config, "interleaved"))


def test_no_collapsible_machinery_remains(config) -> None:
    """`details` and the noteref popup were both tried on the device and rejected."""
    for mode in COMMENTARY_MODES:
        css = render_css(_config(config, mode))
        assert "summary" not in css
        assert "commentary-marker" not in css
    assert "details" not in COMMENTARY_MODES
    assert "popup" not in COMMENTARY_MODES


def test_block_css_reserves_no_share_of_the_screen(config) -> None:
    """ "must not use fixed vh, pixel heights, or screen-size assumptions."" """
    css = re.sub(r"/\*.*?\*/", "", render_css(_config(config, "blocks")), flags=re.S)
    assert not re.search(r"[\d.]+\s*(px|pt|vh|vw|cm|mm|in)\b", css)
    declared = {m.group(1) for m in re.finditer(r"(?m)^\s*([a-z-]+)\s*:", css)}
    forbidden = {"height", "max-height", "min-height", "position", "display", "float"}
    assert not (declared & forbidden), declared & forbidden
    assert not any(p.startswith("column") for p in declared), declared


def test_rashi_font_and_scale_survive_the_layout(config) -> None:
    for mode in COMMENTARY_MODES:
        css = render_css(_config(config, mode))
        assert f'font-family: "{config.rashi_font.family}", serif;' in css
        assert f"font-size: {config.typography.rashi_scale:g}em" in css
        assert f"font-size: {config.typography.biblical_scale:g}em" in css
        assert config.typography.rashi_scale < config.typography.biblical_scale


# ---- the packaged book --------------------------------------------------


def test_blocks_epub_is_valid_rtl_and_within_the_size_limit(blocks_epub, config) -> None:
    with zipfile.ZipFile(blocks_epub) as zf:
        page = zf.read("OEBPS/text/genesis-001.xhtml")
        for name in zf.namelist():
            if name.startswith("OEBPS/text/"):
                assert zf.getinfo(name).file_size <= config.layout.max_file_kb * 1024
    root = ElementTree.fromstring(page)
    assert root.get("dir") == "rtl"
    assert root.find(f"{XHTML}body").get("dir") == "rtl"


def test_an_unknown_mode_is_refused(tmp_path) -> None:
    import yaml

    from tanakh_epub.config import load_config
    from tanakh_epub.paths import DEFAULT_CONFIG

    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["commentary"] = {"mode": "columns"}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match=r"commentary\.mode"):
        load_config(path)

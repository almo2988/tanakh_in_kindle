"""SPEC.md §4, §10, §11, §15, §17, §28, §33 — the packaged EPUB."""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

import pytest

from tanakh_epub.epub.builder import MIMETYPE
from tanakh_epub.epub.metadata import derive_identifier

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "epub": "http://www.idpf.org/2007/ops",
}


@pytest.fixture(scope="module")
def archive(poc_epub):
    with zipfile.ZipFile(poc_epub) as zf:
        yield zf


@pytest.fixture(scope="module")
def opf(archive):
    return ElementTree.fromstring(archive.read("OEBPS/content.opf"))


@pytest.fixture(scope="module")
def nav(archive):
    return ElementTree.fromstring(archive.read("OEBPS/nav.xhtml"))


@pytest.fixture(scope="module")
def ncx(archive):
    return ElementTree.fromstring(archive.read("OEBPS/toc.ncx"))


# ---- Container ----------------------------------------------------------


def test_mimetype_is_first_and_stored_uncompressed(poc_epub) -> None:
    with zipfile.ZipFile(poc_epub) as zf:
        first = zf.infolist()[0]
    assert first.filename == "mimetype"
    assert first.compress_type == zipfile.ZIP_STORED
    with zipfile.ZipFile(poc_epub) as zf:
        assert zf.read("mimetype").decode() == MIMETYPE


def test_container_points_at_the_package_document(archive) -> None:
    container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
    rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
    assert rootfile.get("full-path") == "OEBPS/content.opf"


# ---- Package ------------------------------------------------------------


def test_language_is_hebrew_and_page_progression_is_rtl(opf) -> None:
    """What makes the Kindle turn pages right-to-left (SPEC §17)."""
    assert opf.find("opf:metadata/dc:language", NS).text == "he"
    assert opf.find("opf:spine", NS).get("page-progression-direction") == "rtl"


def test_title_is_hebrew(opf, config) -> None:
    assert opf.find("opf:metadata/dc:title", NS).text == config.title == "תנ״ך עם פירוש רש״י"


def test_identifier_is_stable_across_rebuilds(config) -> None:
    assert derive_identifier(config, ["Genesis"]) == derive_identifier(config, ["Genesis"])
    assert derive_identifier(config, ["Genesis"]) != derive_identifier(config, ["Exodus"])


def test_modified_timestamp_is_present(opf) -> None:
    meta = opf.find("opf:metadata/opf:meta[@property='dcterms:modified']", NS)
    assert meta.text.endswith("Z")


def test_source_versions_are_recorded_in_the_book_itself(opf, config) -> None:
    """SPEC §28 and SPEC_DATA_SOURCE §14 — the build has to say what it was made from."""
    values = [m.text for m in opf.findall("opf:metadata/opf:meta", NS)]
    assert any(config.tanakh_source.version_title in (v or "") for v in values)
    assert any(config.commentary_sources["Rashi"].version_title in (v or "") for v in values)
    rights = [r.text for r in opf.findall("opf:metadata/dc:rights", NS)]
    assert any(config.tanakh_source.license in (r or "") for r in rights)


def test_custom_meta_prefix_is_declared(opf) -> None:
    assert "tanakh:" in (opf.get("prefix") or "")


# ---- Manifest and spine -------------------------------------------------


def test_every_manifest_item_exists_in_the_archive(opf, archive) -> None:
    names = set(archive.namelist())
    for item in opf.findall("opf:manifest/opf:item", NS):
        assert f"OEBPS/{item.get('href')}" in names, item.get("href")


def test_nav_and_ncx_are_both_present(opf) -> None:
    """SPEC §4: Kindle conversion tools and older readers still read the NCX."""
    items = {i.get("id"): i for i in opf.findall("opf:manifest/opf:item", NS)}
    assert items["nav"].get("properties") == "nav"
    assert items["ncx"].get("media-type") == "application/x-dtbncx+xml"
    assert opf.find("opf:spine", NS).get("toc") == "ncx"


def test_fonts_are_in_the_manifest_with_a_kindle_recognised_media_type(opf, config) -> None:
    """`application/vnd.ms-opentype`, not the newer `font/ttf` — see css.FONT_MEDIA_TYPES."""
    media = {i.get("href"): i.get("media-type") for i in opf.findall("opf:manifest/opf:item", NS)}
    assert media.get("fonts/biblical_hebrew.ttf") == "application/vnd.ms-opentype"
    assert media.get(f"fonts/rashi{config.rashi_font.suffix}") == "application/vnd.ms-opentype"


def test_font_files_are_embedded_and_non_empty(archive, config) -> None:
    biblical = archive.read("OEBPS/fonts/biblical_hebrew.ttf")
    rashi = archive.read(f"OEBPS/fonts/rashi{config.rashi_font.suffix}")
    assert biblical == config.biblical_font.file.read_bytes()
    assert rashi == config.rashi_font.file.read_bytes()
    assert len(biblical) > 10_000


def test_one_xhtml_file_per_chapter(archive) -> None:
    text_files = [n for n in archive.namelist() if n.startswith("OEBPS/text/")]
    assert sorted(text_files) == ["OEBPS/text/genesis-001.xhtml", "OEBPS/text/sources.xhtml"]


def test_no_chapter_file_exceeds_the_size_limit(archive, config) -> None:
    limit = config.layout.max_file_kb * 1024
    for name in archive.namelist():
        if name.startswith("OEBPS/text/"):
            assert archive.getinfo(name).file_size <= limit, name


def test_spine_ends_with_the_sources_page(opf) -> None:
    spine = [i.get("idref") for i in opf.findall("opf:spine/opf:itemref", NS)]
    assert spine == ["genesis-001", "sources"]


# ---- Navigation ---------------------------------------------------------


def test_nav_is_hebrew_and_rtl(nav) -> None:
    assert nav.get("lang") == "he"
    assert nav.get("dir") == "rtl"


def test_nav_nesting_is_at_most_two_levels(nav) -> None:
    """Kindle's "Go to" shows two nested levels; a third would hide the chapters."""
    toc = nav.find(".//xhtml:nav[@id='toc']", NS)
    outer = toc.find("xhtml:ol", NS)
    for item in outer.findall("xhtml:li", NS):
        for inner in item.findall("xhtml:ol", NS):
            assert inner.findall("xhtml:ol", NS) == []
            for leaf in inner.findall("xhtml:li", NS):
                assert leaf.findall("xhtml:ol", NS) == []


def test_nav_lists_the_book_and_every_chapter(nav) -> None:
    toc = nav.find(".//xhtml:nav[@id='toc']", NS)
    books = toc.findall("xhtml:ol/xhtml:li", NS)
    titles = [b.find("xhtml:a", NS).text for b in books]
    assert "בראשית" in titles
    genesis = books[titles.index("בראשית")]
    chapters = [a.text for a in genesis.findall("xhtml:ol/xhtml:li/xhtml:a", NS)]
    assert chapters == ["פרק א׳"]


def test_every_nav_link_resolves_to_a_real_file_and_anchor(nav, archive) -> None:
    names = set(archive.namelist())
    for anchor in nav.iter(f"{{{NS['xhtml']}}}a"):
        href = anchor.get("href")
        path, _, fragment = href.partition("#")
        assert f"OEBPS/{path}" in names, href
        if fragment:
            document = archive.read(f"OEBPS/{path}").decode("utf-8")
            assert f'id="{fragment}"' in document, href


def test_ncx_mirrors_the_nav_with_sequential_play_order(ncx) -> None:
    points = list(ncx.iter(f"{{{NS['ncx']}}}navPoint"))
    assert points
    orders = [int(p.get("playOrder")) for p in points]
    assert orders == sorted(orders)
    assert orders == list(range(1, len(orders) + 1))
    labels = [p.find("ncx:navLabel/ncx:text", NS).text for p in points]
    assert "בראשית" in labels and "פרק א׳" in labels


def test_ncx_depth_is_two(ncx) -> None:
    depth = ncx.find("ncx:head/ncx:meta[@name='dtb:depth']", NS)
    assert depth.get("content") == "2"
    for point in ncx.find(f"{{{NS['ncx']}}}navMap"):
        for child in point.findall("ncx:navPoint", NS):
            assert child.findall("ncx:navPoint", NS) == []


def test_ncx_links_resolve(ncx, archive) -> None:
    names = set(archive.namelist())
    for content in ncx.iter(f"{{{NS['ncx']}}}content"):
        path = content.get("src").partition("#")[0]
        assert f"OEBPS/{path}" in names, content.get("src")


# ---- Sources page -------------------------------------------------------


def test_sources_page_attributes_sefaria_and_names_every_version(archive, config) -> None:
    """Compared against the rendered text, not the raw bytes: the Rashi version title
    contains an apostrophe, which is correctly escaped in the markup."""
    root = ElementTree.fromstring(archive.read("OEBPS/text/sources.xhtml"))
    text = "".join(root.itertext())
    assert "ספריא" in text
    assert "מקורות" in text
    assert config.tanakh_source.version_title in text
    assert config.tanakh_source.license in text
    assert config.commentary_sources["Rashi"].version_title in text
    assert config.commentary_sources["Rashi"].license in text
    assert config.biblical_font.name in text
    assert config.rashi_font.name in text
    assert config.biblical_font.license in text


# ---- Every document -----------------------------------------------------


def test_every_xhtml_document_is_hebrew_rtl_and_well_formed(archive) -> None:
    documents = [n for n in archive.namelist() if n.endswith(".xhtml")]
    assert documents
    for name in documents:
        root = ElementTree.fromstring(archive.read(name))
        assert root.get("lang") == "he", name
        assert root.get("dir") == "rtl", name
        assert root.find("xhtml:body", NS).get("dir") == "rtl", name

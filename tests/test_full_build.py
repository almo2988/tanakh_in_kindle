"""Phase 3 — the full-Tanakh features: per-book commentary versions, chapter splitting,
the cover, the build manifest, the sources page and the stable identifier (SPEC.md §10,
§11, §28, §29; SPEC_DATA_SOURCE.md §5, §13–§15)."""

from __future__ import annotations

import dataclasses
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from tanakh_epub.cli import main
from tanakh_epub.config import Layout, load_config
from tanakh_epub.epub import metadata as metadata_module
from tanakh_epub.epub.builder import EpubBuilder
from tanakh_epub.epub.cover import generate_cover, load_cover
from tanakh_epub.epub.manifest import sources_and_licenses
from tanakh_epub.epub.metadata import derive_identifier, identifier_salt, new_identifier_salt
from tanakh_epub.paths import DEFAULT_CONFIG
from tanakh_epub.rendering.html_renderer import ChapterRenderer

OPF = {"opf": "http://www.idpf.org/2007/opf"}
BUILD_DATE = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)


def _build(tmp_path: Path, config, books, genesis_chapter_1, name="book.epub"):
    chapters, text_versions, commentary_versions = genesis_chapter_1
    return EpubBuilder(config, books).build(
        chapters,
        output=tmp_path / name,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=BUILD_DATE,
    )


def _write_config(tmp_path: Path, change) -> Path:
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    change(raw)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


# ---- Per-book commentary versions (D6) --------------------------------------------------


def test_every_book_has_exactly_one_rashi_version(config, books) -> None:
    configured = config.commentary_book_sources["Rashi"]
    assert set(configured) == {b.sefaria_title for b in books}


def test_rashi_versions_are_vocalized_editions_by_book(config) -> None:
    def version(book: str) -> str:
        return config.commentary_source("Rashi", book).version_title

    assert version("Genesis").startswith("Pentateuch with Rashi's commentary")
    assert version("Numbers").endswith("corrected vocalization")
    assert version("Isaiah") == "Sefaria vocalized edition"
    assert "Metsudah" in version("Ruth")
    assert version("I Kings") != version("II Kings"), "Sefaria's titles differ by a space"


def test_a_book_in_two_versions_is_refused(tmp_path: Path) -> None:
    def duplicate(raw):
        raw["sources"]["commentaries"]["Rashi"]["versions"][1]["books"].append("Genesis")

    with pytest.raises(ValueError, match="Genesis is in more than one"):
        load_config(_write_config(tmp_path, duplicate))


def test_versions_used_follow_the_books_built(config) -> None:
    used = config.commentary_versions_for("Rashi", ["Genesis", "Exodus"])
    assert [s.version_title for s in used] == [
        config.commentary_source("Rashi", "Genesis").version_title
    ]
    assert len(config.commentary_versions_for("Rashi")) == 7


# ---- Chapter splitting (SPEC.md §11) ----------------------------------------------------


@pytest.fixture(scope="module")
def tiny_limit_config():
    config = load_config()
    return dataclasses.replace(config, layout=dataclasses.replace(config.layout, max_file_kb=8))


def test_an_oversized_chapter_is_split_at_study_units(
    tiny_limit_config, books, genesis_chapter_1
) -> None:
    chapters, _, _ = genesis_chapter_1
    rendered = ChapterRenderer(tiny_limit_config, books).render_all(chapters)
    assert len(rendered) >= 2
    assert [r.filename for r in rendered][:2] == ["genesis-001.xhtml", "genesis-001-b.xhtml"]
    assert all(r.size_bytes <= 8 * 1024 for r in rendered)

    first, rest = rendered[0], rendered[1:]
    assert 'id="chapter-1"' in first.xhtml and "chapter-heading" in first.xhtml
    for part in rest:
        assert 'id="chapter-1"' not in part.xhtml
        assert "chapter-heading" not in part.xhtml
        assert "book-heading" not in part.xhtml

    verse_ids = [f'id="genesis-1-{n}"' for n in range(1, 11)]
    joined = "".join(r.xhtml for r in rendered)
    assert all(joined.count(v) == 1 for v in verse_ids), "every verse exactly once"


def test_a_split_chapter_has_one_toc_entry_and_every_part_in_the_spine(
    tmp_path: Path, tiny_limit_config, books, genesis_chapter_1
) -> None:
    result = _build(tmp_path, tiny_limit_config, books, genesis_chapter_1)
    assert result.oversized == []
    with zipfile.ZipFile(result.path) as archive:
        nav = archive.read("OEBPS/nav.xhtml").decode("utf-8")
        opf = ElementTree.fromstring(archive.read("OEBPS/content.opf"))
    assert "genesis-001-b.xhtml" not in nav
    spine = [i.get("idref") for i in opf.findall("opf:spine/opf:itemref", OPF)]
    assert spine[:2] == ["genesis-001", "genesis-001-b"]


def test_a_normal_chapter_is_not_split(config, books, genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    rendered = ChapterRenderer(config, books).render_all(chapters)
    assert [r.filename for r in rendered] == ["genesis-001.xhtml"]


# ---- Cover (SPEC.md §29) ------------------------------------------------------------------


def test_the_cover_is_declared_for_the_kindle(tmp_path: Path, config, books, genesis_chapter_1):
    result = _build(tmp_path, config, books, genesis_chapter_1)
    with zipfile.ZipFile(result.path) as archive:
        opf = ElementTree.fromstring(archive.read("OEBPS/content.opf"))
        image = archive.read("OEBPS/images/cover.jpg")
    items = {i.get("id"): i for i in opf.findall("opf:manifest/opf:item", OPF)}
    assert items["cover-image"].get("properties") == "cover-image"
    assert items["cover-image"].get("media-type") == "image/jpeg"
    meta = opf.find("opf:metadata/opf:meta[@name='cover']", OPF)
    assert meta is not None and meta.get("content") == "cover-image"

    from PIL import Image

    with Image.open(io.BytesIO(image)) as picture:
        assert picture.size == (1600, 2560)
        assert picture.mode == "L", "black and white"


def test_no_cover_when_the_mode_is_none(config) -> None:
    assert load_cover(dataclasses.replace(config, cover_mode="none")) is None


def test_cover_refuses_text_it_cannot_shape(config) -> None:
    with pytest.raises(ValueError, match="combining marks"):
        generate_cover(config, lines=("תּוֹרָה",))


# ---- Build manifest and licenses (SPEC_DATA_SOURCE.md §14, §15) ---------------------------


def test_the_build_manifest_is_embedded(tmp_path: Path, config, books, genesis_chapter_1):
    result = _build(tmp_path, config, books, genesis_chapter_1)
    with zipfile.ZipFile(result.path) as archive:
        embedded = json.loads(archive.read("OEBPS/build_manifest.json"))
    assert embedded == result.manifest
    assert embedded["books"] == ["Genesis"]
    assert embedded["identifier"] == result.identifier
    assert embedded["commentary_versions"]["Rashi"]["Genesis"].startswith("Pentateuch")
    for key in ("build_date", "generator_version", "config_hash", "fonts", "delivery_target"):
        assert embedded[key], key


def test_license_report_flags_an_unknown_license(config, books) -> None:
    manifest = {
        "build_date": "2026-09-19T12:00:00Z",
        "identifier": "urn:uuid:x",
        "books": ["Genesis", "Isaiah"],
        "commentary_versions": {
            "Rashi": {
                "Genesis": config.commentary_source("Rashi", "Genesis").version_title,
                "Isaiah": "Sefaria vocalized edition",
            }
        },
    }
    report = sources_and_licenses(config, books, manifest)
    assert "| Sefaria vocalized edition | unknown |" in report
    assert "do not redistribute" in report


# ---- Sources page (SPEC_DATA_SOURCE.md §13) --------------------------------------------


def test_sources_page_lists_each_version_with_its_books(config, books) -> None:
    xhtml = ChapterRenderer(config, books).render_sources(
        build_date=BUILD_DATE,
        text_versions={"Genesis": "x", "Isaiah": "x"},
        commentary_versions={
            "Rashi": {
                "Genesis": config.commentary_source("Rashi", "Genesis").version_title,
                "Isaiah": "Sefaria vocalized edition",
            }
        },
    )
    assert "ספרים: בראשית" in xhtml
    assert "ספרים: ישעיהו" in xhtml
    assert "Sefaria vocalized edition" in xhtml
    assert xhtml.index("ספרים: בראשית") < xhtml.index("ספרים: ישעיהו"), "Tanakh order"


def test_one_version_needs_no_book_list(config, books) -> None:
    xhtml = ChapterRenderer(config, books).render_sources(
        build_date=BUILD_DATE,
        text_versions={"Genesis": "x"},
        commentary_versions={
            "Rashi": {"Genesis": config.commentary_source("Rashi", "Genesis").version_title}
        },
    )
    assert "ספרים:" not in xhtml


# ---- Identifier (SPEC.md §28) -----------------------------------------------------------


def test_identifier_survives_a_typography_change(config) -> None:
    """A re-sent book must replace the old copy on the Kindle, not sit beside it."""
    tweaked = dataclasses.replace(config, raw={**config.raw, "typography": {"x": 1}})
    assert tweaked.config_hash != config.config_hash
    assert derive_identifier(tweaked, ["Genesis"]) == derive_identifier(config, ["Genesis"])


def test_identifier_changes_with_the_salt(config) -> None:
    assert derive_identifier(config, ["Genesis"], "a") != derive_identifier(config, ["Genesis"])


def test_new_identifier_salt_persists(tmp_path: Path) -> None:
    store = tmp_path / "identity.json"
    assert identifier_salt("Tanakh_with_Rashi.epub", store) == ""
    salt = new_identifier_salt("Tanakh_with_Rashi.epub", store)
    assert identifier_salt("Tanakh_with_Rashi.epub", store) == salt
    assert identifier_salt("Other.epub", store) == ""


def test_build_new_identifier_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(metadata_module, "IDENTITY_FILE", tmp_path / "identity.json")
    output = tmp_path / "g.epub"
    args = ["build", "--chapter", "Genesis", "1", "--output", str(output)]

    def identifier() -> str:
        return next(
            line.split()[-1]
            for line in capsys.readouterr().out.splitlines()
            if line.strip().startswith("identifier ")
        )

    assert main(args) == 0
    first = identifier()
    assert main(args) == 0
    assert identifier() == first
    assert main([*args, "--new-identifier"]) == 0
    renewed = identifier()
    assert renewed != first
    assert main(args) == 0
    assert identifier() == renewed, "the new identifier sticks"

    assert (tmp_path / "g.build_manifest.json").is_file()
    assert (tmp_path / "g.SOURCES_AND_LICENSES.md").is_file()


def test_layout_is_a_config_type() -> None:
    """`Layout` is replaced field by field above; keep it a dataclass."""
    assert dataclasses.is_dataclass(Layout)

"""SPEC_DATA_SOURCE.md §9.1, §18 — the markup inventory and the validation report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tanakh_epub.cli import main
from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.processing.inventory import Inventory, format_inventory, scan
from tanakh_epub.processing.validation import format_report, validate_book
from tanakh_epub.providers.local import LocalProvider

TANAKH = "Miqra according to the Masorah"
RASHI = "Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _write_cache(root: Path, *, text=None, rashi=None, text_lengths=None, rashi_lengths=None):
    """A cache in the shape `fetch` writes, from the fixtures unless told otherwise."""
    tanakh = _fixture("genesis_1.json")
    commentary = _fixture("rashi_genesis_1.json")
    for payload, override, lengths in (
        (tanakh, text, text_lengths),
        (commentary, rashi, rashi_lengths),
    ):
        payload.pop("chapters_included", None)
        payload.pop("_capture", None)
        if override is not None:
            payload["text"] = override
        if lengths is not None:
            payload["index_lengths"] = lengths
    (root / "tanakh").mkdir(parents=True, exist_ok=True)
    (root / "rashi").mkdir(parents=True, exist_ok=True)
    (root / "tanakh" / "genesis.json").write_text(json.dumps(tanakh), encoding="utf-8")
    (root / "rashi" / "genesis.json").write_text(json.dumps(commentary), encoding="utf-8")
    return tanakh["text"], commentary["text"]


def _local(root: Path, books) -> LocalProvider:
    return LocalProvider([root], books=books, expected_versions={"tanakh": TANAKH, "Rashi": RASHI})


# ---- Inventory --------------------------------------------------------------------------


def test_inventory_of_the_fixtures_has_no_unknown_patterns() -> None:
    inventory = Inventory()
    scan(inventory, "Genesis", _fixture("genesis_1.json")["text"])
    scan(inventory, "Rashi on Genesis", _fixture("rashi_genesis_1.json")["text"])
    assert inventory.unknown == []
    keys = {p.key for p in inventory.patterns.values()}
    assert '<span class="mam-spi-pe">' in keys
    assert "&nbsp;" in keys


def test_inventory_flags_an_unknown_tag_with_its_first_reference() -> None:
    inventory = Inventory()
    scan(inventory, "Genesis", [["א", 'ב <span class="mam-new">ג</span>'], ["<u>ד</u>"]])
    unknown = {p.key: p.example for p in inventory.unknown}
    assert unknown == {'<span class="mam-new">': "Genesis 1:2", "<u>": "Genesis 2:1"}
    assert "Unknown patterns: 2" in format_inventory(inventory)


def test_inventory_treats_an_extra_attribute_as_unknown() -> None:
    inventory = Inventory()
    scan(inventory, "Genesis", [['<b data-x="1">א</b>']])
    assert [p.key for p in inventory.unknown] == ["<b data-x=…>"]


def test_inventory_lists_invisible_characters() -> None:
    inventory = Inventory()
    scan(inventory, "Rashi on Genesis", [[["א‏ב"]]])
    assert "U+200F RIGHT-TO-LEFT MARK" in {p.key for p in inventory.patterns.values()}
    assert inventory.unknown == []


# ---- Validation -------------------------------------------------------------------------


def test_the_fixture_chapter_validates_clean(tmp_path: Path, config, books) -> None:
    _write_cache(tmp_path, text_lengths=[1, 31], rashi_lengths=[1, 24, 55])
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert report.problems == [], report.problems
    assert (report.chapters, report.verses) == (1, 31)
    assert report.commentaries[0].present


def test_counts_that_disagree_with_the_index_fail(tmp_path: Path, config, books) -> None:
    _write_cache(tmp_path, text_lengths=[50, 1533])
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert "1 chapters, index says 50" in report.problems
    assert "31 verses, index says 1533" in report.problems


def test_an_empty_verse_fails(tmp_path: Path, config, books) -> None:
    text = _fixture("genesis_1.json")["text"]
    text[0][4] = "  "
    _write_cache(tmp_path, text=text)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert report.empty_verses == ["Genesis 1:5"]


def test_unknown_markup_fails_with_the_reference(tmp_path: Path, config, books) -> None:
    text = _fixture("genesis_1.json")["text"]
    text[0][1] = "<u>" + text[0][1] + "</u>"
    _write_cache(tmp_path, text=text)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert len(report.unknown_markup) == 1
    assert "Genesis 1:2" in report.unknown_markup[0]


def test_commentary_on_a_verse_the_text_lacks_fails(tmp_path: Path, config, books) -> None:
    rashi = _fixture("rashi_genesis_1.json")["text"]
    rashi[0].extend([[] for _ in range(40 - len(rashi[0]))])
    rashi[0][39] = ["<b>א.</b> ב"]
    _write_cache(tmp_path, rashi=rashi)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert any("1:40 has no verse" in p for p in report.problems)


@pytest.mark.parametrize("indexed", [56, 54])
def test_an_entry_count_off_the_index_is_a_warning(tmp_path: Path, config, books, indexed) -> None:
    """The commentary index counts every version together (Rashi on Genesis 21:2 is only in
    Metsudah) and is sometimes stale (Rashi on Jonah: 53 in Sefaria's merge, 51 indexed)."""
    _write_cache(tmp_path, rashi_lengths=[1, 24, indexed])
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert report.ok
    assert any(f"55 entries, the index counts {indexed}" in w for w in report.warnings)


def test_invisible_characters_need_no_glyph(tmp_path: Path, config, books) -> None:
    rashi = _fixture("rashi_genesis_1.json")["text"]
    rashi[0][0][0] = rashi[0][0][0] + " \u202aא\u202c\u034f\u200d"
    _write_cache(tmp_path, rashi=rashi)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert report.missing_glyphs == []


def test_nfc_decomposing_a_presentation_form_is_not_a_loss(tmp_path: Path, config, books) -> None:
    """Rashi on Genesis 43:10:1 carries precomposed letters (U+FB3B כּ); NFC splits them
    into letter + dagesh. Same text, so it is counted, not failed."""
    rashi = _fixture("rashi_genesis_1.json")["text"]
    rashi[0][0][0] = rashi[0][0][0] + " כּבר"
    _write_cache(tmp_path, rashi=rashi)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert report.nfc_decomposed == 1
    assert report.nfc_lossy == []


def test_a_character_missing_from_a_font_is_a_warning(tmp_path: Path, config, books) -> None:
    text = _fixture("genesis_1.json")["text"]
    text[0][0] = text[0][0] + " ☃"
    _write_cache(tmp_path, text=text)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    assert report.ok
    assert any("U+2603 SNOWMAN" in w and "Genesis 1:1" in w for w in report.warnings)


def test_oversized_chapter_files_fail(tmp_path: Path, config, books) -> None:
    _write_cache(tmp_path)
    report = validate_book(
        _local(tmp_path, books),
        config,
        books.by_title("Genesis"),
        render=lambda chapters: [("genesis-001.xhtml", 400 * 1024)],
    )
    assert report.oversized == ["genesis-001.xhtml (400 KB)"]


def test_report_names_the_versions_and_the_result(tmp_path: Path, config, books) -> None:
    _write_cache(tmp_path)
    report = validate_book(_local(tmp_path, books), config, books.by_title("Genesis"))
    text = format_report([report], config, books)
    assert TANAKH in text and RASHI in text
    assert "Books checked:        1 / 39" in text
    assert "RESULT: clean" in text


# ---- Commands ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["validate", "inventory-markup"])
def test_commands_refuse_an_empty_cache(command: str, tmp_path: Path, capsys) -> None:
    assert main([command, "--book", "Genesis", "--cache-dir", str(tmp_path)]) == 1
    assert "Run `fetch` first" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["validate", "inventory-markup"])
def test_commands_run_over_a_cache(command: str, tmp_path: Path, capsys) -> None:
    _write_cache(tmp_path)
    report = tmp_path / "report.txt"
    code = main(
        [command, "--book", "Genesis", "--cache-dir", str(tmp_path), "--output", str(report)]
    )
    assert code == 0, capsys.readouterr().out
    assert report.is_file()

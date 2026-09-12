"""SPEC.md §30 — configuration, and the things it must refuse."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tanakh_epub.config import load_commentators, load_config
from tanakh_epub.paths import DEFAULT_CONFIG


def _config_with(tmp_path: Path, **changes) -> Path:
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for dotted, value in changes.items():
        node = raw
        *parents, leaf = dotted.split(".")
        for key in parents:
            node = node[key]
        if value is None:
            node.pop(leaf, None)
        else:
            node[leaf] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def test_default_config_loads(config) -> None:
    assert config.title == "תנ״ך עם פירוש רש״י"
    assert config.commentaries == ("Rashi",)
    assert config.layout.max_file_kb == 300
    assert config.layout.file_per == "chapter"


def test_commentator_labels_come_from_config_not_code() -> None:
    commentators = load_commentators()
    assert commentators["Rashi"].hebrew == "רש״י"
    assert commentators["Rashi"].slug == "rashi"
    assert commentators["Rashi"].index_title("Genesis") == "Rashi on Genesis"
    assert commentators["Rashi"].index_title("I Samuel") == "Rashi on I Samuel"


def test_unknown_commentator_fails_loudly(config) -> None:
    with pytest.raises(KeyError, match="never hard-coded"):
        config.commentator("Ramban")


def test_a_font_without_a_recorded_license_is_refused(tmp_path: Path) -> None:
    """CLAUDE.md non-negotiable 9."""
    path = _config_with(
        tmp_path,
        **{
            "fonts.biblical": {
                "file": "fonts/TaameyFrankCLM-Medium.ttf",
                "family": "X",
                "name": "X",
                "license": "",
            }
        },
    )
    with pytest.raises(ValueError, match="license"):
        load_config(path)


def test_a_missing_font_file_is_refused(tmp_path: Path) -> None:
    path = _config_with(
        tmp_path,
        **{
            "fonts.biblical": {
                "file": "fonts/nope.ttf",
                "family": "X",
                "name": "X",
                "license": "whatever",
            }
        },
    )
    with pytest.raises(FileNotFoundError):
        load_config(path)


def test_one_file_per_book_is_not_configurable(tmp_path: Path) -> None:
    """SPEC §11 withdrew it: Psalms and Genesis+Rashi blow past Amazon's ~300 KB."""
    path = _config_with(tmp_path, **{"layout.file_per": "book"})
    with pytest.raises(ValueError, match="file_per"):
        load_config(path)


def test_a_commentator_without_a_source_is_refused(tmp_path: Path) -> None:
    path = _config_with(tmp_path, **{"sources.commentaries": {}})
    with pytest.raises(ValueError, match=r"sources\.commentaries"):
        load_config(path)


def test_an_unknown_commentator_in_include_is_refused(tmp_path: Path) -> None:
    path = _config_with(tmp_path, **{"include.commentaries": ["Ramban"]})
    with pytest.raises(ValueError, match=r"commentators\.yaml"):
        load_config(path)


def test_config_hash_is_stable(config) -> None:
    assert config.config_hash == load_config().config_hash
    assert config.config_hash.startswith("sha256:")


def test_both_sources_record_a_license(config) -> None:
    """CC BY-SA on the Tanakh text requires naming the source and the license."""
    assert config.tanakh_source.license
    assert config.commentary_sources["Rashi"].license
    assert config.biblical_font.license
    assert config.rashi_font.license


def test_font_license_files_exist(config) -> None:
    for font in (config.biblical_font, config.rashi_font):
        assert font.license_file is not None, font.family
        assert font.license_file.is_file(), font.license_file

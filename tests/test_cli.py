"""SPEC.md §31 — the command line."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tanakh_epub.cli import main


def test_build_chapter_produces_an_epub(tmp_path: Path, capsys) -> None:
    output = tmp_path / "Genesis_Chapter_1.epub"
    assert (
        main(["build", "--chapter", "Genesis", "1", "--max-verse", "10", "--output", str(output)])
        == 0
    )
    assert output.is_file()
    with zipfile.ZipFile(output) as zf:
        assert "OEBPS/text/genesis-001.xhtml" in zf.namelist()
    out = capsys.readouterr().out
    assert "verses             10" in out
    assert "Miqra according to the Masorah" in out


def test_build_reports_the_versions_it_used(tmp_path: Path, capsys) -> None:
    main(["build", "--chapter", "Genesis", "1", "--output", str(tmp_path / "g.epub")])
    out = capsys.readouterr().out
    assert "text version       Miqra according to the Masorah (1 book)" in out
    assert "commentary version Rashi:" in out


def test_no_commentary_builds_verses_only(tmp_path: Path, capsys) -> None:
    output = tmp_path / "plain.epub"
    assert (
        main(["build", "--chapter", "Genesis", "1", "--no-commentary", "--output", str(output)])
        == 0
    )
    with zipfile.ZipFile(output) as zf:
        page = zf.read("OEBPS/text/genesis-001.xhtml").decode("utf-8")
    assert "commentary-entry" not in page
    assert "רש״י" not in page


def test_check_runs_and_reports(tmp_path: Path, capsys) -> None:
    output = tmp_path / "g.epub"
    main(["build", "--chapter", "Genesis", "1", "--output", str(output)])
    code = main(["check", str(output)])
    report = capsys.readouterr().out
    assert "EPUBCheck" in report
    assert "Kindle Previewer" in report
    assert code in (0, 1)


def test_check_on_a_missing_file_fails(tmp_path: Path) -> None:
    assert main(["check", str(tmp_path / "nope.epub")]) == 1


@pytest.mark.parametrize("command", ["fetch", "validate", "inventory-markup"])
def test_phase_two_commands_exist(command: str, capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([command, "--help"])
    assert excinfo.value.code == 0
    assert "--book" in capsys.readouterr().out


def test_unknown_book_fails_loudly() -> None:
    with pytest.raises(KeyError):
        main(["build", "--chapter", "Bereshit", "1"])

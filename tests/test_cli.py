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


# ---- Never a partial book (SPEC_DATA_SOURCE.md §17) ------------------------------------


def test_a_full_build_without_a_download_fails_and_says_what_to_run(tmp_path, capsys) -> None:
    """With nothing fetched, the fixture could still supply Genesis 1 — which is exactly the
    one-chapter "Tanakh" this must never produce."""
    output = tmp_path / "Tanakh_with_Rashi.epub"
    assert main(["build", "--output", str(output)]) == 1
    assert not output.exists()
    err = capsys.readouterr().err
    assert "Not downloaded yet: any book" in err
    assert "`python -m tanakh_epub fetch`" in err


def test_a_whole_book_build_does_not_fall_back_to_the_fixture(tmp_path, capsys) -> None:
    assert main(["build", "--book", "Genesis", "--output", str(tmp_path / "g.epub")]) == 1
    assert 'fetch --books "Genesis"' in capsys.readouterr().err


def test_the_missing_books_are_named(tmp_path, capsys) -> None:
    args = ["build", "--books", "Genesis", "I Samuel", "--output", str(tmp_path / "x.epub")]
    assert main(args) == 1
    assert 'fetch --books "Genesis" "I Samuel"' in capsys.readouterr().err


def test_a_single_chapter_may_still_use_the_fixture(tmp_path) -> None:
    output = tmp_path / "Genesis_Chapter_1.epub"
    assert main(["build", "--chapter", "Genesis", "1", "--output", str(output)]) == 0
    assert output.is_file()


def test_a_chapter_the_fixture_lacks_fails_cleanly(tmp_path, capsys) -> None:
    assert main(["build", "--chapter", "Genesis", "2", "--output", str(tmp_path / "g.epub")]) == 1
    assert "no chapter 2" in capsys.readouterr().err

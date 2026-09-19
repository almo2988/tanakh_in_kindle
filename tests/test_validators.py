"""SPEC.md §3.2, §33 — the external validators.

Both are skipped with a clear message when the tool is absent. A skipped check is never
reported as a pass; a release check has to tell the two apart.
"""

from __future__ import annotations

import pytest

from tanakh_epub.validation_tools import (
    find_epubcheck,
    find_kindle_previewer,
    run_epubcheck,
    run_kindle_previewer,
)


@pytest.mark.epubcheck
def test_poc_epub_passes_epubcheck(poc_epub) -> None:
    if find_epubcheck() is None:
        pytest.skip(
            "EPUBCheck not installed — run scripts/epubcheck.sh once to fetch it into "
            "tools/, or set EPUBCHECK_JAR. Structural validity is NOT verified."
        )
    result = run_epubcheck(poc_epub)
    assert result.passed, result.output


@pytest.mark.kindle_previewer
def test_poc_epub_converts_in_kindle_previewer(poc_epub, tmp_path) -> None:
    if find_kindle_previewer() is None:
        pytest.skip(
            "Kindle Previewer not installed (macOS/Windows only). "
            "Kindle-specific rendering is NOT verified."
        )
    result = run_kindle_previewer(poc_epub, tmp_path / "kpf")
    assert result.passed, result.output


def test_a_missing_tool_reports_skipped_not_passed(poc_epub, monkeypatch) -> None:
    monkeypatch.setattr("tanakh_epub.validation_tools.find_epubcheck", lambda: None)
    result = run_epubcheck(poc_epub)
    assert result.skipped
    assert not result.passed
    assert "EPUBCHECK_JAR" in result.message

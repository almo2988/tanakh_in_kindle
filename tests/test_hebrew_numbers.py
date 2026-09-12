"""SPEC.md §8, §33 — Hebrew numerals."""

from __future__ import annotations

import pytest

from tanakh_epub.processing.hebrew_numbers import (
    GERESH,
    GERSHAYIM,
    chapter_label,
    hebrew_letters,
    int_to_hebrew_numeral,
    reference_label,
    verse_label,
)

# The values SPEC.md §33 names explicitly, plus the neighbours of the 15/16 rule.
EXPECTED = {
    1: "א׳",
    2: "ב׳",
    9: "ט׳",
    10: "י׳",
    11: "י״א",
    14: "י״ד",
    15: "ט״ו",
    16: "ט״ז",
    17: "י״ז",
    20: "כ׳",
    22: "כ״ב",
    100: "ק׳",
    115: "קט״ו",
    116: "קט״ז",
    150: "ק״נ",
    176: "קע״ו",
    316: "שט״ז",
    400: "ת׳",
    500: "ת״ק",
}


@pytest.mark.parametrize(("number", "expected"), sorted(EXPECTED.items()))
def test_numerals(number: int, expected: str) -> None:
    assert int_to_hebrew_numeral(number) == expected


def test_uses_real_geresh_and_gershayim_not_ascii() -> None:
    """ASCII ' and " look almost identical in a terminal and wrong on the device."""
    for number in EXPECTED:
        rendered = int_to_hebrew_numeral(number)
        assert "'" not in rendered
        assert '"' not in rendered
    assert int_to_hebrew_numeral(1).endswith(GERESH)
    assert GERSHAYIM in int_to_hebrew_numeral(11)


def test_geresh_only_on_single_letter_numerals() -> None:
    for number in EXPECTED:
        letters = hebrew_letters(number)
        rendered = int_to_hebrew_numeral(number)
        if len(letters) == 1:
            assert rendered == letters + GERESH
        else:
            assert rendered == letters[:-1] + GERSHAYIM + letters[-1]


def test_fifteen_and_sixteen_rule_inside_larger_numbers() -> None:
    assert hebrew_letters(15) == "טו"
    assert hebrew_letters(16) == "טז"
    assert hebrew_letters(115) == "קטו"
    assert hebrew_letters(316) == "שטז"
    for number in (15, 16, 115, 116, 215, 316, 515):
        assert "יה" not in hebrew_letters(number)
        assert "יו" not in hebrew_letters(number)


def test_labels_are_hebrew_only() -> None:
    assert chapter_label(1) == "פרק א׳"
    assert chapter_label(15) == "פרק ט״ו"
    assert verse_label(11) == "י״א"
    assert reference_label("בראשית", 1, 1) == "בראשית א׳:א׳"


@pytest.mark.parametrize("number", [0, -1, 1000, 5000])
def test_out_of_range_fails_loudly(number: int) -> None:
    """A silently wrong numeral is worse than a stopped build."""
    with pytest.raises(ValueError):
        int_to_hebrew_numeral(number)


def test_non_integer_fails_loudly() -> None:
    with pytest.raises(TypeError):
        int_to_hebrew_numeral(1.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        int_to_hebrew_numeral(True)  # type: ignore[arg-type]

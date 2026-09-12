"""Hebrew numerals — SPEC.md §8.

Chapter and verse numbers are the only numbers the reader ever sees, and they are always
Hebrew: `פרק א׳`, `י״א`, `ט״ו`, `קט״ו`. Real geresh (U+05F3) and gershayim (U+05F4) are
used, never the ASCII apostrophe and quote — they look almost identical in a terminal and
completely wrong on the device.
"""

from __future__ import annotations

GERESH = "׳"
"""U+05F3 HEBREW PUNCTUATION GERESH — after a single-letter numeral."""

GERSHAYIM = "״"
"""U+05F4 HEBREW PUNCTUATION GERSHAYIM — before the last letter of a multi-letter numeral."""

_HUNDREDS = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"]
_TENS = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
_UNITS = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]

_MAX = 999
"""The largest chapter or verse number in the Tanakh is 176 (תהלים קי״ט); 999 is
head-room, not a promise. Thousands are deliberately unsupported: a silently wrong
numeral is worse than a loud failure."""


def hebrew_letters(number: int) -> str:
    """The bare letters of a Hebrew numeral, with no geresh or gershayim.

    Applies the 15/16 rule — ``טו`` and ``טז`` rather than ``יה`` and ``יו`` — including
    inside larger numbers, so 115 is ``קטו`` and 316 is ``שטז``.
    """
    if not isinstance(number, int) or isinstance(number, bool):
        raise TypeError(f"Hebrew numerals need an int, got {type(number).__name__}")
    if not 1 <= number <= _MAX:
        raise ValueError(f"Cannot write {number} as a Hebrew numeral (supported range: 1–{_MAX})")

    hundreds, remainder = divmod(number, 100)
    letters = _HUNDREDS[hundreds]

    # The 15/16 rule: the pairs that would spell a name of God are written one letter down.
    if remainder == 15:
        return letters + "טו"
    if remainder == 16:
        return letters + "טז"

    tens, units = divmod(remainder, 10)
    return letters + _TENS[tens] + _UNITS[units]


def int_to_hebrew_numeral(number: int) -> str:
    """A displayable Hebrew numeral — SPEC.md §8.1.

    >>> int_to_hebrew_numeral(1)
    'א׳'
    >>> int_to_hebrew_numeral(15)
    'ט״ו'
    >>> int_to_hebrew_numeral(115)
    'קט״ו'
    """
    letters = hebrew_letters(number)
    if len(letters) == 1:
        return letters + GERESH
    return letters[:-1] + GERSHAYIM + letters[-1]


def chapter_label(chapter: int) -> str:
    """The chapter heading text: ``פרק א׳``."""
    return f"פרק {int_to_hebrew_numeral(chapter)}"


def verse_label(verse: int) -> str:
    """The verse number as rendered next to the verse: ``א׳``."""
    return int_to_hebrew_numeral(verse)


def reference_label(hebrew_book_title: str, chapter: int, verse: int) -> str:
    """A full Hebrew reference: ``בראשית א׳:א׳`` — SPEC_DATA_SOURCE.md §16."""
    return f"{hebrew_book_title} {int_to_hebrew_numeral(chapter)}:{int_to_hebrew_numeral(verse)}"

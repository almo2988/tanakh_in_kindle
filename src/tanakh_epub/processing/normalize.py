"""Unicode and whitespace normalization — SPEC.md §7, SPEC_DATA_SOURCE.md §7.

The only two transformations allowed here are NFC and ASCII whitespace collapsing.
Nothing strips combining marks, and NFKC/NFKD are never used: they would fold Hebrew
presentation forms and destroy the text this whole project exists to preserve.
"""

from __future__ import annotations

import unicodedata

NBSP = " "
THIN_SPACE = " "

_COLLAPSIBLE = " \t\r\n\v\f"
"""Only ASCII whitespace collapses. U+00A0 and U+2009 are typography the source chose
deliberately — they space the paseq and the parasha marker — and survive untouched."""


def to_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def is_nfc(text: str) -> bool:
    return unicodedata.is_normalized("NFC", text)


def collapse_whitespace(text: str, *, preserve_paragraphs: bool = False) -> str:
    """Collapse runs of ASCII whitespace to a single space and trim the ends.

    With ``preserve_paragraphs``, a blank line (the internal paragraph separator) survives
    as ``\\n\\n``; every other run still collapses.
    """
    if preserve_paragraphs:
        parts = text.split("\n\n")
        collapsed = [collapse_whitespace(part) for part in parts]
        return "\n\n".join(part for part in collapsed if part)

    out: list[str] = []
    pending_space = False
    for char in text:
        if char in _COLLAPSIBLE:
            pending_space = bool(out)
            continue
        if pending_space:
            out.append(" ")
            pending_space = False
        out.append(char)
    return "".join(out)


def normalize(text: str, *, preserve_paragraphs: bool = False) -> str:
    """NFC, then whitespace. In that order — NFC can compose a mark onto a base letter,
    and doing it after the whitespace pass would leave the result unnormalized."""
    return collapse_whitespace(to_nfc(text), preserve_paragraphs=preserve_paragraphs)

"""SPEC.md §7, §33 — the Hebrew text is never altered."""

from __future__ import annotations

import json
import unicodedata
from collections import Counter

from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.processing.normalize import collapse_whitespace, normalize, to_nfc

NIKKUD_AND_TEAMIM = range(0x0591, 0x05C8)
"""U+0591–U+05C7: טעמי המקרא, ניקוד, meteg, and the rest of the combining block."""


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_nfc_round_trips_the_fixture_losslessly() -> None:
    """SPEC §33: normalizing the source must not drop a single mark.

    NFC *reorders* Hebrew combining marks — Sefaria stores them in typing order (dagesh
    before vowel) and NFC sorts them by canonical combining class. That is canonical
    equivalence, not loss: same characters, same count, same text by Unicode's own
    definition. What this test guards is that nothing disappears.
    """
    for name in ("genesis_1.json", "rashi_genesis_1.json"):
        for raw in _flatten(_fixture(name)["text"]):
            normalized = to_nfc(raw)
            assert unicodedata.is_normalized("NFC", normalized)
            assert len(normalized) == len(raw)
            assert Counter(normalized) == Counter(raw)
            assert to_nfc(normalized) == normalized, "NFC is not idempotent here"


def test_nfc_reorders_marks_but_stays_canonically_equivalent() -> None:
    """Pinning the behaviour found in the captured data, because it has a device
    consequence: Taamey Frank positions marks by typing order, and NFC changes that
    order. Whether the font's OpenType logic copes is a Paperwhite question (D2), not a
    desktop one — see the Phase 1 device checklist.
    """
    source = _fixture("genesis_1.json")["text"][0][0]
    assert not unicodedata.is_normalized("NFC", source), "fixture is already NFC; note is stale"
    normalized = to_nfc(source)
    assert normalized != source
    assert unicodedata.normalize("NFD", normalized) == unicodedata.normalize("NFD", source)


def test_fixture_carries_nikkud_and_teamim() -> None:
    """The whole point of the chosen version — a nikud-only text would pass everything
    else in this suite and be the wrong book."""
    first_verse = _fixture("genesis_1.json")["text"][0][0]
    marks = _marks(first_verse)
    assert marks, "no combining marks at all in בראשית א׳:א׳"
    assert any(0x0591 <= ord(c) <= 0x05AF for c in first_verse), "no טעמים in בראשית א׳:א׳"
    assert any(0x05B0 <= ord(c) <= 0x05BC for c in first_verse), "no ניקוד in בראשית א׳:א׳"


def test_whitespace_collapse_keeps_meaningful_spaces() -> None:
    assert collapse_whitespace("  א   ב \n ג  ") == "א ב ג"
    assert collapse_whitespace("א ב") == "א ב"
    assert collapse_whitespace("א ב") == "א ב"


def test_paragraph_separator_survives_collapsing() -> None:
    assert normalize("א  \n\n  ב", preserve_paragraphs=True) == "א\n\nב"
    assert normalize("א  \n\n  ", preserve_paragraphs=True) == "א"


def test_normalization_never_removes_combining_marks() -> None:
    verse = _fixture("genesis_1.json")["text"][0][0]
    assert Counter(_marks(normalize(verse))) == Counter(_marks(verse))


def test_nfkc_and_nfkd_are_never_used() -> None:
    """SPEC §7: compatibility normalization folds Hebrew presentation forms away.

    U+FB4F HEBREW LIGATURE ALEF LAMED is the clearest case — NFKC splits it into two
    letters and silently rewrites the text; NFC leaves it exactly as the source had it.
    """
    ligature = "\ufb4f"
    assert unicodedata.normalize("NFKC", ligature) != ligature
    assert normalize(ligature) == ligature
    assert to_nfc(ligature) == ligature


def _flatten(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    return [s for child in node for s in _flatten(child)]


def _marks(text: str) -> list[str]:
    return [c for c in text if ord(c) in NIKKUD_AND_TEAMIM]

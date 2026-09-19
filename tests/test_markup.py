"""SPEC_DATA_SOURCE.md §8, §9 — markup conversion, and what happens to anything unknown."""

from __future__ import annotations

import json

import pytest

from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.processing.markup import (
    PARAGRAPH_SEPARATOR,
    InternalMarkupError,
    UnknownMarkupError,
    assert_internal_markup_only,
    convert_commentary_entry,
    convert_verse,
    paragraphs,
)

REF = "Genesis 1:1"


def test_enlarged_letter_becomes_letter_large() -> None:
    assert convert_verse("<big>בְּ</big>רֵאשִׁית", reference=REF) == (
        '<span class="letter-large">בְּ</span>רֵאשִׁית'
    )


def test_reduced_letter_and_paseq_become_letter_small() -> None:
    assert convert_verse("אֱלֹהִים<small>׀</small>לָאוֹר", reference=REF) == (
        'אֱלֹהִים<span class="letter-small">׀</span>לָאוֹר'
    )


def test_bold_outside_a_leading_position_is_kept() -> None:
    assert convert_verse("עֵשֶׂב<b>׀</b> זֹרֵעַ", reference=REF) == "עֵשֶׂב<b>׀</b> זֹרֵעַ"


def test_parasha_marker_is_mapped_and_ends_the_paragraph() -> None:
    converted = convert_verse(
        'אֶחָד׃&nbsp;<span class="mam-spi-pe">{פ}</span><br>וַיֹּאמֶר', reference=REF
    )
    assert '<span class="parasha-marker">{פ}</span>' in converted
    assert paragraphs(converted) == [
        'אֶחָד׃ <span class="parasha-marker">{פ}</span>',
        "וַיֹּאמֶר",
    ]


def test_named_entities_become_their_characters_and_survive_normalization() -> None:
    """&nbsp; and &thinsp; are deliberate typography, not collapsible whitespace."""
    converted = convert_verse("אֱלֹהִים&thinsp;לָאוֹר&nbsp;כִּי", reference=REF)
    assert converted == "אֱלֹהִים לָאוֹר כִּי"


def test_dibur_hamatchil_is_taken_from_the_leading_bold_element() -> None:
    entry = convert_commentary_entry(
        "<b>בראשית.</b> אָמַר רַבִּי יִצְחָק", reference="Rashi on Genesis 1:1:1"
    )
    assert entry.dibur_hamatchil == "בראשית."
    assert entry.text == "אָמַר רַבִּי יִצְחָק"
    assert "<b>" not in entry.text


def test_bold_that_does_not_lead_is_not_a_dibur_hamatchil() -> None:
    entry = convert_commentary_entry("אָמַר <b>רַבִּי</b> יִצְחָק", reference="Rashi on Genesis 1:1:1")
    assert entry.dibur_hamatchil is None
    assert entry.text == "אָמַר <b>רַבִּי</b> יִצְחָק"


def test_unknown_tag_fails_the_build() -> None:
    with pytest.raises(UnknownMarkupError) as excinfo:
        convert_verse("בְּרֵאשִׁית<u>בָּרָא</u>", reference=REF)
    assert "<u>" in str(excinfo.value)
    assert REF in str(excinfo.value)


def test_known_tag_with_an_unknown_class_fails_the_build() -> None:
    """On MAM spans the class carries the whole meaning; ignoring it loses content."""
    with pytest.raises(UnknownMarkupError) as excinfo:
        convert_verse('<span class="mam-not-a-real-class">קרי</span>', reference=REF)
    assert "mam-not-a-real-class" in str(excinfo.value)


def test_unexpected_attribute_fails_the_build() -> None:
    with pytest.raises(UnknownMarkupError):
        convert_verse('<b id="x">׀</b>', reference=REF)


def test_text_is_escaped_so_it_cannot_become_markup() -> None:
    assert convert_verse("a < b & c", reference=REF) == "a &lt; b &amp; c"


def test_internal_markup_audit_rejects_anything_outside_the_subset() -> None:
    internal = '<b>x</b><em>y</em><span class="letter-large">z</span>'
    assert_internal_markup_only(internal, reference=REF)
    with pytest.raises(InternalMarkupError):
        assert_internal_markup_only("<u>x</u>", reference=REF)
    with pytest.raises(InternalMarkupError):
        assert_internal_markup_only('<span class="mam-spi-pe">{פ}</span>', reference=REF)
    with pytest.raises(InternalMarkupError):
        assert_internal_markup_only("<span>x</span>", reference=REF)


# ---- against the real fixtures ------------------------------------------


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_every_fixture_verse_converts_to_internal_markup_only() -> None:
    chapter = _fixture("genesis_1.json")["text"][0]
    assert len(chapter) == 31
    for index, raw in enumerate(chapter, start=1):
        reference = f"Genesis 1:{index}"
        converted = convert_verse(raw, reference=reference)
        assert converted
        assert_internal_markup_only(converted, reference=reference)


def test_every_fixture_rashi_entry_converts_and_keeps_its_dibur_hamatchil() -> None:
    chapter = _fixture("rashi_genesis_1.json")["text"][0]
    entries = 0
    for verse_index, verse_entries in enumerate(chapter, start=1):
        for entry_index, raw in enumerate(verse_entries, start=1):
            reference = f"Rashi on Genesis 1:{verse_index}:{entry_index}"
            entry = convert_commentary_entry(raw, reference=reference)
            assert_internal_markup_only(entry.text, reference=reference)
            assert entry.dibur_hamatchil, reference
            entries += 1
    assert entries == 55


# ---- Rules added from the Phase 2 inventory of Genesis ------------------------------
# The inputs are real strings from Genesis (MAM) and Rashi on Genesis, cut to the part
# that matters.


def test_open_parasha_marker_is_kept_and_does_not_end_the_paragraph() -> None:
    raw = 'עָקֵֽב׃&nbsp;<span class="mam-spi-samekh">{ס}</span>&nbsp;&nbsp;'
    out = convert_verse(raw, reference="Genesis 3:15")
    assert '<span class="parasha-marker">{ס}</span>' in out
    assert PARAGRAPH_SEPARATOR not in out


def test_ketiv_qere_keeps_both_readings_and_their_brackets() -> None:
    raw = (
        'הָאָ֖רֶץ <span class="mam-kq"><span class="mam-kq-k">(הוצא)</span> '
        '<span class="mam-kq-q">[הַיְצֵ֣א]</span></span> אִתָּ֑ךְ'
    )
    out = convert_verse(raw, reference="Genesis 8:17")
    assert out == "הָאָ֖רֶץ (הוצא) [הַיְצֵ֣א] אִתָּ֑ךְ"


def test_trivial_ketiv_qere_keeps_the_word() -> None:
    raw = 'שָׁ֤ם <span class="mam-kq-trivial">אׇֽהֳלֹה֙</span> בַּתְּחִלָּ֔ה'
    assert convert_verse(raw, reference="Genesis 13:3") == "שָׁ֤ם אׇֽהֳלֹה֙ בַּתְּחִלָּ֔ה"


def test_unwrapped_span_inside_bold_stays_inside_the_bold() -> None:
    out = convert_verse('<b>א<span class="mam-kq-trivial">ב</span>ג</b>', reference=REF)
    assert out == "<b>אבג</b>"


def test_mam_footnote_is_dropped_with_its_content() -> None:
    raw = (
        'מִנְּשֹֽׂא<sup class="footnote-marker">*</sup><i class="footnote">(בספרי ספרד ואשכנז מִנְּשֽׂוֹא)</i>׃'
    )
    assert convert_verse(raw, reference="Genesis 4:13") == "מִנְּשֹֽׂא׃"


def test_footnote_with_nested_markup_is_dropped_whole() -> None:
    raw = (
        'סֵ֗פֶר<sup class="footnote-marker">*</sup>'
        '<i class="footnote">(בספרי תימן <big>סֵ֔</big>פֶר בסמ״ך גדולה)</i> תּֽוֹלְדֹ֖ת'
    )
    assert convert_verse(raw, reference="Genesis 5:1") == "סֵ֗פֶר תּֽוֹלְדֹ֖ת"


def test_small_inside_a_rashi_entry() -> None:
    raw = '<b>המול ימול.</b> לְאַחַר (<small>ס"א</small> לְאֶחָד) כְּמוֹ'
    entry = convert_commentary_entry(raw, reference="Rashi on Genesis 17:13:1")
    assert entry.dibur_hamatchil == "המול ימול."
    assert '(<span class="letter-small">ס"א</span> לְאֶחָד)' in entry.text


def test_an_italic_without_the_footnote_class_is_still_unknown() -> None:
    """`<i>` alone has not been seen yet; only MAM's footnote class has a rule."""
    with pytest.raises(UnknownMarkupError):
        convert_verse("<i>x</i>", reference=REF)

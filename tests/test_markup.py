"""SPEC_DATA_SOURCE.md §8, §9 — markup conversion, and what happens to anything unknown."""

from __future__ import annotations

import json

import pytest

from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.processing.markup import (
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
        convert_verse('<span class="mam-kq-q">קרי</span>', reference=REF)
    assert "mam-kq-q" in str(excinfo.value)


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

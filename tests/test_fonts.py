"""SPEC.md §15, §16, §33 — the embedded fonts.

A font that is missing a character does not fail the build; it renders a blank box on the
device, and only on the device. These tests read each font's own `cmap` and check it
against the actual Hebrew in the fixtures, so a font swap cannot ship tofu unnoticed.
"""

from __future__ import annotations

import json
import re
import unicodedata

import pytest

from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.processing.hebrew_numbers import chapter_label, int_to_hebrew_numeral
from tanakh_epub.processing.normalize import to_nfc

fontTools = pytest.importorskip("fontTools", reason="fonttools is a dev dependency")
from fontTools.ttLib import TTFont  # noqa: E402


def _codepoints(font_path) -> set[int]:
    return set(TTFont(font_path).getBestCmap())


def _text_characters(fixture_name: str) -> set[str]:
    """Every character that can reach a font from one fixture.

    Tags are stripped and the two named entities resolved, because that is what the
    conversion pipeline does before any of this is rendered.
    """
    raw = json.loads((FIXTURES_DIR / fixture_name).read_text(encoding="utf-8"))

    def flatten(node):
        return [node] if isinstance(node, str) else [s for child in node for s in flatten(child)]

    characters: set[str] = set()
    for string in flatten(raw["text"]):
        stripped = re.sub(r"<[^>]*>", "", string)
        stripped = stripped.replace("&nbsp;", " ").replace("&thinsp;", " ")
        characters |= set(to_nfc(stripped))
    return {c for c in characters if not c.isspace()}


def _report_missing(needed: set[str], covered: set[int], font_name: str) -> None:
    missing = sorted(c for c in needed if ord(c) not in covered)
    assert not missing, f"{font_name} has no glyph for: " + ", ".join(
        f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in missing
    )


def test_biblical_font_covers_every_character_of_the_tanakh_fixture(config) -> None:
    _report_missing(
        _text_characters("genesis_1.json"),
        _codepoints(config.biblical_font.file),
        config.biblical_font.name,
    )


def test_rashi_font_covers_every_character_of_the_commentary_fixture(config) -> None:
    _report_missing(
        _text_characters("rashi_genesis_1.json"),
        _codepoints(config.rashi_font.file),
        config.rashi_font.name,
    )


def test_biblical_font_covers_the_hebrew_numerals_and_headings(config) -> None:
    """Verse numbers and `פרק א׳` are set in the biblical font."""
    needed = set("פרק")
    for number in (1, 11, 15, 16, 115, 150, 176):
        needed |= set(chapter_label(number)) | set(int_to_hebrew_numeral(number))
    _report_missing(
        {c for c in needed if not c.isspace()},
        _codepoints(config.biblical_font.file),
        config.biblical_font.name,
    )


def test_biblical_font_carries_nikkud_and_teamim(config) -> None:
    """The whole reason a font is embedded at all — the stock Kindle Hebrew face stacks
    these badly (SPEC §0)."""
    covered = _codepoints(config.biblical_font.file)
    teamim = [c for c in covered if 0x0591 <= c <= 0x05AF]
    nikkud = [c for c in covered if 0x05B0 <= c <= 0x05C7]
    assert len(teamim) >= 25, f"only {len(teamim)} טעמים in {config.biblical_font.name}"
    assert len(nikkud) >= 15, f"only {len(nikkud)} ניקוד marks in {config.biblical_font.name}"


@pytest.mark.parametrize("role", ["biblical", "rashi"])
def test_fonts_permit_embedding(config, role: str) -> None:
    """CLAUDE.md non-negotiable 9. fsType 2 would forbid embedding outright."""
    font = config.biblical_font if role == "biblical" else config.rashi_font
    assert TTFont(font.file)["OS/2"].fsType == 0, f"{font.name} restricts embedding"


@pytest.mark.parametrize("role", ["biblical", "rashi"])
def test_fonts_are_static_not_variable(config, role: str) -> None:
    """Variable fonts are not known to survive Kindle's KFX conversion."""
    font = config.biblical_font if role == "biblical" else config.rashi_font
    assert "fvar" not in TTFont(font.file), f"{font.name} is a variable font"


@pytest.mark.parametrize("role", ["biblical", "rashi"])
def test_config_font_metadata_matches_the_file(config, role: str) -> None:
    """The name in config is what the מקורות page and the OPF report; it must be the
    font actually embedded, not the one someone meant to embed."""
    font = config.biblical_font if role == "biblical" else config.rashi_font
    names = {}
    for record in TTFont(font.file)["name"].names:
        try:
            names.setdefault(record.nameID, record.toUnicode())
        except UnicodeDecodeError:
            continue
    family = names[1]
    assert family in font.name, f'config calls it "{font.name}", the file says "{family}"'
    assert font.family == family, (
        f'config declares the CSS family as "{font.family}" but the font calls itself '
        f'"{family}". They must match: a reader that resolves an embedded font by its own '
        f"name rather than by the @font-face family will otherwise fall back silently."
    )
    assert font.suffix in (".ttf", ".otf"), "WOFF does not survive Kindle conversion"

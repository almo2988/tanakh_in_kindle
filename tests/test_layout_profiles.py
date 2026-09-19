"""The layout experiment — docs/LAYOUT_EXPERIMENT.md, SPEC.md §13, §14, §24, §26, §27.

Three layout profiles, one renderer. These tests pin what each profile emits, hold every
profile to the same Kindle-safe CSS rules, and prove that the EPUBs say exactly the
same thing and differ only in how it is laid out.
"""

from __future__ import annotations

import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from tanakh_epub.cli import main
from tanakh_epub.config import load_config
from tanakh_epub.layout_experiment import (
    PER_VARIANT_FILES,
    build_variants,
    content_differences,
    format_report,
    output_name,
)
from tanakh_epub.paths import DEFAULT_CONFIG
from tanakh_epub.rendering.css import render_css
from tanakh_epub.rendering.html_renderer import ChapterRenderer

XHTML = "{http://www.w3.org/1999/xhtml}"
PROFILES = ["current", "balanced", "dense"]

EXPECTED = {
    # name: label, (biblical, rashi, verse number, divider) scales, (biblical, rashi) line
    # heights, (study unit, verse, entry, paragraph) spacing, and divider alignment.
    "current": {
        "label": "A-current",
        "scales": (1.25, 0.9, 0.75, 0.85),
        "line_heights": (1.9, 1.65),
        "spacing": (1.1, 0.35, 0.4, 0.3),
        "divider": ("center", "0.5em 0 0.4em 0", "0.15em 0 0.15em 0"),
    },
    "balanced": {
        "label": "B-balanced",
        "scales": (1.15, 0.9, 0.72, 0.8),
        "line_heights": (1.75, 1.5),
        "spacing": (0.75, 0.3, 0.25, 0.2),
        "divider": ("right", "0.4em 0 0.25em 0", "0.12em 0 0 0"),
    },
    "dense": {
        "label": "C-dense",
        "scales": (1.1, 0.86, 0.7, 0.78),
        "line_heights": (1.6, 1.42),
        "spacing": (0.55, 0.2, 0.15, 0.12),
        "divider": ("right", "0.3em 0 0.18em 0", "0.08em 0 0 0"),
    },
}

BIBLICAL_INK_EM = 1.24
"""Worst-case ink height of Taamey Frank CLM with ניקוד and טעמים stacked, in em of the
text: 0.93 above the baseline, 0.31 below, measured by shaping with the font's own
OpenType positioning (the method is in config/default.yaml). A biblical line height at or
under this lets marks on adjacent lines touch."""


@pytest.fixture(scope="module")
def profile_configs():
    return {name: load_config(profile=name) for name in PROFILES}


def _rules(css: str) -> dict[str, dict[str, str]]:
    """``{selector: {property: value}}``, merging repeated selectors in source order."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = rules.setdefault(selector.strip(), {})
        for declaration in body.split(";"):
            if ":" in declaration:
                prop, value = declaration.split(":", 1)
                declarations[prop.strip()] = value.strip()
    return rules


# ---- Profiles exist and resolve ------------------------------------------


def test_the_three_profiles_are_defined_in_order(config) -> None:
    assert list(config.layout_profiles) == PROFILES
    assert [p.label for p in config.layout_profiles.values()] == [
        EXPECTED[name]["label"] for name in PROFILES
    ]


def test_hebrew_labels_are_hebrew_and_distinct(config) -> None:
    """The label goes into the reader-visible title of an experiment build."""
    labels = [p.hebrew_label for p in config.layout_profiles.values()]
    assert len(set(labels)) == len(PROFILES)
    for label in labels:
        assert not re.search(r"[A-Za-z]", label), label


def test_a_normal_build_uses_the_control_profile(config) -> None:
    """Existing builds keep rendering exactly as before until D10 picks a layout."""
    assert config.layout_profile.name == "current"


def test_the_control_profile_changes_nothing(config) -> None:
    """A is the control group: it must be the base config sections, untouched."""
    base = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert base["layout_profiles"]["current"].keys() <= {"label", "hebrew_label", "description"}
    t = config.typography
    assert (t.biblical_scale, t.rashi_scale, t.verse_number_scale, t.divider_scale) == (
        base["typography"]["biblical_scale"],
        base["typography"]["rashi_scale"],
        base["typography"]["verse_number_scale"],
        base["typography"]["divider_scale"],
    )


def test_profiles_never_change_fonts(profile_configs, config) -> None:
    for variant in profile_configs.values():
        assert variant.biblical_font == config.biblical_font
        assert variant.rashi_font == config.rashi_font
        assert variant.typography.rashi_script == config.typography.rashi_script
        assert (
            variant.typography.dibur_hamatchil_in_biblical_font
            == config.typography.dibur_hamatchil_in_biblical_font
        )


def test_biblical_line_height_clears_the_stacked_marks(profile_configs) -> None:
    """Density never at the cost of ניקוד and טעמים colliding between lines."""
    for name, variant in profile_configs.items():
        assert variant.typography.biblical_line_height >= BIBLICAL_INK_EM + 0.3, name


def test_every_profile_has_its_own_identifier(profile_configs) -> None:
    """Or the Kindle treats the sideloads as one book, each replacing the last."""
    hashes = {variant.config_hash for variant in profile_configs.values()}
    assert len(hashes) == len(PROFILES)


# ---- CSS, per profile ----------------------------------------------------


@pytest.mark.parametrize("name", PROFILES)
def test_font_sizes_and_line_heights(name, profile_configs) -> None:
    rules = _rules(render_css(profile_configs[name]))
    biblical, rashi, verse_number, divider = EXPECTED[name]["scales"]
    biblical_lh, rashi_lh = EXPECTED[name]["line_heights"]
    assert rules[".biblical-text"]["font-size"] == f"{biblical:g}em"
    assert rules[".biblical-text"]["line-height"] == f"{biblical_lh:g}"
    assert rules[".commentary-text"]["font-size"] == f"{rashi:g}em"
    assert rules[".commentary-text"]["line-height"] == f"{rashi_lh:g}"
    assert rules[".verse-number"]["font-size"] == f"{verse_number:g}em"
    assert rules[".commentary-divider"]["font-size"] == f"{divider:g}em"


@pytest.mark.parametrize("name", PROFILES)
def test_spacing(name, profile_configs) -> None:
    rules = _rules(render_css(profile_configs[name]))
    unit, verse, entry, paragraph = EXPECTED[name]["spacing"]
    assert rules[".study-unit"]["margin"] == f"0 0 {unit:g}em 0"
    assert rules[".verse"]["margin"] == f"0 0 {verse:g}em 0"
    assert rules[".commentary-entry"]["margin"] == f"0 0 {entry:g}em 0"
    assert rules[".commentary-text"]["margin"] == f"0 0 {paragraph:g}em 0"


@pytest.mark.parametrize("name", PROFILES)
def test_divider_is_one_rule_above_the_label(name, profile_configs) -> None:
    """SPEC §24: one top rule, never a second one below. No colour, no background."""
    css = render_css(profile_configs[name])
    divider = _rules(css)[".commentary-divider"]
    align, margin, padding = EXPECTED[name]["divider"]
    assert divider["border-top"] == "thin solid"
    assert "border-bottom" not in divider
    assert "border" not in divider, "the shorthand would draw four rules"
    assert divider["text-align"] == align
    assert divider["margin"] == margin
    assert divider["padding"] == padding
    assert css.count("border-") == 1, "the divider's rule is the only border in the book"
    for forbidden in ("color", "background", "url(", "content:"):
        assert forbidden not in "".join(f"{k}:{v}" for k, v in divider.items()), forbidden


@pytest.mark.parametrize("name", PROFILES)
def test_no_forbidden_css(name, profile_configs) -> None:
    """SPEC §26, for every variant: no layout tricks, no absolute or viewport units, no
    `direction` — RTL comes from the markup."""
    css = render_css(profile_configs[name])
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for forbidden in (
        "display",
        "position",
        "float",
        "grid",
        "flex",
        "column",
        "calc(",
        "@page",
        "@media",
        "direction",
        "unicode-bidi",
        "orphans",
        "widows",
        "javascript",
        "expression(",
    ):
        assert forbidden not in body, forbidden
    assert not re.search(r"\d\s*(px|pt|vh|vw|vmin|vmax|cm|mm|in)\b", body)


@pytest.mark.parametrize("name", PROFILES)
def test_verse_number_stays_inline(name, profile_configs) -> None:
    """Nothing in any profile may lift the verse number onto a line of its own."""
    rules = _rules(render_css(profile_configs[name]))
    for selector in (".verse-number", ".biblical-text", ".verse"):
        assert not {"display", "float", "width", "position"} & rules[selector].keys()


@pytest.mark.parametrize("name", PROFILES)
def test_every_break_hint_is_emitted_in_both_spellings(name, profile_configs) -> None:
    rules = _rules(render_css(profile_configs[name]))
    legacy = {"avoid": "avoid", "page": "always"}
    seen = 0
    for selector, declarations in rules.items():
        for prop, value in declarations.items():
            if prop.startswith("break-"):
                seen += 1
                twin = "page-" + prop
                assert declarations.get(twin) == legacy[value], f"{selector} {prop}"
            if prop.startswith("page-break-"):
                assert prop.removeprefix("page-") in declarations, f"{selector} {prop}"
    assert seen >= 3


@pytest.mark.parametrize("name", PROFILES)
def test_the_required_break_hints_are_in_every_profile(name, profile_configs) -> None:
    rules = _rules(render_css(profile_configs[name]))
    assert rules[".keep-together"]["break-inside"] == "avoid"
    assert rules[".chapter-heading"]["break-after"] == "avoid"
    assert rules[".book-start"]["break-before"] == "page"
    assert "break-inside" not in rules[".study-unit"], "the whole unit must stay splittable"
    assert "break-inside" not in rules[".commentary"], "the run of entries must stay splittable"


@pytest.mark.parametrize("name", PROFILES)
def test_no_profile_uses_the_optional_break_hints(name, profile_configs) -> None:
    """D-dense-break-aware, the one profile that used them, was rejected by the human."""
    rules = _rules(render_css(profile_configs[name]))
    assert "break-inside" not in rules[".commentary-entry"]
    assert not {"break-before", "break-after"} & rules[".commentary-divider"].keys()
    assert "break-after" not in rules[".book-heading"]


def test_optional_break_hints_are_emitted_when_a_profile_asks(tmp_path: Path) -> None:
    breaks = {
        "keep_each_entry_together": True,
        "keep_divider_with_neighbours": True,
        "keep_book_heading_with_next": True,
    }
    path = _config_with_profiles(
        tmp_path, {"x": {"label": "X", "hebrew_label": "א", "breaks": breaks}}, profile="x"
    )
    rules = _rules(render_css(load_config(path)))
    assert rules[".commentary-entry"]["break-inside"] == "avoid"
    assert rules[".commentary-entry"]["page-break-inside"] == "avoid"
    assert rules[".commentary-divider"]["break-before"] == "avoid"
    assert rules[".commentary-divider"]["page-break-after"] == "avoid"
    assert rules[".book-heading"]["break-after"] == "avoid"
    assert "break-inside" not in rules[".study-unit"]


@pytest.mark.parametrize("name", PROFILES)
def test_no_page_is_ever_forced_except_before_a_book(name, profile_configs) -> None:
    """SPEC §27: no forced page per verse, entry or chapter."""
    rules = _rules(render_css(profile_configs[name]))
    forced = [
        selector
        for selector, declarations in rules.items()
        for prop, value in declarations.items()
        if value in ("page", "always", "left", "right", "recto", "verso") and "break" in prop
    ]
    assert forced == [".book-start", ".book-start"]  # break-before + page-break-before


# ---- Same content, only layout differs ------------------------------------


def _semantic(xhtml: str) -> dict:
    tree = ElementTree.fromstring(xhtml)
    verses = [e for e in tree.iter(f"{XHTML}div") if e.get("class") == "verse"]
    entries = [
        e for e in tree.iter(f"{XHTML}div") if "commentary-entry" in e.get("class", "").split()
    ]
    return {
        "verse_ids": [v.get("id") for v in verses],
        "entry_ids": [e.get("id") for e in entries],
        "verse_text": ["".join(v.itertext()) for v in verses],
        "entry_text": ["".join(e.itertext()) for e in entries],
        "text": "".join(tree.find(f"{XHTML}body").itertext()),
    }


def test_every_profile_renders_the_same_semantic_content(
    profile_configs, books, genesis_chapter_1
) -> None:
    chapters, _, _ = genesis_chapter_1
    rendered = {
        name: ChapterRenderer(variant, books).render_all(chapters)[0]
        for name, variant in profile_configs.items()
    }
    reference = _semantic(rendered["current"].xhtml)
    assert len(reference["verse_ids"]) == 10 and len(reference["entry_ids"]) == 17
    for name, chapter in rendered.items():
        assert _semantic(chapter.xhtml) == reference, name
        # Stronger still: the markup does not depend on the profile at all.
        assert chapter.xhtml == rendered["current"].xhtml, name


@pytest.fixture(scope="module")
def variants(tmp_path_factory, books, genesis_chapter_1):
    chapters, text_versions, commentary_versions = genesis_chapter_1
    return build_variants(
        config_path=None,
        profile_names=PROFILES,
        books=books,
        chapters=chapters,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        output_dir=tmp_path_factory.mktemp("experiment"),
        build_date=datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC),
    )


def test_variant_file_names(variants) -> None:
    assert [v.result.path.name for v in variants] == [
        "layout_A_current.epub",
        "layout_B_balanced.epub",
        "layout_C_dense.epub",
    ]
    assert output_name(variants[0].profile) == "layout_A_current.epub"


def test_only_stylesheet_title_and_identifier_differ(variants) -> None:
    """Every chapter, the nav, the sources page and both fonts are byte-identical."""
    assert content_differences(variants) == []
    contents = []
    for variant in variants:
        with zipfile.ZipFile(variant.result.path) as archive:
            contents.append({name: archive.read(name) for name in archive.namelist()})
    differing = {
        name for other in contents[1:] for name in other if other[name] != contents[0][name]
    }
    assert differing == PER_VARIANT_FILES


def test_variants_differ_in_title_and_identifier_only_in_metadata(variants) -> None:
    ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
    seen = []
    for variant in variants:
        with zipfile.ZipFile(variant.result.path) as archive:
            opf = ElementTree.fromstring(archive.read("OEBPS/content.opf"))
        title = opf.find("opf:metadata/dc:title", ns).text
        identifier = opf.find("opf:metadata/dc:identifier", ns).text
        profile = opf.find("opf:metadata/opf:meta[@property='tanakh:layout-profile']", ns).text
        assert title == f"תנ״ך עם פירוש רש״י — {variant.profile.hebrew_label}"
        assert profile == variant.profile.label
        seen.append((title, identifier))
    assert len({t for t, _ in seen}) == len(PROFILES)
    assert len({i for _, i in seen}) == len(PROFILES)


def test_content_differences_catches_a_changed_chapter(variants, tmp_path: Path) -> None:
    """The guard itself must be able to fail."""
    import dataclasses

    tampered = tmp_path / "tampered.epub"
    with (
        zipfile.ZipFile(variants[1].result.path) as source,
        zipfile.ZipFile(tampered, "w") as target,
    ):
        for item in source.infolist():
            data = source.read(item)
            if item.filename.endswith("genesis-001.xhtml"):
                data = data.replace("בְּ".encode(), "ב".encode(), 1)
            target.writestr(item, data)
    fake = dataclasses.replace(
        variants[1], result=dataclasses.replace(variants[1].result, path=tampered)
    )
    assert content_differences([variants[0], fake]) == [
        "B-balanced: OEBPS/text/genesis-001.xhtml differs"
    ]


def test_report_lists_every_parameter_and_size(variants, genesis_chapter_1) -> None:
    chapters, _, _ = genesis_chapter_1
    report = format_report(variants, chapters)
    for name in PROFILES:
        assert EXPECTED[name]["label"] in report
    for heading in (
        "Biblical text",
        "Rashi",
        "Verse number",
        "Divider",
        "Study-unit gap",
        "Entry gap",
        "Page-break hints",
        "EPUB",
        "XHTML",
        "CSS",
    ):
        assert heading in report, heading
    assert "1.25em, line-height 1.9" in report
    assert "1.1em, line-height 1.6" in report
    for word in ("best", "winner", "recommended"):
        assert word not in report.lower(), "the software never picks a layout"


# ---- Config validation ----------------------------------------------------


def _config_with_profiles(tmp_path: Path, profiles: dict, **layout) -> Path:
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["layout_profiles"] = profiles
    raw["layout"].update(layout)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def test_unknown_profile_fails_loudly() -> None:
    with pytest.raises(ValueError, match='no layout profile "roomy"'):
        load_config(profile="roomy")


def test_a_profile_cannot_change_a_font(tmp_path: Path) -> None:
    path = _config_with_profiles(
        tmp_path,
        {"x": {"label": "X", "hebrew_label": "א", "typography": {"rashi_script": False}}},
        profile="x",
    )
    with pytest.raises(ValueError, match="never fonts or content"):
        load_config(path)


def test_a_profile_with_a_typo_fails_loudly(tmp_path: Path) -> None:
    path = _config_with_profiles(
        tmp_path,
        {"x": {"label": "X", "hebrew_label": "א", "spacing": {"study_units": 0.5}}},
        profile="x",
    )
    with pytest.raises(ValueError, match="study_units"):
        load_config(path)


def test_extends_cycle_fails_loudly(tmp_path: Path) -> None:
    path = _config_with_profiles(
        tmp_path,
        {
            "x": {"label": "X", "hebrew_label": "א", "extends": "y"},
            "y": {"label": "Y", "hebrew_label": "ב", "extends": "x"},
        },
        profile="x",
    )
    with pytest.raises(ValueError, match="cycle"):
        load_config(path)


def test_divider_alignment_is_validated(tmp_path: Path) -> None:
    path = _config_with_profiles(
        tmp_path,
        {"x": {"label": "X", "hebrew_label": "א", "spacing": {"divider_align": "justify"}}},
        profile="x",
    )
    with pytest.raises(ValueError, match="divider_align"):
        load_config(path)


def test_a_config_without_profiles_renders_its_base_sections(tmp_path: Path) -> None:
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    del raw["layout_profiles"], raw["layout"]["profile"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    config = load_config(path)
    assert config.layout_profile.name == "base"
    assert config.typography.biblical_line_height == 1.9


# ---- CLI --------------------------------------------------------------------


def test_experiment_layout_command_writes_every_epub_and_a_report(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "experiment-layout",
            "--chapter",
            "Genesis",
            "1",
            "--max-verse",
            "10",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    names = sorted(p.name for p in tmp_path.glob("*.epub"))
    assert names == [
        "layout_A_current.epub",
        "layout_B_balanced.epub",
        "layout_C_dense.epub",
    ]
    out = capsys.readouterr().out
    assert "byte-identical" in out
    assert (tmp_path / "layout_experiment.txt").read_text(encoding="utf-8") in out


def test_experiment_layout_can_build_a_subset(tmp_path: Path) -> None:
    code = main(
        [
            "experiment-layout",
            "--chapter",
            "Genesis",
            "1",
            "--profiles",
            "balanced",
            "dense",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    assert sorted(p.name for p in tmp_path.glob("*.epub")) == [
        "layout_B_balanced.epub",
        "layout_C_dense.epub",
    ]


def test_build_accepts_a_layout_profile(tmp_path: Path, capsys) -> None:
    output = tmp_path / "dense.epub"
    assert (
        main(
            [
                "build",
                "--chapter",
                "Genesis",
                "1",
                "--layout-profile",
                "dense",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "C-dense" in capsys.readouterr().out
    with zipfile.ZipFile(output) as archive:
        css = archive.read("OEBPS/styles/main.css").decode("utf-8")
    assert "font-size: 1.1em" in css

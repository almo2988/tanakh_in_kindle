"""Build manifest and license report — SPEC_DATA_SOURCE.md §14, §15.

One record of what went into a build, from the same data that feeds the מקורות page:

- ``build_manifest.json`` — embedded in the EPUB as ``OEBPS/build_manifest.json`` and
  written next to the output, so a build can be reproduced from the cache: same config
  hash, same versions, same books.
- ``SOURCES_AND_LICENSES.md`` — the same facts for a person, in English, outside the book.
"""

from __future__ import annotations

import json
from datetime import datetime

from .. import __version__
from ..books import BookTable
from ..config import Config


def build_manifest(
    config: Config,
    books: BookTable,
    *,
    book_titles: list[str],
    text_versions: dict[str, str],
    commentary_versions: dict[str, dict[str, str]],
    identifier: str,
    build_date: datetime,
) -> dict:
    ordered = [b.sefaria_title for b in books if b.sefaria_title in set(book_titles)]
    return {
        "build_date": build_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator_version": __version__,
        "identifier": identifier,
        "config_hash": config.config_hash,
        "layout_profile": config.layout_profile.label,
        "content_provider": config.tanakh_source.provider,
        "tanakh_version": config.tanakh_source.version_title,
        "tanakh_versions_by_book": {b: text_versions[b] for b in ordered if b in text_versions},
        "commentary_versions": {
            name: {b: by_book[b] for b in ordered if b in by_book}
            for name, by_book in commentary_versions.items()
        },
        "fonts": {"biblical": config.biblical_font.name, "rashi": config.rashi_font.name},
        "books": ordered,
        "delivery_target": config.delivery,
    }


def manifest_json(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def sources_and_licenses(config: Config, books: BookTable, manifest: dict) -> str:
    lines = [
        "# Sources and licenses",
        "",
        f"Build {manifest['build_date']} · identifier `{manifest['identifier']}` · "
        f"{len(manifest['books'])} book(s).",
        "",
        "All text comes from [Sefaria](https://www.sefaria.org), unchanged except for Unicode "
        "NFC normalization and the markup conversion in `docs/MARKUP_RULES.md`.",
        "",
        "## Tanakh",
        "",
        "| Version | License | Source | Books |",
        "|---|---|---|---|",
    ]
    source = config.tanakh_source
    lines.append(
        f"| {source.version_title} | {source.license} | {source.source_url or ''} | "
        f"{len(manifest['books'])} |"
    )
    for name, by_book in manifest["commentary_versions"].items():
        lines += [
            "",
            f"## {name}",
            "",
            "| Version | License | Source | Books |",
            "|---|---|---|---|",
        ]
        groups: dict[str, list[str]] = {}
        for book, version in by_book.items():
            groups.setdefault(version, []).append(book)
        for version, titles in groups.items():
            info = config.commentary_source(name, titles[0])
            lines.append(
                f"| {version.strip()} | {info.license} | {info.source_url or ''} | "
                f"{', '.join(titles)} |"
            )
        missing = [b for b in manifest["books"] if b not in by_book]
        if missing:
            lines += ["", f"Books without {name}: {', '.join(missing)}."]
    lines += ["", "## Fonts", "", "| Font | License |", "|---|---|"]
    for font in (config.biblical_font, config.rashi_font):
        lines.append(f"| {font.name} | {font.license} |")
    unknown = [
        v
        for name, by_book in manifest["commentary_versions"].items()
        for v in dict.fromkeys(by_book.values())
        if config.commentary_source(name, next(b for b in by_book if by_book[b] == v)).license
        == "unknown"
    ]
    if unknown:
        lines += [
            "",
            "**Note:** Sefaria lists the license of "
            + ", ".join(f"*{v.strip()}*" for v in unknown)
            + " as unknown. This build is for personal reading; do not redistribute it "
            "without clearing that license with Sefaria.",
        ]
    return "\n".join(lines) + "\n"

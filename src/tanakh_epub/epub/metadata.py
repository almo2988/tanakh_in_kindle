"""Package metadata — SPEC.md §28.

The identifier is derived, not random: the same output name, layout profile and books
produce the same ``dc:identifier`` on every rebuild — even after a font size or a markup
rule changes — so a re-sent book replaces the previous copy on the device instead of
appearing beside it. ``build --new-identifier`` stores a fresh salt for that output name in
``data/processed/identity.json``; every later build of it uses the new identifier.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..config import Config
from ..paths import PROCESSED_DIR

IDENTITY_FILE = PROCESSED_DIR / "identity.json"

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/almo2988/tanakh_in_kindle")


@dataclass(frozen=True)
class PackageMetadata:
    identifier: str
    title: str
    creator: str
    publisher: str
    modified: str
    rights_statements: tuple[str, ...]
    custom_meta: tuple[dict[str, str], ...]


def derive_identifier(config: Config, books: list[str], salt: str = "") -> str:
    """Stable per output name, layout profile, book list and salt — not per config hash."""
    seed = "|".join([config.output_filename, config.layout_profile.name, salt, *sorted(books)])
    return f"urn:uuid:{uuid.uuid5(NAMESPACE, seed)}"


def identifier_salt(output_name: str, path: Path | None = None) -> str:
    path = path or IDENTITY_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(output_name, "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def new_identifier_salt(output_name: str, path: Path | None = None) -> str:
    path = path or IDENTITY_FILE
    try:
        salts = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        salts = {}
    salts[output_name] = uuid.uuid4().hex
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(salts, indent=2) + "\n", encoding="utf-8")
    return salts[output_name]


def build_metadata(
    config: Config,
    *,
    books: list[str],
    text_versions: dict[str, str],
    commentary_versions: dict[str, dict[str, str]],
    modified: datetime | None = None,
    generator_version: str = "0.1.0",
    identifier_salt: str = "",
) -> PackageMetadata:
    modified = (modified or datetime.now(UTC)).astimezone(UTC)

    # Recording the exact version titles in the book itself is what makes a build
    # reproducible and what several Sefaria licenses require (SPEC_DATA_SOURCE §14).
    custom: list[dict[str, str]] = [
        {"property": "tanakh:content-provider", "value": config.tanakh_source.provider},
        {"property": "tanakh:generator-version", "value": generator_version},
        {"property": "tanakh:config-hash", "value": config.config_hash},
        {"property": "tanakh:delivery-target", "value": config.delivery},
        {"property": "tanakh:layout-profile", "value": config.layout_profile.label},
    ]
    for book in sorted(text_versions):
        custom.append(
            {"property": "tanakh:text-version", "value": f"{book}: {text_versions[book]}"}
        )
    for name in sorted(commentary_versions):
        for version in dict.fromkeys(commentary_versions[name].values()):
            custom.append({"property": "tanakh:commentary-version", "value": f"{name}: {version}"})

    rights = [
        f"{config.tanakh_source.version_title} — {config.tanakh_source.license} "
        f"(via {config.tanakh_source.provider})"
    ]
    for name in config.commentaries:
        used = commentary_versions.get(name) or {}
        sources = (
            {
                config.commentary_source(name, book).version_title: config.commentary_source(
                    name, book
                )
                for book in used
            }
            if used
            else {config.commentary_sources[name].version_title: config.commentary_sources[name]}
        )
        for source in sources.values():
            rights.append(f"{source.version_title} — {source.license} (via {source.provider})")

    return PackageMetadata(
        identifier=derive_identifier(config, books, identifier_salt),
        title=config.title,
        creator=config.creator,
        publisher=config.publisher,
        modified=modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
        rights_statements=tuple(rights),
        custom_meta=tuple(custom),
    )

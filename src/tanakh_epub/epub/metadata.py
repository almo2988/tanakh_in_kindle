"""Package metadata — SPEC.md §28.

The identifier is derived, not random: the same config and the same books produce the same
``dc:identifier`` on every rebuild, so a re-sideloaded book replaces the previous copy on
the device instead of appearing beside it. Phase 3 adds the ``--new-identifier`` escape
hatch (PROGRESS.md task 3.8).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from ..config import Config

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


def derive_identifier(config: Config, books: list[str]) -> str:
    seed = "|".join([config.config_hash, config.output_filename, *sorted(books)])
    return f"urn:uuid:{uuid.uuid5(NAMESPACE, seed)}"


def build_metadata(
    config: Config,
    *,
    books: list[str],
    text_versions: dict[str, str],
    commentary_versions: dict[str, str],
    modified: datetime | None = None,
    generator_version: str = "0.1.0",
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
        custom.append(
            {
                "property": "tanakh:commentary-version",
                "value": f"{name}: {commentary_versions[name]}",
            }
        )

    rights = [
        f"{config.tanakh_source.version_title} — {config.tanakh_source.license} "
        f"(via {config.tanakh_source.provider})"
    ]
    for name in config.commentaries:
        source = config.commentary_sources[name]
        rights.append(f"{source.version_title} — {source.license} (via {source.provider})")

    return PackageMetadata(
        identifier=derive_identifier(config, books),
        title=config.title,
        creator=config.creator,
        publisher=config.publisher,
        modified=modified.strftime("%Y-%m-%dT%H:%M:%SZ"),
        rights_statements=tuple(rights),
        custom_meta=tuple(custom),
    )

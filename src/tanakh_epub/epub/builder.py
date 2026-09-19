"""The EPUB writer — SPEC.md §4, §11, §17, §28, §32.

Decision D8: hand-rolled (``zipfile`` + Jinja2), not ``ebooklib``. The spec allows
``ebooklib`` only if its output passes EPUBCheck *and* Kindle Previewer unmodified; every
file this project cares about — the OPF spine with ``page-progression-direction``, the NCX
kept alongside the nav document, the exact manifest and media types — is one Kindle
conversion quirk away from needing a hand edit. ``zipfile`` gives that control for about
a hundred lines, so nothing is gained by taking the dependency.

Zip layout is not free-form: ``mimetype`` must be the first entry and stored uncompressed,
or readers reject the file before anything else is looked at.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..books import BookTable
from ..config import Config
from ..models import Chapter
from ..rendering.css import CommentaryParts, epub_font_href, font_media_type, render_css
from ..rendering.html_renderer import ChapterRenderer, RenderedChapter, build_environment
from .metadata import build_metadata
from .navigation import build_navigation, render_nav, render_ncx

MIMETYPE = "application/epub+zip"
META_PREFIX = "tanakh: https://github.com/almo2988/tanakh_in_kindle/ns#"
"""Namespace for the custom `meta` properties in the OPF. EPUB 3 requires any prefix
outside the reserved vocabularies to be declared on the package element."""
OEBPS = "OEBPS"
SOURCES_FILENAME = "sources.xhtml"

ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
"""A fixed timestamp, so two builds of the same content produce identical bytes."""


@dataclass
class ManifestItem:
    id: str
    href: str
    media_type: str
    properties: str = ""


@dataclass
class BuildResult:
    path: Path
    chapters: list[RenderedChapter]
    identifier: str
    oversized: list[RenderedChapter] = field(default_factory=list)
    """Chapter files over ``layout.max_file_kb`` — Amazon's ~300 KB guideline (SPEC §11)."""
    rashi_font_protected: bool = True
    """False if Kindle's converter may still make the Rashi font the book's default font
    (see `CommentaryParts`); only a build of a few verses can hit it."""

    @property
    def total_bytes(self) -> int:
        return self.path.stat().st_size


class EpubBuilder:
    def __init__(self, config: Config, books: BookTable) -> None:
        self.config = config
        self.books = books
        self.env = build_environment()
        self.renderer = ChapterRenderer(config, books, self.env)

    def build(
        self,
        chapters: list[Chapter],
        *,
        output: Path,
        text_versions: dict[str, str],
        commentary_versions: dict[str, str],
        build_date: datetime | None = None,
    ) -> BuildResult:
        if not chapters:
            raise ValueError("Nothing to build: no chapters were selected")

        build_date = build_date or datetime.now(UTC)
        parts = CommentaryParts.plan(chapters, self.config)
        rendered = self.renderer.render_all(chapters, parts)
        sources_xhtml = self.renderer.render_sources(build_date=build_date)
        css = render_css(self.config, commentary_parts=parts.count)

        navigation = build_navigation(
            self.config, self.books, rendered, sources_filename=SOURCES_FILENAME
        )
        metadata = build_metadata(
            self.config,
            books=sorted({c.book for c in chapters}),
            text_versions=text_versions,
            commentary_versions=commentary_versions,
            modified=build_date,
        )

        nav_xhtml = render_nav(self.env, navigation)
        ncx = render_ncx(
            self.env, navigation, identifier=metadata.identifier, title=self.config.title
        )

        manifest, spine = self._manifest_and_spine(rendered)
        opf = self.env.get_template("content.opf.j2").render(
            meta_prefix=META_PREFIX,
            identifier=metadata.identifier,
            title=metadata.title,
            creator=metadata.creator,
            publisher=metadata.publisher,
            modified=metadata.modified,
            rights_statements=list(metadata.rights_statements),
            custom_meta=list(metadata.custom_meta),
            cover_id=None,
            manifest=[vars(item) for item in manifest],
            spine=spine,
        )
        container = self.env.get_template("container.xml.j2").render()

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w") as archive:
            self._write_mimetype(archive)
            self._write(archive, "META-INF/container.xml", container)
            self._write(archive, f"{OEBPS}/content.opf", opf)
            self._write(archive, f"{OEBPS}/nav.xhtml", nav_xhtml)
            self._write(archive, f"{OEBPS}/toc.ncx", ncx)
            self._write(archive, f"{OEBPS}/styles/main.css", css)
            for chapter in rendered:
                self._write(archive, f"{OEBPS}/text/{chapter.filename}", chapter.xhtml)
            self._write(archive, f"{OEBPS}/text/{SOURCES_FILENAME}", sources_xhtml)
            for role, font in (
                ("biblical", self.config.biblical_font),
                ("rashi", self.config.rashi_font),
            ):
                self._write_bytes(
                    archive,
                    f"{OEBPS}/{epub_font_href(self.config, role)}",
                    font.file.read_bytes(),
                )

        limit = self.config.layout.max_file_kb * 1024
        return BuildResult(
            path=output,
            chapters=rendered,
            identifier=metadata.identifier,
            oversized=[c for c in rendered if c.size_bytes > limit],
            rashi_font_protected=parts.protects_rashi_font,
        )

    # ---- manifest --------------------------------------------------------

    def _manifest_and_spine(
        self, rendered: list[RenderedChapter]
    ) -> tuple[list[ManifestItem], list[str]]:
        manifest = [
            ManifestItem("nav", "nav.xhtml", "application/xhtml+xml", "nav"),
            ManifestItem("ncx", "toc.ncx", "application/x-dtbncx+xml"),
            ManifestItem("css", "styles/main.css", "text/css"),
        ]
        spine: list[str] = []

        for chapter in rendered:
            item_id = f"{chapter.book.slug}-{chapter.chapter:03d}"
            manifest.append(
                ManifestItem(item_id, f"text/{chapter.filename}", "application/xhtml+xml")
            )
            spine.append(item_id)

        manifest.append(
            ManifestItem("sources", f"text/{SOURCES_FILENAME}", "application/xhtml+xml")
        )
        spine.append("sources")

        for role, font in (
            ("biblical", self.config.biblical_font),
            ("rashi", self.config.rashi_font),
        ):
            href = epub_font_href(self.config, role)
            manifest.append(ManifestItem(f"font-{role}", href, font_media_type(font.suffix)))

        return manifest, spine

    # ---- zip mechanics ---------------------------------------------------

    @staticmethod
    def _write_mimetype(archive: zipfile.ZipFile) -> None:
        info = zipfile.ZipInfo("mimetype", date_time=ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, MIMETYPE)

    @staticmethod
    def _write(archive: zipfile.ZipFile, name: str, text: str) -> None:
        EpubBuilder._write_bytes(archive, name, text.encode("utf-8"))

    @staticmethod
    def _write_bytes(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
        info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, payload)

"""Command line interface — SPEC.md §31.

``fetch`` is the only command that touches the network: it fills ``data/cache/`` from
Sefaria. Everything else — ``inventory-markup``, ``validate``, ``build``,
``experiment-layout`` — reads the cache (falling back to the checked-in fixtures for a book
that has not been fetched), so a build works offline once the books are cached.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .books import BookTable, load_books
from .config import Config, load_config
from .epub.builder import EpubBuilder
from .epub.manifest import manifest_json, sources_and_licenses
from .epub.metadata import identifier_salt, new_identifier_salt
from .layout_experiment import build_variants, content_differences, format_report
from .paths import CACHE_DIR, PROJECT_ROOT
from .processing.inventory import Inventory, format_inventory, scan
from .processing.study_units import ChapterSelection, ContentError, load_chapters, stats
from .processing.validation import format_report as format_validation
from .processing.validation import validate
from .providers.base import ProviderError
from .providers.fetch import fetch_book
from .providers.local import LocalProvider
from .providers.sefaria import SefariaClient, SefariaProvider
from .rendering.html_renderer import ChapterRenderer
from .validation_tools import ToolResult, run_epubcheck, run_kindle_previewer


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tanakh_epub",
        description="Build a Hebrew Tanakh + Rashi EPUB for the Kindle Paperwhite.",
    )
    parser.add_argument("--version", action="version", version=f"tanakh-epub {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build an EPUB from local data")
    _add_selection_arguments(build)
    build.add_argument(
        "--layout-profile",
        metavar="NAME",
        default=None,
        help="a key under layout_profiles in the config (default: layout.profile)",
    )
    build.add_argument("--no-commentary", action="store_true", help="verses only")
    build.add_argument("--output", type=Path, default=None, help="output .epub path")
    build.add_argument(
        "--new-identifier",
        action="store_true",
        help="give this output a new dc:identifier from now on, so the Kindle treats it as a "
        "new book rather than an update of the old one",
    )
    _add_kpf_argument(build)

    experiment = subparsers.add_parser(
        "experiment-layout",
        help="build the same content once per layout profile, for the device test",
        description="Build one EPUB per layout profile from identical content — "
        "output/layout_<label>.epub — and print the parameters and sizes of each. "
        "With no selection, builds the whole Tanakh (run `fetch` first).",
    )
    _add_selection_arguments(experiment)
    experiment.add_argument(
        "--profiles",
        nargs="+",
        metavar="NAME",
        default=None,
        help="profiles to build, in this order (default: every profile in the config)",
    )
    experiment.add_argument(
        "--output-dir", type=Path, default=None, help="where the EPUBs go (default: output/)"
    )
    _add_kpf_argument(experiment)

    check = subparsers.add_parser(
        "check", help="run EPUBCheck (and Kindle Previewer, if installed) over an EPUB"
    )
    check.add_argument("epub", type=Path)
    check.add_argument(
        "--kindle-output", type=Path, default=None, help="where Kindle Previewer writes the KPF"
    )

    fetch = subparsers.add_parser(
        "fetch",
        help="fetch whole books from Sefaria into data/cache/",
        description="Fill data/cache/ with the configured Tanakh and commentary versions. "
        "A cached book in the configured version is skipped unless refreshed.",
    )
    fetch.add_argument("--config", type=Path, default=None)
    fetch.add_argument("--book", metavar="BOOK", help="one book, by its Sefaria title")
    fetch.add_argument("--books", nargs="+", metavar="BOOK", help="several books")
    fetch.add_argument("--refresh", action="store_true", help="re-fetch the selected books")
    fetch.add_argument("--refresh-all", action="store_true", help="re-fetch every book")
    fetch.add_argument(
        "--prefer",
        choices=("export", "api"),
        default="export",
        help="which Sefaria source to try first (default: the Sefaria-Export bucket)",
    )
    fetch.add_argument("--cache-dir", type=Path, default=None, help=argparse.SUPPRESS)

    for name, summary in (
        ("inventory-markup", "count every tag, class and entity in the cached data"),
        ("validate", "check the cached data is complete and convertible"),
    ):
        sub = subparsers.add_parser(name, help=summary, description=summary)
        sub.add_argument("--config", type=Path, default=None)
        sub.add_argument("--book", metavar="BOOK")
        sub.add_argument("--books", nargs="+", metavar="BOOK")
        sub.add_argument("--output", type=Path, default=None, help="also write the report here")
        sub.add_argument("--cache-dir", type=Path, default=None, help=argparse.SUPPRESS)

    return parser


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=Path, default=None, help="config file (default: config/default.yaml)"
    )
    parser.add_argument("--book", metavar="BOOK", help="build one book, by its Sefaria title")
    parser.add_argument("--books", nargs="+", metavar="BOOK", help="build several books")
    parser.add_argument(
        "--chapter",
        nargs=2,
        metavar=("BOOK", "N"),
        help="build a single chapter, e.g. --chapter Genesis 1",
    )
    parser.add_argument(
        "--max-verse",
        type=int,
        default=None,
        metavar="N",
        help="stop after verse N — for the POC build (בראשית א׳:א׳–י׳)",
    )


def _add_kpf_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--kpf",
        action="store_true",
        help="also convert each EPUB to KPF with Kindle Previewer (next to the EPUB)",
    )


def _selections(args, config: Config, books: BookTable) -> tuple[list[ChapterSelection], str]:
    """Resolve the requested subset, and a default output name describing it."""
    if args.chapter:
        title, number = args.chapter
        book = books.by_title(title)
        chapter = int(number)
        return (
            [ChapterSelection(book, (chapter,), max_verse=args.max_verse)],
            f"{book.sefaria_title.replace(' ', '_')}_Chapter_{chapter}.epub",
        )

    titles = args.books or ([args.book] if args.book else None)
    if titles:
        selected = [books.by_title(title) for title in titles]
        selections = [ChapterSelection(book, None, max_verse=args.max_verse) for book in selected]
        if len(selected) == 1:
            return selections, f"{selected[0].sefaria_title.replace(' ', '_')}.epub"
        return selections, config.output_filename

    return (
        [ChapterSelection(book, None, max_verse=args.max_verse) for book in books],
        config.output_filename,
    )


def _expected_versions(config: Config, books: BookTable) -> dict[str, str]:
    expected = {"tanakh": config.tanakh_source.version_title}
    for name in config.commentaries:
        for book in books:
            title = book.sefaria_title
            expected[f"{name}:{title}"] = config.commentary_source(name, title).version_title
    return expected


def _titles(args, books: BookTable) -> list[str]:
    titles = args.books or ([args.book] if args.book else None)
    if titles:
        return [books.by_title(t).sefaria_title for t in titles]
    return [book.sefaria_title for book in books]


def _load_content(args, config: Config, books: BookTable):
    """The requested chapters as the internal model, or ``None`` — with the reason on
    stderr — if any of them is not available locally.

    Never a partial book: a whole-book build of a book that was not fetched fails, even
    when the test fixture could supply its first chapter (SPEC_DATA_SOURCE.md §17). A
    single-chapter build may use the fixture, which is what keeps the POC build offline.
    """
    provider = LocalProvider(books=books, expected_versions=_expected_versions(config, books))

    selections, default_name = _selections(args, config, books)
    available = set(provider.get_books())
    missing = [
        s.book.sefaria_title
        for s in selections
        if s.book.sefaria_title not in available
        or (s.chapters is None and provider.is_partial(s.book.sefaria_title))
    ]
    if missing:
        whole = len(missing) == len(books)
        named = "any book" if whole else ", ".join(missing)
        command = "python -m tanakh_epub fetch" + (
            ""
            if whole
            else "".join(f' --books "{t}"' if i == 0 else f' "{t}"' for i, t in enumerate(missing))
        )
        print(
            f"Not downloaded yet: {named}.\n"
            f"Run `{command}` first (once; it caches the text in data/cache/).",
            file=sys.stderr,
        )
        return None
    try:
        return (*load_chapters(provider, config, selections), default_name)
    except (ContentError, ProviderError) as exc:
        print(exc, file=sys.stderr)
        return None


def _shown(path: Path) -> Path:
    return path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path


def _convert_to_kpf(epub: Path) -> ToolResult:
    """Kindle Previewer's conversion, with the KPF copied next to the EPUB."""
    # Previewer fails if its output folder is the input's own folder, so use a subfolder.
    work_dir = epub.parent / "kindle-previewer" / epub.stem
    converted = run_kindle_previewer(epub, work_dir)
    print(f"\n{converted.message}")
    if not converted.passed:
        if converted.output:
            print("\n".join(f"  {line}" for line in converted.output.splitlines()))
        return converted
    kpf = max(work_dir.glob("**/*.kpf"), key=lambda p: p.stat().st_mtime)
    target = epub.with_suffix(".kpf")
    shutil.copyfile(kpf, target)
    print(f"Wrote {_shown(target)}")
    return converted


def cmd_build(args) -> int:
    config = load_config(args.config, profile=args.layout_profile)
    books = load_books()

    if args.no_commentary:
        config = Config(**{**vars(config), "commentaries": ()})

    content = _load_content(args, config, books)
    if content is None:
        return 1
    chapters, text_versions, commentary_versions, default_name = content
    output = args.output or (config.output_dir / default_name)
    salt = new_identifier_salt(output.name) if args.new_identifier else identifier_salt(output.name)

    result = EpubBuilder(config, books).build(
        chapters,
        output=output,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=datetime.now(UTC),
        identifier_salt=salt,
    )
    # SPEC_DATA_SOURCE §14–§15: the manifest and license report sit next to the book.
    stem = output.with_suffix("")
    manifest_path = stem.parent / f"{stem.name}.build_manifest.json"
    licenses_path = stem.parent / f"{stem.name}.SOURCES_AND_LICENSES.md"
    manifest_path.write_text(manifest_json(result.manifest), encoding="utf-8")
    licenses_path.write_text(sources_and_licenses(config, books, result.manifest), encoding="utf-8")

    counts = stats(chapters)
    print(f"Built {_shown(result.path)}")
    print(f"  identifier         {result.identifier}")
    print(f"  layout profile     {config.layout_profile.label}")
    print(f"  chapter files      {len(result.chapters)}")
    print(f"  verses             {counts.verses}")
    print(
        f"  commentary entries {counts.commentary_entries} "
        f"({counts.verses_with_commentary} verses with, "
        f"{counts.verses_without_commentary} without)"
    )
    print(f"  size               {result.total_bytes / 1024:.0f} KB")
    print(f"  manifest           {_shown(manifest_path)}")
    print(f"  licenses           {_shown(licenses_path)}")
    for version in dict.fromkeys(text_versions.values()):
        count = sum(1 for v in text_versions.values() if v == version)
        print(f"  text version       {version} ({count} book{'s' if count > 1 else ''})")
    for name, by_book in sorted(commentary_versions.items()):
        for version in dict.fromkeys(by_book.values()):
            print(f"  commentary version {name}: {version}")

    if not result.rashi_font_protected:
        print(
            "\nWarning: one Rashi paragraph is longer than all the verses in this build, so "
            "Kindle may show the commentary in the reader's font, not Rashi script. "
            "Build a whole chapter or more.",
            file=sys.stderr,
        )

    if result.oversized:
        limit = config.layout.max_file_kb
        print(f"\nChapter files over {limit} KB (SPEC §11):", file=sys.stderr)
        for chapter in result.oversized:
            print(f"  {chapter.filename}  {chapter.size_bytes / 1024:.0f} KB", file=sys.stderr)
        return 1

    if args.kpf and not _convert_to_kpf(result.path).passed:
        return 1

    return 0


def cmd_experiment_layout(args) -> int:
    base = load_config(args.config)
    if not base.layout_profiles:
        print(f"{base.path} defines no layout_profiles.", file=sys.stderr)
        return 1
    books = load_books()

    # Content is loaded once and shared, so no variant can differ in what it says.
    content = _load_content(args, base, books)
    if content is None:
        return 1
    chapters, text_versions, commentary_versions, _ = content

    output_dir = args.output_dir or base.output_dir
    variants = build_variants(
        config_path=args.config,
        profile_names=args.profiles or list(base.layout_profiles),
        books=books,
        chapters=chapters,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        output_dir=output_dir,
        build_date=datetime.now(UTC),
    )

    report = format_report(variants, chapters)
    print(report)
    report_path = output_dir / "layout_experiment.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"Report written to {_shown(report_path)}")

    problems = content_differences(variants)
    if problems:
        print("\nThe variants differ in more than layout:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(
        "Every chapter, the navigation, the sources page and both fonts are byte-identical "
        "across the variants; only the stylesheet, title and identifier differ."
    )

    failed = False
    for variant in variants:
        if variant.result.oversized:
            failed = True
            print(f"{variant.result.path.name}: chapter files over the size limit", file=sys.stderr)
        if args.kpf and not _convert_to_kpf(variant.result.path).passed:
            failed = True
    return 1 if failed else 0


def cmd_check(args) -> int:
    epub: Path = args.epub
    if not epub.is_file():
        print(f"No such file: {epub}", file=sys.stderr)
        return 1

    failed = False

    epubcheck = run_epubcheck(epub)
    print(f"== {epubcheck.tool}")
    if epubcheck.skipped:
        print(f"  SKIPPED: {epubcheck.message}")
    else:
        print(f"  {'PASS' if epubcheck.passed else 'FAIL'}: {epubcheck.message}")
        failed = failed or not epubcheck.passed
    if epubcheck.output:
        print("\n".join(f"  {line}" for line in epubcheck.output.splitlines()))

    previewer = run_kindle_previewer(epub, args.kindle_output or (epub.parent / "kindle-previewer"))
    print(f"\n== {previewer.tool}")
    if previewer.skipped:
        print(f"  SKIPPED: {previewer.message}")
    else:
        print(f"  {'PASS' if previewer.passed else 'FAIL'}: {previewer.message}")
        failed = failed or not previewer.passed
    if previewer.output:
        print("\n".join(f"  {line}" for line in previewer.output.splitlines()))

    return 1 if failed else 0


def cmd_fetch(args) -> int:
    config = load_config(args.config)
    books = load_books()
    cache_dir = args.cache_dir or CACHE_DIR
    titles = _titles(args, books)
    provider = SefariaProvider(SefariaClient(), prefer=args.prefer)

    failed = False
    for title in titles:
        book = books.by_title(title)
        for outcome in fetch_book(
            provider,
            config,
            book,
            cache_dir=cache_dir,
            refresh=args.refresh or args.refresh_all,
        ):
            where = f"  → {_shown(outcome.path)}" if outcome.path else ""
            detail = f"  {outcome.detail}" if outcome.detail else ""
            print(f"{outcome.status:8} {outcome.label}{where}{detail}")
            failed = failed or outcome.status == "failed"
    print(f"\n{len(provider.client.requests)} request(s) to Sefaria.")
    return 1 if failed else 0


def _cached_titles(args, config: Config, books: BookTable, cache_dir: Path):
    """The selected books that are in the cache — a validate or inventory over fixtures
    would describe the fixtures, not the data a build will use."""
    provider = LocalProvider(
        [cache_dir], books=books, expected_versions=_expected_versions(config, books)
    )
    wanted = _titles(args, books)
    have = set(provider.get_books())
    missing = [t for t in wanted if t not in have]
    explicit = bool(args.books or args.book)
    return provider, [t for t in wanted if t in have], (missing if explicit else [])


def _emit(report: str, output: Path | None) -> None:
    print(report, end="")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        print(f"Report written to {_shown(output)}")


def cmd_inventory(args) -> int:
    config = load_config(args.config)
    books = load_books()
    provider, titles, missing = _cached_titles(args, config, books, args.cache_dir or CACHE_DIR)
    if missing or not titles:
        print(
            f"Not cached: {', '.join(missing) or 'any book'}. Run `fetch` first.", file=sys.stderr
        )
        return 1
    inventory = Inventory()
    try:
        for title in titles:
            scan(inventory, title, provider.get_book_text(title))
            for name in config.commentaries:
                if provider.has_commentary(name, title):
                    label = config.commentator(name).index_title(title)
                    scan(inventory, label, provider.get_book_commentary(name, title))
    except ProviderError as exc:
        print(exc, file=sys.stderr)
        return 1
    _emit(format_inventory(inventory), args.output)
    return 1 if inventory.unknown else 0


def cmd_validate(args) -> int:
    config = load_config(args.config)
    books = load_books()
    provider, titles, missing = _cached_titles(args, config, books, args.cache_dir or CACHE_DIR)
    if missing or not titles:
        print(
            f"Not cached: {', '.join(missing) or 'any book'}. Run `fetch` first.", file=sys.stderr
        )
        return 1
    renderer = ChapterRenderer(config, books)

    def render(chapters):
        return [(c.filename, c.size_bytes) for c in renderer.render_all(chapters)]

    reports = validate(provider, config, books, titles, render=render)
    _emit(format_validation(reports, config, books), args.output)
    return 0 if all(r.ok for r in reports) else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "fetch":
        return cmd_fetch(args)
    if args.command == "inventory-markup":
        return cmd_inventory(args)
    if args.command == "validate":
        return cmd_validate(args)

    if args.command == "build":
        return cmd_build(args)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "experiment-layout":
        return cmd_experiment_layout(args)

    raise AssertionError(f"unhandled command {args.command!r}")

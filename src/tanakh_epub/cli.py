"""Command line interface — SPEC.md §31.

Phase 1 implements ``build`` and ``check``. ``fetch``, ``validate`` and
``inventory-markup`` belong to the Sefaria provider and land in Phase 2; they are listed
here so ``--help`` tells the truth about what does and does not exist yet, and so running
one gives a pointer rather than an ``unknown command``.
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
from .paths import PROJECT_ROOT
from .processing.study_units import ChapterSelection, load_chapters, stats
from .providers.local import LocalProvider
from .validation_tools import run_epubcheck, run_kindle_previewer

PHASE_2_COMMANDS = {
    "fetch": "2.3",
    "validate": "2.8",
    "inventory-markup": "2.5",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tanakh_epub",
        description="Build a Hebrew Tanakh + Rashi EPUB for the Kindle Paperwhite.",
    )
    parser.add_argument("--version", action="version", version=f"tanakh-epub {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build an EPUB from local data")
    build.add_argument(
        "--config", type=Path, default=None, help="config file (default: config/default.yaml)"
    )
    build.add_argument("--book", metavar="BOOK", help="build one book, by its Sefaria title")
    build.add_argument("--books", nargs="+", metavar="BOOK", help="build several books")
    build.add_argument(
        "--chapter",
        nargs=2,
        metavar=("BOOK", "N"),
        help="build a single chapter, e.g. --chapter Genesis 1",
    )
    build.add_argument(
        "--max-verse",
        type=int,
        default=None,
        metavar="N",
        help="stop after verse N — for the POC build (בראשית א׳:א׳–י׳)",
    )
    build.add_argument("--no-commentary", action="store_true", help="verses only")
    build.add_argument("--output", type=Path, default=None, help="output .epub path")
    build.add_argument(
        "--kpf",
        action="store_true",
        help="also convert the EPUB to KPF with Kindle Previewer (next to the EPUB)",
    )

    check = subparsers.add_parser(
        "check", help="run EPUBCheck (and Kindle Previewer, if installed) over an EPUB"
    )
    check.add_argument("epub", type=Path)
    check.add_argument(
        "--kindle-output", type=Path, default=None, help="where Kindle Previewer writes the KPF"
    )

    for name in PHASE_2_COMMANDS:
        subparsers.add_parser(name, help=f"(Phase {PHASE_2_COMMANDS[name][0]}) not implemented yet")

    return parser


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


def cmd_build(args) -> int:
    config = load_config(args.config)
    books = load_books()

    if args.no_commentary:
        config = Config(**{**vars(config), "commentaries": ()})

    provider = LocalProvider(
        books=books,
        expected_versions={
            "tanakh": config.tanakh_source.version_title,
            **{name: source.version_title for name, source in config.commentary_sources.items()},
        },
    )

    selections, default_name = _selections(args, config, books)
    available = set(provider.get_books())
    selections = [s for s in selections if s.book.sefaria_title in available]
    if not selections:
        print(
            "No local data for the requested books. Phase 1 builds from tests/fixtures/; "
            "run `python -m tanakh_epub fetch` once Phase 2 lands.",
            file=sys.stderr,
        )
        return 1

    chapters, text_versions, commentary_versions = load_chapters(provider, config, selections)
    output = args.output or (config.output_dir / default_name)

    result = EpubBuilder(config, books).build(
        chapters,
        output=output,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=datetime.now(UTC),
    )

    counts = stats(chapters)
    shown = (
        result.path.relative_to(PROJECT_ROOT)
        if result.path.is_relative_to(PROJECT_ROOT)
        else result.path
    )
    print(f"Built {shown}")
    print(f"  identifier         {result.identifier}")
    print(f"  chapter files      {len(result.chapters)}")
    print(f"  verses             {counts.verses}")
    print(
        f"  commentary entries {counts.commentary_entries} "
        f"({counts.verses_with_commentary} verses with, "
        f"{counts.verses_without_commentary} without)"
    )
    print(f"  size               {result.total_bytes / 1024:.0f} KB")
    for book, version in sorted(text_versions.items()):
        print(f"  text version       {book}: {version}")
    for name, version in sorted(commentary_versions.items()):
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

    if args.kpf:
        # Previewer fails if its output folder is the input's own folder, so use a subfolder.
        work_dir = result.path.parent / "kindle-previewer"
        converted = run_kindle_previewer(result.path, work_dir)
        print(f"\n{converted.message}")
        if not converted.passed:
            if converted.output:
                print("\n".join(f"  {line}" for line in converted.output.splitlines()))
            return 1
        kpf = max(work_dir.glob("**/*.kpf"), key=lambda p: p.stat().st_mtime)
        target = result.path.with_suffix(".kpf")
        shutil.copyfile(kpf, target)
        print(f"Wrote {target}")

    return 0


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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command in PHASE_2_COMMANDS:
        task = PHASE_2_COMMANDS[args.command]
        print(
            f'"{args.command}" is Phase 2, task {task} (see PROGRESS.md). '
            f"Phase 1 builds from the checked-in fixtures in tests/fixtures/.",
            file=sys.stderr,
        )
        return 2

    if args.command == "build":
        return cmd_build(args)
    if args.command == "check":
        return cmd_check(args)

    raise AssertionError(f"unhandled command {args.command!r}")

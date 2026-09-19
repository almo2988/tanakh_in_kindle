"""Command line interface — SPEC.md §31.

Phase 1 implements ``build``, ``check`` and ``experiment-layout`` (one EPUB per layout
profile, for the device to choose between — docs/LAYOUT_EXPERIMENT.md). ``fetch``, ``validate`` and
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
from .layout_experiment import build_variants, content_differences, format_report
from .paths import PROJECT_ROOT
from .processing.study_units import ChapterSelection, load_chapters, stats
from .providers.local import LocalProvider
from .validation_tools import ToolResult, run_epubcheck, run_kindle_previewer

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
    _add_selection_arguments(build)
    build.add_argument(
        "--layout-profile",
        metavar="NAME",
        default=None,
        help="a key under layout_profiles in the config (default: layout.profile)",
    )
    build.add_argument("--no-commentary", action="store_true", help="verses only")
    build.add_argument("--output", type=Path, default=None, help="output .epub path")
    _add_kpf_argument(build)

    experiment = subparsers.add_parser(
        "experiment-layout",
        help="build the same content once per layout profile, for the device test",
        description="Build one EPUB per layout profile from identical content — "
        "output/layout_<label>.epub — and print the parameters and sizes of each. "
        "With no selection, builds every book that has local data.",
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

    for name in PHASE_2_COMMANDS:
        subparsers.add_parser(name, help=f"(Phase {PHASE_2_COMMANDS[name][0]}) not implemented yet")

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


def _load_content(args, config: Config, books: BookTable):
    """The requested chapters as the internal model, or ``None`` if there is no local
    data for any of them."""
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
        return None
    return (*load_chapters(provider, config, selections), default_name)


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

    result = EpubBuilder(config, books).build(
        chapters,
        output=output,
        text_versions=text_versions,
        commentary_versions=commentary_versions,
        build_date=datetime.now(UTC),
    )

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
    if args.command == "experiment-layout":
        return cmd_experiment_layout(args)

    raise AssertionError(f"unhandled command {args.command!r}")

"""Wrappers around the external validators — SPEC.md §3.2.

Both tools are optional on a given machine and both are needed in the end. When one is
absent the wrapper says so plainly and reports "skipped" rather than pretending the check
passed; the build log has to show the difference.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import PROJECT_ROOT

EPUBCHECK_ENV = "EPUBCHECK_JAR"
KINDLE_PREVIEWER_ENV = "KINDLE_PREVIEWER"


@dataclass(frozen=True)
class ToolResult:
    tool: str
    available: bool
    passed: bool
    output: str
    message: str

    @property
    def skipped(self) -> bool:
        return not self.available


def find_epubcheck() -> list[str] | None:
    """``epubcheck`` on PATH, ``$EPUBCHECK_JAR``, or a jar under ``tools/``."""
    explicit = os.environ.get(EPUBCHECK_ENV)
    if explicit and Path(explicit).is_file():
        return ["java", "-jar", explicit]

    on_path = shutil.which("epubcheck")
    if on_path:
        return [on_path]

    jars = sorted((PROJECT_ROOT / "tools").glob("epubcheck*/epubcheck.jar"))
    if jars and shutil.which("java"):
        return ["java", "-jar", str(jars[-1])]
    return None


def run_epubcheck(epub: Path) -> ToolResult:
    command = find_epubcheck()
    if command is None:
        return ToolResult(
            tool="EPUBCheck",
            available=False,
            passed=False,
            output="",
            message=(
                "EPUBCheck not found — skipped. Install it, or set "
                f"{EPUBCHECK_ENV}=/path/to/epubcheck.jar, or run scripts/epubcheck.sh "
                "which downloads it into tools/."
            ),
        )

    completed = subprocess.run(
        [*command, str(epub)],
        capture_output=True,
        text=True,
    )
    output = (completed.stdout + completed.stderr).strip()
    return ToolResult(
        tool="EPUBCheck",
        available=True,
        passed=completed.returncode == 0,
        output=output,
        message="EPUBCheck passed" if completed.returncode == 0 else "EPUBCheck reported errors",
    )


KINDLE_PREVIEWER_APPS = (
    "/Applications/Kindle Previewer 4.app/Contents/MacOS/KindlePreviewer4CLI",
    "/Applications/Kindle Previewer 3.app/Contents/MacOS/Kindle Previewer 3",
)


def find_kindle_previewer() -> str | None:
    explicit = os.environ.get(KINDLE_PREVIEWER_ENV)
    if explicit and Path(explicit).exists():
        return explicit
    for name in ("kindlepreviewer", "KindlePreviewer", "KindlePreviewer4CLI"):
        found = shutil.which(name)
        if found:
            return found
    return next((app for app in KINDLE_PREVIEWER_APPS if Path(app).exists()), None)


def run_kindle_previewer(epub: Path, output_dir: Path) -> ToolResult:
    """Convert to KPF. macOS/Windows only; a clean skip everywhere else."""
    command = find_kindle_previewer()
    if command is None:
        return ToolResult(
            tool="Kindle Previewer",
            available=False,
            passed=False,
            output="",
            message=(
                "Kindle Previewer not found — skipped. It is macOS/Windows only; "
                f"set {KINDLE_PREVIEWER_ENV} to its executable if it is installed elsewhere. "
                "Kindle-specific rendering is not verified by this run."
            ),
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [command, str(epub), "--convert", "--output", str(output_dir)],
        capture_output=True,
        text=True,
    )
    output = (completed.stdout + completed.stderr).strip()
    kpf = sorted(output_dir.glob("**/*.kpf"), key=lambda p: p.stat().st_mtime)
    # Previewer falls back to Mobi when Enhanced Typesetting is unsupported: not a KPF.
    ok = completed.returncode == 0 and bool(kpf)
    return ToolResult(
        tool="Kindle Previewer",
        available=True,
        passed=ok,
        output=output,
        message=(
            f"Kindle Previewer conversion succeeded: {kpf[-1]}"
            if ok
            else "Kindle Previewer conversion failed or produced no KPF"
        ),
    )

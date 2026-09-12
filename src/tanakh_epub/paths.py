"""Where things live on disk.

Resolved from this file rather than from the current working directory, so the CLI
behaves the same however it is invoked.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]

CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"
BOOKS_CONFIG = CONFIG_DIR / "books.yaml"
COMMENTATORS_CONFIG = CONFIG_DIR / "commentators.yaml"

FONTS_DIR = PROJECT_ROOT / "fonts"
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

TEMPLATES_DIR = PACKAGE_ROOT / "rendering" / "templates"

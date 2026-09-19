#!/usr/bin/env bash
# Run EPUBCheck over an EPUB, downloading it into tools/ on first use.
#
#   scripts/epubcheck.sh output/Genesis_Chapter_1.epub
#
# Exits 0 when the file is valid, 1 when EPUBCheck reports errors, and 2 when the tool
# could not be made available — never 0 for a check that did not actually run.

set -euo pipefail

VERSION="${EPUBCHECK_VERSION:-5.2.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/tools"
JAR="${EPUBCHECK_JAR:-$TOOLS/epubcheck-$VERSION/epubcheck.jar}"

if [ $# -lt 1 ]; then
  echo "usage: $(basename "$0") <file.epub> [more.epub ...]" >&2
  exit 2
fi

# macOS ships a /usr/bin/java stub that fails when no JDK is installed. Kindle Previewer
# bundles a working JRE, so fall back to it rather than skipping the check.
if ! java -version >/dev/null 2>&1; then
  KP_JRE="/Applications/Kindle Previewer 4.app/Contents/Resources/KFXGen/jre/bin"
  if [ -x "$KP_JRE/java" ]; then
    export PATH="$KP_JRE:$PATH"
  fi
fi

if command -v epubcheck >/dev/null 2>&1 && [ ! -f "$JAR" ]; then
  exec epubcheck "$@"
fi

if [ ! -f "$JAR" ]; then
  if ! command -v java >/dev/null 2>&1; then
    echo "EPUBCheck needs Java, which is not installed. Skipping." >&2
    exit 2
  fi
  echo "Downloading EPUBCheck $VERSION into tools/ ..." >&2
  mkdir -p "$TOOLS"
  ZIP="$TOOLS/epubcheck-$VERSION.zip"
  curl -fsSL -o "$ZIP" \
    "https://github.com/w3c/epubcheck/releases/download/v$VERSION/epubcheck-$VERSION.zip"
  unzip -qo "$ZIP" -d "$TOOLS"
  rm -f "$ZIP"
fi

java -jar "$JAR" "$@"

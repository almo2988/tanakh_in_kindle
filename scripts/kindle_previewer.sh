#!/usr/bin/env bash
# Convert an EPUB with Kindle Previewer 3, which catches Kindle-specific rendering
# problems before the device does.
#
#   scripts/kindle_previewer.sh output/Genesis_Chapter_1.epub [output-dir]
#
# Kindle Previewer is macOS/Windows only and cannot be installed from a script. When it
# is absent this exits 2 with a message — a skipped check is never reported as a pass.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $(basename "$0") <file.epub> [output-dir]" >&2
  exit 2
fi

EPUB="$1"
OUT="${2:-$(dirname "$EPUB")/kindle-previewer}"

find_previewer() {
  if [ -n "${KINDLE_PREVIEWER:-}" ] && [ -e "$KINDLE_PREVIEWER" ]; then
    echo "$KINDLE_PREVIEWER"; return 0
  fi
  for candidate in kindlepreviewer KindlePreviewer; do
    if command -v "$candidate" >/dev/null 2>&1; then command -v "$candidate"; return 0; fi
  done
  MAC="/Applications/Kindle Previewer 3.app/Contents/MacOS/Kindle Previewer 3"
  if [ -x "$MAC" ]; then echo "$MAC"; return 0; fi
  return 1
}

if ! PREVIEWER="$(find_previewer)"; then
  cat >&2 <<'MSG'
Kindle Previewer 3 not found — skipped.

It runs on macOS and Windows only:
  https://www.amazon.com/Kindle-Previewer/b?node=21381691011

Set KINDLE_PREVIEWER=/path/to/the/executable if it is installed somewhere unusual.
Kindle-specific rendering has NOT been verified by this run.
MSG
  exit 2
fi

mkdir -p "$OUT"
"$PREVIEWER" "$EPUB" -convert -output "$OUT"

#!/usr/bin/env python3
"""Capture the Phase 1 test fixtures from the Sefaria API.

Run once. The fixtures are committed; nothing in the test suite or the Phase 1 build
touches the network. Re-run it only to re-capture, and expect the diff to be reviewed —
the Hebrew text must never change silently.

    python3 scripts/capture_fixtures.py

Two requests, one per index, each for a **whole book** (CLAUDE.md non-negotiable 7 — the
per-verse endpoints are never used). Chapter 1 is then sliced out of the response and
written verbatim: no normalization, no markup conversion, no re-encoding of entities.
That is the point of a fixture — it has to be able to catch a mistake in the pipeline,
which it cannot do if the pipeline has already touched it.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

USER_AGENT = (
    "tanakh-epub-generator/0.1 (+https://github.com/almo2988/tanakh_in_kindle; "
    "fixture capture, 2 requests)"
)
API = "https://www.sefaria.org/api/v3/texts/"

CHAPTER = 1

TARGETS = [
    {
        "out": "genesis_1.json",
        "index": "Genesis",
        "version_title": "Miqra according to the Masorah",
        "kind": "text",
        "depth": 2,
    },
    {
        "out": "rashi_genesis_1.json",
        "index": "Rashi on Genesis",
        "version_title": (
            "Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934"
        ),
        "kind": "commentary",
        "commentator": "Rashi",
        "depth": 3,
    },
]


def request_url(index: str, version_title: str) -> str:
    version = urllib.parse.quote(f"hebrew|{version_title}", safe="")
    return f"{API}{urllib.parse.quote(index)}?version={version}&return_format=default"


def curl_command(url: str) -> str:
    return f"curl -sS -A '{USER_AGENT}' '{url}'"


def fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def capture(target: dict) -> Path:
    url = request_url(target["index"], target["version_title"])
    print(f"GET {url}")
    payload = fetch(url)

    versions = payload.get("versions") or []
    if not versions:
        raise SystemExit(f'Sefaria returned no versions for "{target["index"]}"')
    version = versions[0]
    if version.get("versionTitle") != target["version_title"]:
        raise SystemExit(
            f'Asked for version "{target["version_title"]}" but got '
            f'"{version.get("versionTitle")}" — refusing to write a mislabelled fixture'
        )

    whole_book = version["text"]
    chapter = whole_book[CHAPTER - 1]

    fixture = {
        "_capture": {
            "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "command": curl_command(url),
            "script": "scripts/capture_fixtures.py",
            "note": (
                f"One whole-book request; chapter {CHAPTER} sliced out of the response and "
                "written verbatim. Markup, entities and Unicode are untouched."
            ),
            "whole_book_chapters": len(whole_book),
        },
        "index": target["index"],
        "kind": target["kind"],
        "version_title": version.get("versionTitle"),
        "language": version.get("actualLanguage") or version.get("language"),
        "license": version.get("license"),
        "version_source": version.get("versionSource"),
        "source": "api",
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "depth": target["depth"],
        "chapters_included": [CHAPTER],
        "text": [chapter],
    }
    if "commentator" in target:
        fixture["commentator"] = target["commentator"]

    path = FIXTURES / target["out"]
    path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"  → {path} ({path.stat().st_size:,} bytes)")
    return path


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for i, target in enumerate(TARGETS):
        if i:
            time.sleep(1)  # polite: a delay between requests (SPEC_DATA_SOURCE §2)
        capture(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The cover — SPEC.md §29.

``cover.mode``:

- ``generated`` (default): a plain black-and-white JPEG with the title in the biblical
  font. The Kindle library shows it; nothing else depends on it.
- ``custom``: ``cover.path``, a JPEG or PNG, used as is.
- ``none``: no cover.

Text is drawn with Pillow's basic layout engine, which lays characters out left to right.
The title is unpointed Hebrew — letters, spaces, geresh and gershayim, no combining marks —
so reversing it gives the correct visual order without a bidi or shaping library. A title
with ניקוד would need real shaping and is refused rather than drawn wrong.
"""

from __future__ import annotations

import io
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..paths import PROJECT_ROOT

WIDTH, HEIGHT = 1600, 2560
"""Amazon's recommended cover size (1:1.6)."""

TITLE_LINES = ("תנ״ך", "עם פירוש רש״י")
"""SPEC.md §29: `תנ״ך / עם פירוש רש״י`."""


@dataclass(frozen=True)
class Cover:
    data: bytes
    media_type: str
    extension: str


def _visual(line: str) -> str:
    if any(unicodedata.combining(c) for c in line):
        raise ValueError(f"cover text {line!r} has combining marks; basic layout cannot draw them")
    return line[::-1]


def generate_cover(config: Config, lines: tuple[str, ...] = TITLE_LINES) -> Cover:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    font_path = str(config.biblical_font.file)
    sizes = (420, 170)

    # Measure every line first so the block can be centred vertically.
    rendered = []
    for line, size in zip(lines, sizes, strict=False):
        font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.BASIC)
        text = _visual(line)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        rendered.append((text, font, right - left, bottom - top, left, top))

    rule_gap = 150
    block = sum(h for _, _, _, h, _, _ in rendered) + 2 * rule_gap
    y = (HEIGHT - block) // 2

    for index, (text, font, width, height, left, top) in enumerate(rendered):
        draw.text(((WIDTH - width) // 2 - left, y - top), text, font=font, fill=0)
        y += height
        if index == 0:
            # A single rule between the two lines — the same device as the commentary
            # divider inside the book.
            y += rule_gap
            draw.rectangle(((WIDTH // 2 - 260, y), (WIDTH // 2 + 260, y + 6)), fill=0)
            y += rule_gap

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90, optimize=True)
    return Cover(out.getvalue(), "image/jpeg", "jpg")


def load_cover(config: Config) -> Cover | None:
    mode = config.cover_mode
    if mode == "none":
        return None
    if mode == "generated":
        return generate_cover(config)
    if mode == "custom":
        raw = (config.raw.get("cover") or {}).get("path")
        if not raw:
            raise ValueError("cover.mode is custom but cover.path is not set")
        path = Path(raw)
        path = path if path.is_absolute() else PROJECT_ROOT / path
        suffix = path.suffix.lower()
        media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix)
        if media is None:
            raise ValueError(f"cover.path must be a JPEG or PNG, not {path.name}")
        return Cover(path.read_bytes(), media, "png" if suffix == ".png" else "jpg")
    raise ValueError(f"cover.mode must be none, generated or custom, not {mode!r}")

"""Markup inventory — SPEC_DATA_SOURCE.md §9.1.

Every tag + attribute combination, every named or numeric character reference, and every
invisible or private-use character in the source strings, with a count and the first
reference where it occurs. Each tag combination is marked known or unknown against
``markup.RULES``, so the inventory answers the one question that matters before a build:
is there anything the converter would stop on?
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser

from .markup import RULES

KNOWN_ENTITIES = frozenset({"nbsp", "thinsp", "amp", "lt", "gt", "quot"})
"""Resolved by the parser to the character they name; U+00A0 and U+2009 are then kept."""

INVISIBLE_CATEGORIES = frozenset({"Cf", "Co", "Cc", "Cs"})


@dataclass
class Pattern:
    kind: str
    """``tag`` · ``entity`` · ``char``."""

    key: str
    count: int = 0
    example: str = ""
    known: bool = True


@dataclass
class Inventory:
    sources: list[str] = field(default_factory=list)
    strings: int = 0
    patterns: dict[tuple[str, str], Pattern] = field(default_factory=dict)

    def add(self, kind: str, key: str, reference: str, *, known: bool) -> None:
        pattern = self.patterns.get((kind, key))
        if pattern is None:
            pattern = self.patterns[(kind, key)] = Pattern(
                kind, key, example=reference, known=known
            )
        pattern.count += 1

    @property
    def unknown(self) -> list[Pattern]:
        return [p for p in self.patterns.values() if not p.known]


class _Scanner(HTMLParser):
    def __init__(self, inventory: Inventory, reference: str) -> None:
        super().__init__(convert_charrefs=False)
        self.inventory = inventory
        self.reference = reference

    def _tag(self, tag: str, attrs) -> None:
        css_class = next((v for n, v in attrs if n == "class"), None)
        css_class = (css_class or "").strip() or None
        others = sorted(n for n, _ in attrs if n != "class")
        key = f"<{tag}" + (f' class="{css_class}"' if css_class else "")
        key += "".join(f" {name}=…" for name in others) + ">"
        known = not others and (tag, css_class) in RULES
        self.inventory.add("tag", key, self.reference, known=known)

    def handle_starttag(self, tag, attrs) -> None:
        self._tag(tag, attrs)

    def handle_startendtag(self, tag, attrs) -> None:
        self._tag(tag, attrs)

    def handle_entityref(self, name) -> None:
        self.inventory.add("entity", f"&{name};", self.reference, known=name in KNOWN_ENTITIES)

    def handle_charref(self, name) -> None:
        # A numeric reference resolves to exactly the character it names.
        self.inventory.add("entity", f"&#{name};", self.reference, known=True)

    def handle_comment(self, data) -> None:
        self.inventory.add("tag", "<!-- comment -->", self.reference, known=False)


def strings_with_references(text: list, prefix: str) -> Iterator[tuple[str, str]]:
    """``("Genesis 1:1", "…")`` for every non-empty string in a nested Sefaria list."""

    def walk(node, path: tuple[int, ...]):
        if isinstance(node, str):
            if node.strip():
                yield f"{prefix} " + ":".join(str(n) for n in path), node
        elif isinstance(node, list):
            for number, child in enumerate(node, start=1):
                yield from walk(child, (*path, number))

    yield from walk(text, ())


def scan(inventory: Inventory, label: str, text: list) -> None:
    """Add one whole index (``label`` is its Sefaria title) to the inventory."""
    inventory.sources.append(label)
    for reference, raw in strings_with_references(text, label):
        inventory.strings += 1
        scanner = _Scanner(inventory, reference)
        scanner.feed(raw)
        scanner.close()
        for char in raw:
            category = unicodedata.category(char)
            if category in INVISIBLE_CATEGORIES:
                name = unicodedata.name(char, "unnamed")
                # Kept verbatim (the text is never altered), but worth seeing.
                inventory.add("char", f"U+{ord(char):04X} {name}", reference, known=True)


def format_inventory(inventory: Inventory) -> str:
    lines = [
        "MARKUP INVENTORY",
        f"Sources:  {', '.join(inventory.sources)}",
        f"Strings:  {inventory.strings:,}",
        "",
    ]
    titles = {"tag": "Tags", "entity": "Character references", "char": "Invisible characters"}
    for kind, title in titles.items():
        rows = sorted(
            (p for p in inventory.patterns.values() if p.kind == kind),
            key=lambda p: (-p.count, p.key),
        )
        if not rows:
            continue
        lines.append(title)
        for p in rows:
            status = "known  " if p.known else "UNKNOWN"
            lines.append(f"  {status} {p.count:7,}  {p.key:<40}  e.g. {p.example}")
        lines.append("")
    unknown = inventory.unknown
    lines.append(f"Unknown patterns: {len(unknown)}")
    for p in unknown:
        lines.append(f"  {p.key}  ({p.count}×, first at {p.example})")
    return "\n".join(lines) + "\n"

"""Sefaria markup → internal markup — SPEC_DATA_SOURCE.md §8–§9.

Two rules govern this module.

**Parse, never regex.** Sefaria strings carry inline HTML; they go through a real parser
and come out as internal markup. ``html = response["text"]`` pasted into a template is
forbidden (SPEC_DATA_SOURCE.md §8).

**Fail loudly.** Anything not in ``RULES`` stops the build, naming the tag, the class and
the reference that produced it. Silently stripping an unknown tag is how a parasha marker,
a ניקוד-bearing letter, or half a verse disappears without anyone noticing (CLAUDE.md
non-negotiable 6).

Phase 1 scope: the table below covers exactly the patterns present in the checked-in
fixtures, and nothing else — an untested rule is worse than a loud failure. Phase 2 runs
``inventory-markup`` over the full dataset and extends the table from what it finds
(PROGRESS.md task 2.6).

Internal markup (SPEC_DATA_SOURCE.md §9.3) is a closed subset: ``<b>``, ``<em>``,
``<span class="letter-large|letter-small|parasha-marker">``, and paragraph breaks written
as a blank line. ``assert_internal_markup_only`` enforces it before rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

from .normalize import collapse_whitespace, to_nfc

PARAGRAPH_SEPARATOR = "\n\n"
"""How a paragraph break is carried inside a single model string."""

ALLOWED_TAGS = ("b", "em", "span")
ALLOWED_SPAN_CLASSES = ("letter-large", "letter-small", "parasha-marker")

PARAGRAPH_ENDING_MARKERS = ("{פ}",)
"""A closed parasha ends the paragraph; an open one, {ס}, does not — SPEC_DATA_SOURCE §9.2."""


class UnknownMarkupError(RuntimeError):
    """Markup the rules table does not cover reached the converter. The build stops here."""


class InternalMarkupError(RuntimeError):
    """Converted text contains something outside the internal subset."""


@dataclass(frozen=True)
class Rule:
    """What to do with one source tag.

    ``action``:
      ``keep``      emit the same tag (its name must already be internal markup)
      ``rename``    emit ``tag`` instead
      ``wrap``      emit ``<span class="{css_class}">``
      ``paragraph`` a void tag that ends the current paragraph
      ``drop``      discard the element **and its content**
    """

    action: str
    tag: str | None = None
    css_class: str | None = None
    note: str = ""


RULES: dict[tuple[str, str | None], Rule] = {
    # ---- Tanakh — "Miqra according to the Masorah" -----------------------
    ("big", None): Rule(
        "wrap",
        tag="span",
        css_class="letter-large",
        note="enlarged Masoretic letter, e.g. the ב of בראשית",
    ),
    ("small", None): Rule(
        "wrap", tag="span", css_class="letter-small", note="reduced letter, and the paseq ׀"
    ),
    ("span", "mam-spi-pe"): Rule(
        "wrap", tag="span", css_class="parasha-marker", note="closed parasha marker {פ}"
    ),
    ("br", None): Rule("paragraph", note="paragraph break"),
    # ---- Both ------------------------------------------------------------
    # A <b> leading a commentary entry is the dibur hamatchil and is extracted before this
    # table is consulted. Every other <b> — the bold paseq in Genesis 1:29–30, a bold run
    # inside a Rashi entry — is kept as <b>.
    ("b", None): Rule("keep", tag="b", note="bold run; kept"),
}

VOID_TAGS = frozenset({"br"})


# ---------------------------------------------------------------------------
# A minimal tree, so that "the entry's leading element" is a structural question
# rather than a string-matching one.
# ---------------------------------------------------------------------------


@dataclass
class Text:
    value: str


@dataclass
class Break:
    """A paragraph boundary."""


@dataclass
class Element:
    tag: str
    css_class: str | None = None
    children: list = field(default_factory=list)

    def plain_text(self) -> str:
        parts = []
        for child in self.children:
            if isinstance(child, Text):
                parts.append(child.value)
            elif isinstance(child, Element):
                parts.append(child.plain_text())
        return "".join(parts)


Node = Text | Break | Element


class _Converter(HTMLParser):
    """Turns one Sefaria string into a list of internal nodes.

    ``convert_charrefs`` is on, so ``&nbsp;`` and ``&thinsp;`` arrive as U+00A0 and
    U+2009 — which is what the source means by them, and which ``normalize`` then leaves
    alone rather than collapsing into an ordinary space.
    """

    def __init__(self, reference: str) -> None:
        super().__init__(convert_charrefs=True)
        self.reference = reference
        self.nodes: list[Node] = []
        self._open: list[tuple[str, Element]] = []
        self._dropping: list[str] = []

    # -- helpers ----------------------------------------------------------

    def _append(self, node: Node) -> None:
        (self._open[-1][1].children if self._open else self.nodes).append(node)

    def _unknown(self, tag: str, css_class: str | None, extra: str = "") -> None:
        described = f"<{tag}" + (f' class="{css_class}"' if css_class else "") + ">"
        detail = f" — {extra}" if extra else ""
        raise UnknownMarkupError(
            f"Unknown Sefaria markup {described} at {self.reference}{detail}. "
            f"Nothing is stripped silently: add a rule to markup.RULES "
            f"(and a row to docs/MARKUP_RULES.md) once you know what it means."
        )

    def _rule(self, tag: str, attrs) -> Rule:
        css_class: str | None = None
        for name, value in attrs:
            if name == "class":
                css_class = (value or "").strip() or None
            else:
                self._unknown(tag, None, extra=f'carries an unexpected attribute "{name}"')

        rule = RULES.get((tag, css_class))
        if rule is None:
            # A known tag with an unknown class is still unknown: on MAM spans the class
            # carries the entire meaning of the element.
            self._unknown(tag, css_class)
        return rule

    def _start(self, tag: str, attrs, *, self_closing: bool) -> None:
        rule = self._rule(tag, attrs)

        if rule.action == "paragraph":
            if self._open:
                self._unknown(
                    tag,
                    None,
                    extra="a paragraph break inside inline markup is not handled in Phase 1",
                )
            self.nodes.append(Break())
            return

        if rule.action == "drop":
            if not (self_closing or tag in VOID_TAGS):
                self._dropping.append(tag)
            return

        element = Element(
            tag=rule.tag or tag,
            css_class=rule.css_class if rule.action == "wrap" else None,
        )
        self._append(element)
        if not (self_closing or tag in VOID_TAGS):
            self._open.append((tag, element))

    # -- HTMLParser hooks -------------------------------------------------

    def handle_starttag(self, tag: str, attrs) -> None:
        if self._dropping:
            self._dropping.append(tag)
            return
        self._start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag: str, attrs) -> None:
        if self._dropping:
            return
        self._start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag: str) -> None:
        if self._dropping:
            if self._dropping[-1] == tag:
                self._dropping.pop()
            return
        if tag in VOID_TAGS:
            return
        if self._open and self._open[-1][0] == tag:
            self._open.pop()
        # A stray close tag (`</b>` with nothing open) is dropped rather than unwinding
        # something it does not own; the internal-markup audit catches any damage.

    def handle_data(self, data: str) -> None:
        if self._dropping or not data:
            return
        self._append(Text(data))

    def close_and_finish(self) -> list[Node]:
        self.close()
        return _break_after_parasha_markers(self.nodes)


def _break_after_parasha_markers(nodes: list[Node]) -> list[Node]:
    """A closed parasha ends the paragraph — SPEC_DATA_SOURCE.md §9.2.

    Done after parsing so the break lands *after* the marker's own element, not inside it.
    """
    out: list[Node] = []
    for node in nodes:
        out.append(node)
        if isinstance(node, Break):
            continue
        rendered = node.value if isinstance(node, Text) else node.plain_text()
        if any(marker in rendered for marker in PARAGRAPH_ENDING_MARKERS):
            out.append(Break())
    return out


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _serialize(nodes: list[Node]) -> str:
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(_escape(node.value))
        elif isinstance(node, Break):
            out.append(PARAGRAPH_SEPARATOR)
        else:
            attr = f' class="{node.css_class}"' if node.css_class else ""
            out.append(f"<{node.tag}{attr}>{_serialize(node.children)}</{node.tag}>")
    return "".join(out)


def _parse(raw: str, reference: str) -> list[Node]:
    converter = _Converter(reference)
    converter.feed(to_nfc(raw))
    return converter.close_and_finish()


def _finish(nodes: list[Node]) -> str:
    return collapse_whitespace(_serialize(nodes), preserve_paragraphs=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvertedEntry:
    text: str
    dibur_hamatchil: str | None


def convert_verse(raw: str, *, reference: str) -> str:
    """Convert one biblical verse string to internal markup."""
    return _finish(_parse(raw, reference))


def convert_commentary_entry(raw: str, *, reference: str) -> ConvertedEntry:
    """Convert one commentary entry, splitting off its dibur hamatchil.

    The dibur hamatchil comes from the entry's own leading ``<b>`` element — structural
    extraction from Sefaria's markup, never a text match against the verse
    (SPEC_DATA_SOURCE.md §9.2).
    """
    nodes = _parse(raw, reference)

    index = 0
    while index < len(nodes) and isinstance(nodes[index], Text) and not nodes[index].value.strip():
        index += 1

    dibur: str | None = None
    leading = nodes[index] if index < len(nodes) else None
    if isinstance(leading, Element) and leading.tag == "b" and leading.css_class is None:
        dibur = collapse_whitespace(leading.plain_text()) or None
        if dibur is not None:
            nodes = nodes[:index] + nodes[index + 1 :]

    return ConvertedEntry(text=_finish(nodes), dibur_hamatchil=dibur)


def paragraphs(text: str) -> list[str]:
    """Split internal markup into the paragraphs the renderer emits."""
    return [part for part in text.split(PARAGRAPH_SEPARATOR) if part]


class _InternalMarkupAudit(HTMLParser):
    def __init__(self, reference: str) -> None:
        super().__init__(convert_charrefs=False)
        self.reference = reference

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in ALLOWED_TAGS:
            raise InternalMarkupError(
                f"<{tag}> survived conversion at {self.reference}; "
                f"internal markup allows only {list(ALLOWED_TAGS)}"
            )
        classes = [value for name, value in attrs if name == "class"]
        if [name for name, _ in attrs if name != "class"]:
            raise InternalMarkupError(f"<{tag}> carries a non-class attribute at {self.reference}")
        if tag == "span":
            if len(classes) != 1 or classes[0] not in ALLOWED_SPAN_CLASSES:
                raise InternalMarkupError(
                    f'<span class="{classes[0] if classes else ""}"> is not internal markup '
                    f"at {self.reference}; allowed: {list(ALLOWED_SPAN_CLASSES)}"
                )
        elif classes:
            raise InternalMarkupError(f"<{tag}> carries a class at {self.reference}")

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)


def assert_internal_markup_only(text: str, *, reference: str) -> None:
    """Guard for SPEC_DATA_SOURCE.md §9.3 — run over everything before it is rendered."""
    audit = _InternalMarkupAudit(reference)
    audit.feed(text)
    audit.close()

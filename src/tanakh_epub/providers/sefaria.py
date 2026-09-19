"""Sefaria provider — SPEC_DATA_SOURCE.md §1–§5, §11, §17.

Fetches **whole books** (never verses) and writes them to ``data/cache/`` in the file shape
``LocalProvider`` reads. The build never calls this module: it reads the cache, so an
offline build works once a book is cached, and nothing above the provider layer performs
HTTP (SPEC_DATA_SOURCE.md §2).

Two official sources, no scraping:

- **Sefaria-Export**, a public Google Cloud Storage bucket with one JSON file per
  index/language/version. Preferred for whole books (§2). The file's path is built from the
  index's own ``categories``, which the API reports.
- **The Sefaria API**, for version discovery (``list_versions``), index metadata, and as the
  fallback when the export has no file for a version.

Both return the same nested ``[chapter][verse]`` / ``[chapter][verse][entry]`` lists with the
same inline markup — checked byte for byte on בראשית א׳ and רש״י on it when this module
was written. Whatever comes back is stored verbatim: no normalization, no markup
conversion. That happens later, in ``processing``, where it can be tested.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import __version__
from .base import ProviderError

API = "https://www.sefaria.org/api"
EXPORT = "https://storage.googleapis.com/sefaria-export/json"

USER_AGENT = (
    f"tanakh-epub-generator/{__version__} "
    "(+https://github.com/almo2988/tanakh_in_kindle; whole-book fetch for a personal EPUB)"
)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class NotFound(ProviderError):
    """HTTP 404 — the index, version or export file does not exist."""


Transport = Callable[[str, float], bytes]
"""``(url, timeout) -> body``. Raises ``urllib.error.HTTPError`` / ``URLError`` / ``TimeoutError``
like ``urllib`` does. Injected so the retry logic can be tested without a network."""


def _urllib_transport(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class SefariaClient:
    """Polite HTTP: a descriptive User-Agent, a delay between requests, and exponential
    backoff on 429/5xx and network errors (SPEC_DATA_SOURCE.md §2, §17)."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        delay: float = 1.0,
        retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport or _urllib_transport
        self.delay = delay
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.sleep = sleep
        self.clock = clock
        self._last_request: float | None = None
        self.requests: list[str] = []
        """Every URL requested, in order — for the fetch log and for tests."""

    def _wait_turn(self) -> None:
        if self._last_request is not None:
            remaining = self.delay - (self.clock() - self._last_request)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request = self.clock()

    def get_json(self, url: str, *, what: str) -> Any:
        """GET and decode JSON. ``what`` names the thing for error messages, e.g.
        ``"Rashi on Genesis" (version "…")``."""
        attempt = 0
        while True:
            self._wait_turn()
            self.requests.append(url)
            try:
                body = self.transport(url, self.timeout)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise NotFound(f"Could not retrieve {what}: HTTP 404 at {url}") from None
                if exc.code not in RETRYABLE_STATUS or attempt >= self.retries:
                    raise ProviderError(
                        f"Could not retrieve {what}: HTTP {exc.code}"
                        + (f" after {attempt} retries" if attempt else "")
                    ) from None
                reason = f"HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt >= self.retries:
                    detail = getattr(exc, "reason", None) or exc
                    raise ProviderError(
                        f"Could not retrieve {what}: {detail} after {attempt} retries"
                    ) from None
                reason = type(exc).__name__
            else:
                try:
                    return json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProviderError(
                        f"Could not retrieve {what}: invalid JSON ({exc})"
                    ) from None

            wait = self.backoff * (2**attempt)
            attempt += 1
            print(f"  {reason} for {what}; retry {attempt}/{self.retries} in {wait:.0f}s")
            self.sleep(wait)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionInfo:
    """One version of an index, as the API lists it."""

    version_title: str
    language: str
    license: str
    version_source: str | None
    priority: float | None
    status: str | None
    is_primary: bool


@dataclass(frozen=True)
class IndexInfo:
    title: str
    categories: tuple[str, ...]
    depth: int
    lengths: tuple[int, ...]
    """Sefaria's own counts: ``[chapters, verses]`` for a book, ``[chapters, verses with
    commentary, entries]`` for a commentary. The validation report checks against these."""


@dataclass(frozen=True)
class FetchedBook:
    index: IndexInfo
    version: VersionInfo
    text: list
    source: str
    """``export`` or ``api``."""

    url: str


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class SefariaProvider:
    """Whole-book access to Sefaria. The signatures follow SPEC_DATA_SOURCE.md §2."""

    def __init__(self, client: SefariaClient | None = None, *, prefer: str = "export") -> None:
        if prefer not in ("export", "api"):
            raise ValueError(f'prefer must be "export" or "api", not {prefer!r}')
        self.client = client or SefariaClient()
        self.prefer = prefer
        self._indexes: dict[str, IndexInfo] = {}

    # -- discovery --------------------------------------------------------

    def get_index(self, index_title: str) -> IndexInfo:
        """Raises ``NotFound`` when the index does not exist — for a commentary, that means
        "no commentary for this book" (SPEC_DATA_SOURCE.md §5), and the caller decides."""
        if index_title not in self._indexes:
            url = f"{API}/v2/index/{_quote(index_title)}"
            raw = self.client.get_json(url, what=f'the index "{index_title}"')
            if not isinstance(raw, dict) or "error" in raw or "title" not in raw:
                raise NotFound(f'Sefaria has no index "{index_title}"')
            schema = raw.get("schema") or {}
            self._indexes[index_title] = IndexInfo(
                title=raw["title"],
                categories=tuple(raw.get("categories") or ()),
                depth=int(schema.get("depth") or 0),
                lengths=tuple(int(n) for n in schema.get("lengths") or ()),
            )
        return self._indexes[index_title]

    def list_versions(self, index_title: str) -> list[VersionInfo]:
        url = f"{API}/texts/versions/{_quote(index_title)}"
        raw = self.client.get_json(url, what=f'the versions of "{index_title}"')
        if not isinstance(raw, list):
            raise NotFound(f'Sefaria lists no versions for "{index_title}"')
        return [_version(entry) for entry in raw]

    def find_version(self, index_title: str, version_title: str) -> VersionInfo:
        """The Hebrew version with exactly this title, or a clear error listing the others."""
        versions = self.list_versions(index_title)
        for version in versions:
            if version.version_title == version_title and version.language == "he":
                return version
        hebrew = sorted(v.version_title for v in versions if v.language == "he")
        raise ProviderError(
            f'"{index_title}" has no Hebrew version "{version_title}". '
            f"Hebrew versions available: {hebrew or 'none'}"
        )

    # -- whole books ------------------------------------------------------

    def fetch_book(self, index_title: str, *, version_title: str, depth: int) -> FetchedBook:
        """One whole index, one version. Export first (or API first with ``prefer="api"``),
        the other as the fallback when the first has no such file."""
        index = self.get_index(index_title)
        if index.depth != depth:
            raise ProviderError(
                f'"{index_title}" has depth {index.depth} on Sefaria; expected {depth}'
            )
        version = self.find_version(index_title, version_title)
        what = f'"{index_title}" (version "{version_title}")'

        order = [self._from_export, self._from_api]
        if self.prefer == "api":
            order.reverse()
        misses: list[str] = []
        for attempt in order:
            try:
                text, source, url = attempt(index, version_title, what)
            except NotFound as exc:
                misses.append(str(exc))
                continue
            _check_shape(text, depth, what)
            return FetchedBook(index=index, version=version, text=text, source=source, url=url)
        raise ProviderError(
            f"Could not retrieve {what} from either source:\n  " + "\n  ".join(misses)
        )

    def _from_export(self, index: IndexInfo, version_title: str, what: str):
        path = "/".join(_quote(part) for part in (*index.categories, index.title, "Hebrew"))
        url = f"{EXPORT}/{path}/{_quote(version_title)}.json"
        raw = self.client.get_json(url, what=f"{what} from Sefaria-Export")
        if not isinstance(raw, dict) or raw.get("versionTitle") != version_title:
            found = raw.get("versionTitle") if isinstance(raw, dict) else type(raw).__name__
            raise ProviderError(f'Sefaria-Export returned version "{found}" for {what}')
        return raw.get("text"), "export", url

    def _from_api(self, index: IndexInfo, version_title: str, what: str):
        version = _quote(f"hebrew|{version_title}")
        url = f"{API}/v3/texts/{_quote(index.title)}?version={version}&return_format=default"
        raw = self.client.get_json(url, what=f"{what} from the API")
        versions = raw.get("versions") if isinstance(raw, dict) else None
        if not versions:
            raise NotFound(f"The API returned no text for {what}")
        if versions[0].get("versionTitle") != version_title:
            raise ProviderError(
                f'Asked the API for {what} but got version "{versions[0].get("versionTitle")}"'
            )
        return versions[0].get("text"), "api", url

    def get_book_text(self, book: str, *, version_title: str) -> list[list[str]]:
        return self.fetch_book(book, version_title=version_title, depth=2).text

    def get_book_commentary(
        self, commentator_prefix: str, book: str, *, version_title: str
    ) -> list[list[list[str]]]:
        index_title = f"{commentator_prefix}{book}"
        return self.fetch_book(index_title, version_title=version_title, depth=3).text


def _quote(part: str) -> str:
    return urllib.parse.quote(part, safe="")


def _version(entry: dict) -> VersionInfo:
    priority = entry.get("priority")
    return VersionInfo(
        version_title=entry.get("versionTitle", ""),
        language=entry.get("actualLanguage") or entry.get("language") or "",
        license=entry.get("license") or "unknown",
        version_source=entry.get("versionSource"),
        priority=float(priority) if isinstance(priority, int | float) else None,
        status=entry.get("status"),
        is_primary=bool(entry.get("isPrimary")),
    )


def _check_shape(text: Any, depth: int, what: str) -> None:
    """Refuse anything that is not the nested list the index promises (§17: malformed data
    fails clearly, never as a half-built book)."""

    def ok(node: Any, level: int) -> bool:
        if level == 0:
            return isinstance(node, str)
        # Sefaria pads missing sections with "" or [] at any level.
        if node == "" or node is None:
            return True
        return isinstance(node, list) and all(ok(child, level - 1) for child in node)

    if not isinstance(text, list) or not text or not ok(text, depth):
        raise ProviderError(f"{what} is not a depth-{depth} nested list of strings")


# ---------------------------------------------------------------------------
# Cache — SPEC_DATA_SOURCE.md §11
# ---------------------------------------------------------------------------


def cache_path(cache_dir: Path, subdir: str, slug: str) -> Path:
    """``data/cache/tanakh/genesis.json``, ``data/cache/rashi/genesis.json``."""
    return cache_dir / subdir / f"{slug}.json"


def cached_version(path: Path) -> str | None:
    """The version a cache file holds, or ``None`` if there is no readable file."""
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version_title")
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return None


def write_cache(
    path: Path,
    fetched: FetchedBook,
    *,
    kind: str,
    depth: int,
    commentator: str | None = None,
    now: datetime | None = None,
) -> None:
    """Write in the shape ``LocalProvider`` reads. The text is stored verbatim."""
    payload: dict[str, Any] = {
        "index": fetched.index.title,
        "kind": kind,
        "version_title": fetched.version.version_title,
        "language": fetched.version.language,
        "license": fetched.version.license,
        "version_source": fetched.version.version_source,
        "provider": "Sefaria",
        "source": fetched.source,
        "source_request": fetched.url,
        "fetched_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "categories": list(fetched.index.categories),
        "index_lengths": list(fetched.index.lengths),
        "depth": depth,
        "text": fetched.text,
    }
    if commentator:
        payload["commentator"] = commentator
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)

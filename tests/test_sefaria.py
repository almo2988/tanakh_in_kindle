"""SPEC_DATA_SOURCE.md §2, §11, §12, §17 — the Sefaria provider and the cache, offline.

A fake transport stands in for the network, so retries, fallbacks and the cache are tested
without a request leaving the machine. The real endpoints are exercised by
tests/test_sefaria_network.py, which only runs with RUN_NETWORK_TESTS=1.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from tanakh_epub.paths import FIXTURES_DIR
from tanakh_epub.providers.base import ProviderError
from tanakh_epub.providers.fetch import fetch_book
from tanakh_epub.providers.local import LocalProvider
from tanakh_epub.providers.sefaria import (
    API,
    EXPORT,
    USER_AGENT,
    NotFound,
    SefariaClient,
    SefariaProvider,
    cache_path,
    cached_version,
)

TANAKH = "Miqra according to the Masorah"
RASHI = "Pentateuch with Rashi's commentary by M. Rosenbaum and A.M. Silbermann, 1929-1934"


def _fixture_text(name: str) -> list:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))["text"]


GENESIS = _fixture_text("genesis_1.json")
RASHI_GENESIS = _fixture_text("rashi_genesis_1.json")


def _http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "error", {}, io.BytesIO(b""))


class FakeSefaria:
    """Answers the handful of URLs the provider uses. ``fail`` maps a URL substring to a
    list of HTTP codes to raise, one per request, before answering normally."""

    def __init__(self, *, export: bool = True, rashi: bool = True) -> None:
        self.export = export
        self.rashi = rashi
        self.fail: dict[str, list[int | Exception]] = {}
        self.seen: list[str] = []

    def __call__(self, url: str, timeout: float) -> bytes:
        self.seen.append(url)
        for fragment, failures in self.fail.items():
            if fragment in url and failures:
                failure = failures.pop(0)
                if isinstance(failure, Exception):
                    raise failure
                raise _http_error(url, failure)
        return json.dumps(self._answer(url)).encode("utf-8")

    def _answer(self, url: str):
        rashi = "Rashi%20on%20Genesis" in url
        if rashi and not self.rashi:
            if url.startswith(f"{API}/v2/index/"):
                return {"error": "Index not found"}
            raise _http_error(url, 404)
        if url.startswith(f"{API}/v2/index/"):
            if rashi:
                return {
                    "title": "Rashi on Genesis",
                    "categories": ["Tanakh", "Rishonim on Tanakh", "Rashi", "Torah"],
                    "schema": {"depth": 3, "lengths": [50, 1072, 2017]},
                }
            return {
                "title": "Genesis",
                "categories": ["Tanakh", "Torah"],
                "schema": {"depth": 2, "lengths": [50, 1533]},
            }
        if url.startswith(f"{API}/texts/versions/"):
            title = RASHI if rashi else TANAKH
            return [
                {"versionTitle": "The Koren Jerusalem Bible", "language": "en"},
                {
                    "versionTitle": title,
                    "language": "he",
                    "actualLanguage": "he",
                    "license": "Public Domain" if rashi else "CC-BY-SA",
                    "versionSource": "https://example.org/source",
                    "priority": 2,
                    "status": "locked",
                    "isPrimary": True,
                },
            ]
        if url.startswith(EXPORT):
            if not self.export:
                raise _http_error(url, 404)
            return {
                "versionTitle": RASHI if rashi else TANAKH,
                "text": RASHI_GENESIS if rashi else GENESIS,
            }
        if url.startswith(f"{API}/v3/texts/"):
            return {
                "versions": [
                    {
                        "versionTitle": RASHI if rashi else TANAKH,
                        "text": RASHI_GENESIS if rashi else GENESIS,
                    }
                ]
            }
        raise AssertionError(f"unexpected URL {url}")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def _provider(fake: FakeSefaria, clock: FakeClock | None = None, **kwargs) -> SefariaProvider:
    clock = clock or FakeClock()
    client = SefariaClient(transport=fake, sleep=clock.sleep, clock=clock, **kwargs)
    return SefariaProvider(client)


# ---- Politeness and failure handling --------------------------------------------------


def test_user_agent_names_the_project() -> None:
    assert "tanakh-epub-generator" in USER_AGENT
    assert "github.com/almo2988/tanakh_in_kindle" in USER_AGENT


def test_requests_are_spaced_by_the_delay() -> None:
    clock = FakeClock()
    provider = _provider(FakeSefaria(), clock, delay=1.0)
    provider.get_index("Genesis")
    provider.list_versions("Genesis")
    assert clock.sleeps == [1.0]


def test_transient_errors_back_off_exponentially_then_succeed() -> None:
    fake = FakeSefaria()
    fake.fail["/v2/index/"] = [503, 429]
    clock = FakeClock()
    provider = _provider(fake, clock, delay=0, backoff=2.0)
    assert provider.get_index("Genesis").lengths == (50, 1533)
    assert clock.sleeps == [2.0, 4.0]


def test_gives_up_after_the_retries_with_a_clear_message() -> None:
    fake = FakeSefaria()
    fake.fail["/v2/index/"] = [TimeoutError("timed out")] * 4
    provider = _provider(fake, delay=0)
    with pytest.raises(ProviderError, match=r'Could not retrieve the index "Genesis".*3 retries'):
        provider.get_index("Genesis")


def test_a_client_error_is_not_retried() -> None:
    fake = FakeSefaria()
    fake.fail["/v2/index/"] = [400]
    provider = _provider(fake, delay=0)
    with pytest.raises(ProviderError, match="HTTP 400"):
        provider.get_index("Genesis")
    assert len(fake.seen) == 1


def test_invalid_json_fails_clearly() -> None:
    client = SefariaClient(transport=lambda url, timeout: b"<html>", delay=0)
    with pytest.raises(ProviderError, match="invalid JSON"):
        client.get_json("https://example.org", what="something")


# ---- Whole books ------------------------------------------------------------------------


def test_whole_book_comes_from_the_export_first() -> None:
    fake = FakeSefaria()
    fetched = _provider(fake, delay=0).fetch_book("Genesis", version_title=TANAKH, depth=2)
    assert fetched.source == "export"
    assert fetched.text == GENESIS
    assert (
        fetched.url
        == f"{EXPORT}/Tanakh/Torah/Genesis/Hebrew/Miqra%20according%20to%20the%20Masorah.json"
    )
    assert not any("/v3/texts/" in url for url in fake.seen)


def test_api_is_the_fallback_when_the_export_has_no_file() -> None:
    fetched = _provider(FakeSefaria(export=False), delay=0).fetch_book(
        "Genesis", version_title=TANAKH, depth=2
    )
    assert fetched.source == "api"
    assert fetched.text == GENESIS


def test_no_request_ever_asks_for_a_single_verse() -> None:
    """CLAUDE.md non-negotiable 7."""
    fake = FakeSefaria(export=False)
    _provider(fake, delay=0).fetch_book("Genesis", version_title=TANAKH, depth=2)
    assert not any("Genesis.1" in url or "Genesis%201" in url for url in fake.seen)


def test_an_unknown_version_names_the_available_ones() -> None:
    with pytest.raises(ProviderError, match=r"Hebrew versions available.*Miqra"):
        _provider(FakeSefaria(), delay=0).fetch_book("Genesis", version_title="Nope", depth=2)


def test_a_depth_mismatch_is_refused() -> None:
    with pytest.raises(ProviderError, match="depth 2"):
        _provider(FakeSefaria(), delay=0).fetch_book("Genesis", version_title=TANAKH, depth=3)


def test_malformed_text_is_refused() -> None:
    fake = FakeSefaria()
    answer = fake._answer

    def broken(url):
        data = answer(url)
        if url.startswith(EXPORT):
            data["text"] = [[{"not": "a string"}]]
        return data

    fake._answer = broken
    with pytest.raises(ProviderError, match="not a depth-2 nested list"):
        _provider(fake, delay=0).fetch_book("Genesis", version_title=TANAKH, depth=2)


def test_missing_commentary_index_is_not_found() -> None:
    with pytest.raises(NotFound):
        _provider(FakeSefaria(rashi=False), delay=0).get_index("Rashi on Genesis")


# ---- Cache ------------------------------------------------------------------------------


def test_fetch_writes_a_cache_the_local_provider_reads(tmp_path: Path, config, books) -> None:
    outcomes = fetch_book(
        _provider(FakeSefaria(), delay=0), config, books.by_title("Genesis"), cache_dir=tmp_path
    )
    assert [o.status for o in outcomes] == ["fetched", "fetched"]

    text_file = cache_path(tmp_path, "tanakh", "genesis")
    stored = json.loads(text_file.read_text(encoding="utf-8"))
    for key in ("fetched_at", "source", "version_title", "license", "index_lengths"):
        assert stored[key], key
    assert stored["text"] == GENESIS, "the cache holds the text verbatim"

    local = LocalProvider(
        [tmp_path],
        books=books,
        expected_versions={"tanakh": TANAKH, "Rashi": RASHI},
    )
    assert local.get_book_text("Genesis") == GENESIS
    assert local.get_book_commentary("Rashi", "Genesis") == RASHI_GENESIS
    assert local.index_lengths("Genesis") == (50, 1533)
    assert local.text_source("Genesis").license == "CC-BY-SA"


def test_a_cached_book_is_not_fetched_again(tmp_path: Path, config, books) -> None:
    genesis = books.by_title("Genesis")
    fetch_book(_provider(FakeSefaria(), delay=0), config, genesis, cache_dir=tmp_path)
    fake = FakeSefaria()
    outcomes = fetch_book(_provider(fake, delay=0), config, genesis, cache_dir=tmp_path)
    assert [o.status for o in outcomes] == ["cached", "cached"]
    assert not any(url.startswith(EXPORT) for url in fake.seen)


def test_refresh_fetches_again(tmp_path: Path, config, books) -> None:
    genesis = books.by_title("Genesis")
    fetch_book(_provider(FakeSefaria(), delay=0), config, genesis, cache_dir=tmp_path)
    outcomes = fetch_book(
        _provider(FakeSefaria(), delay=0), config, genesis, cache_dir=tmp_path, refresh=True
    )
    assert [o.status for o in outcomes] == ["fetched", "fetched"]


def test_a_cached_file_in_another_version_is_a_miss(tmp_path: Path, config, books) -> None:
    """SPEC_DATA_SOURCE §11 — never mixed silently."""
    path = cache_path(tmp_path, "tanakh", "genesis")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version_title": "Tanach with Nikkud"}), encoding="utf-8")
    outcomes = fetch_book(
        _provider(FakeSefaria(), delay=0), config, books.by_title("Genesis"), cache_dir=tmp_path
    )
    assert outcomes[0].status == "fetched"
    assert "replaced" in outcomes[0].detail
    assert cached_version(path) == TANAKH


def test_a_book_without_commentary_is_reported_not_failed(tmp_path: Path, config, books) -> None:
    outcomes = fetch_book(
        _provider(FakeSefaria(rashi=False), delay=0),
        config,
        books.by_title("Genesis"),
        cache_dir=tmp_path,
    )
    assert [o.status for o in outcomes] == ["fetched", "absent"]
    assert not cache_path(tmp_path, "rashi", "genesis").exists()


def test_a_failed_fetch_leaves_no_partial_file(tmp_path: Path, config, books) -> None:
    fake = FakeSefaria()
    fake.fail["sefaria-export"] = [500] * 10
    fake.fail["/v3/texts/"] = [500] * 10
    outcomes = fetch_book(
        _provider(fake, delay=0, retries=1, backoff=0),
        config,
        books.by_title("Genesis"),
        cache_dir=tmp_path,
    )
    assert outcomes[0].status == "failed"
    assert not cache_path(tmp_path, "tanakh", "genesis").exists()

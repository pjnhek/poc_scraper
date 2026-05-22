"""Unit tests for src/clients/replay.py.

Covers the request-hash function (stability, order-independence), the JSON
round-trip from each recording wrapper to its replay counterpart, the
missing-fixture failure mode (ReplayMissError, not a silent empty result),
and the ReplayLLM role discriminator (writer vs judge subdirectory).

Per CLAUDE.md "Unit tests - call our pure functions directly with crafted
inputs", these tests use tmp_path and never touch fixtures/demo-bundle/.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.clients.browserbase_client import RenderedPage
from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import LLMResponse
from src.clients.replay import (
    RecordingBrowserbase,
    RecordingExa,
    RecordingLLM,
    ReplayBrowserbase,
    ReplayExa,
    ReplayLLM,
    ReplayMissError,
    _canonical_hash,
)

# --- request-hash stability and order-independence -------------------------


def test_canonical_hash_stable_for_same_kwargs() -> None:
    a = _canonical_hash("news", domain="x.com", days=90, num_results=8)
    b = _canonical_hash("news", domain="x.com", days=90, num_results=8)
    assert a == b


def test_canonical_hash_differs_for_different_kwargs() -> None:
    a = _canonical_hash("news", domain="x.com", days=90, num_results=8)
    b = _canonical_hash("news", domain="y.com", days=90, num_results=8)
    assert a != b


def test_canonical_hash_order_independent() -> None:
    a = _canonical_hash("news", domain="x.com", days=90, num_results=8)
    b = _canonical_hash("news", num_results=8, days=90, domain="x.com")
    assert a == b


def test_canonical_hash_method_is_part_of_key() -> None:
    a = _canonical_hash("news", domain="x.com")
    b = _canonical_hash("about", domain="x.com")
    assert a != b


def test_canonical_hash_is_16_hex_chars() -> None:
    h = _canonical_hash("news", domain="x.com")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


# --- ReplayExa round-trip --------------------------------------------------


class _FakeExa:
    """Minimal ExaLike stub used to feed a known result to RecordingExa."""

    def __init__(self, results: list[ExaResult]) -> None:
        self._results = results

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        return self._results

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return self._results


async def test_replay_exa_round_trip_about(tmp_path: Path) -> None:
    rec_payload = [
        ExaResult(
            url="https://x.com/about",
            title="About X",
            snippet="X is a company.",
            published_at=datetime(2026, 1, 15, tzinfo=UTC),
        )
    ]
    recorder = RecordingExa(inner=_FakeExa(rec_payload), bundle_dir=tmp_path)
    written = await recorder.search_about("x.com")
    assert written == rec_payload

    replayer = ReplayExa(tmp_path)
    read_back = await replayer.search_about("x.com")
    assert read_back == rec_payload


async def test_replay_exa_round_trip_news(tmp_path: Path) -> None:
    rec_payload = [
        ExaResult(
            url="https://news.com/a",
            title="Headline A",
            snippet="Snippet A.",
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        ExaResult(
            url="https://news.com/b",
            title=None,
            snippet=None,
            published_at=None,
        ),
    ]
    recorder = RecordingExa(inner=_FakeExa(rec_payload), bundle_dir=tmp_path)
    await recorder.search_news("x.com", days=90, num_results=8)

    replayer = ReplayExa(tmp_path)
    read_back = await replayer.search_news("x.com", days=90, num_results=8)
    assert read_back == rec_payload


async def test_replay_exa_missing_fixture_raises_miss_error(tmp_path: Path) -> None:
    replayer = ReplayExa(tmp_path)
    with pytest.raises(ReplayMissError) as exc_info:
        await replayer.search_about("never-recorded.com")
    msg = str(exc_info.value)
    assert "about" in msg
    assert "never-recorded.com" in msg


# --- ReplayBrowserbase round-trip ------------------------------------------


class _FakeBrowserbase:
    def __init__(self, page: RenderedPage | None) -> None:
        self._page = page

    async def render(self, url: str) -> RenderedPage | None:
        return self._page


async def test_replay_browserbase_round_trip(tmp_path: Path) -> None:
    page = RenderedPage(url="https://x.com/about", html="<p>hi</p>", status_code=200)
    recorder = RecordingBrowserbase(inner=_FakeBrowserbase(page), bundle_dir=tmp_path)
    await recorder.render("https://x.com/about")

    replayer = ReplayBrowserbase(tmp_path)
    read_back = await replayer.render("https://x.com/about")
    assert read_back == page


async def test_replay_browserbase_round_trip_none(tmp_path: Path) -> None:
    recorder = RecordingBrowserbase(inner=_FakeBrowserbase(None), bundle_dir=tmp_path)
    await recorder.render("https://x.com/blocked")

    replayer = ReplayBrowserbase(tmp_path)
    read_back = await replayer.render("https://x.com/blocked")
    assert read_back is None


async def test_replay_browserbase_missing_fixture_raises(tmp_path: Path) -> None:
    replayer = ReplayBrowserbase(tmp_path)
    with pytest.raises(ReplayMissError) as exc_info:
        await replayer.render("https://never.com/")
    assert "render" in str(exc_info.value)


# --- ReplayLLM round-trip and role discriminator ---------------------------


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text

    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(text=self._text)


async def test_replay_llm_round_trip_writer(tmp_path: Path) -> None:
    recorder = RecordingLLM(inner=_FakeLLM("writer-text"), bundle_dir=tmp_path, role="writer")
    await recorder.synthesize("sys", "ctx", "user")

    replayer = ReplayLLM(tmp_path, role="writer")
    response = await replayer.synthesize("sys", "ctx", "user")
    assert response.text == "writer-text"


async def test_replay_llm_role_discriminator_separates_writer_from_judge(
    tmp_path: Path,
) -> None:
    """ReplayLLM(role="writer") and ReplayLLM(role="judge") must use distinct
    subdirectories so the same (system, context, user_prompt) tuple can produce
    different responses for writer vs judge."""
    rec_writer = RecordingLLM(inner=_FakeLLM("writer-only"), bundle_dir=tmp_path, role="writer")
    rec_judge = RecordingLLM(inner=_FakeLLM("judge-only"), bundle_dir=tmp_path, role="judge")
    await rec_writer.synthesize("sys", "ctx", "user")
    await rec_judge.synthesize("sys", "ctx", "user")

    writer = ReplayLLM(tmp_path, role="writer")
    judge = ReplayLLM(tmp_path, role="judge")
    assert (await writer.synthesize("sys", "ctx", "user")).text == "writer-only"
    assert (await judge.synthesize("sys", "ctx", "user")).text == "judge-only"


async def test_replay_llm_missing_fixture_raises(tmp_path: Path) -> None:
    replayer = ReplayLLM(tmp_path, role="writer")
    with pytest.raises(ReplayMissError) as exc_info:
        await replayer.synthesize("sys", "ctx", "user")
    msg = str(exc_info.value)
    assert "synthesize" in msg
    assert "writer" in msg


async def test_replay_llm_max_tokens_is_part_of_key(tmp_path: Path) -> None:
    """max_tokens=None vs max_tokens=512 must produce distinct fixtures so the
    same prompt with different token caps does not collide on the same file."""
    rec = RecordingLLM(inner=_FakeLLM("default"), bundle_dir=tmp_path, role="writer")
    rec_capped = RecordingLLM(inner=_FakeLLM("capped"), bundle_dir=tmp_path, role="writer")
    await rec.synthesize("sys", "ctx", "user")
    await rec_capped.synthesize("sys", "ctx", "user", max_tokens=512)

    replayer = ReplayLLM(tmp_path, role="writer")
    default = await replayer.synthesize("sys", "ctx", "user")
    capped = await replayer.synthesize("sys", "ctx", "user", max_tokens=512)
    assert default.text == "default"
    assert capped.text == "capped"


# --- Recording wrappers also satisfy the Protocols structurally ------------


async def test_recording_exa_returns_inner_result_unchanged(tmp_path: Path) -> None:
    payload = [ExaResult(url="https://x.com/about", title="t", snippet="s", published_at=None)]
    recorder = RecordingExa(inner=_FakeExa(payload), bundle_dir=tmp_path)
    out = await recorder.search_about("x.com")
    # The wrapper must return the inner result unchanged; teeing to disk is a
    # side-effect, not a substitution.
    assert out == payload


async def test_recording_creates_subdirectory(tmp_path: Path) -> None:
    """Recording wrappers should not fail when the bundle subdirectory does
    not exist yet; they create it lazily."""
    bundle = tmp_path / "fresh"
    assert not bundle.exists()
    recorder = RecordingExa(inner=_FakeExa([]), bundle_dir=bundle)
    await recorder.search_about("x.com")
    assert (bundle / "exa").is_dir()

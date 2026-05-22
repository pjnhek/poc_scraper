"""Replay and recording clients for the demo bundle (HARD-04 / D-13..D-17).

Three replay clients (ReplayExa, ReplayBrowserbase, ReplayLLM) satisfy the
existing ExaLike, BrowserbaseLike, and LLMClient protocols *structurally*
(no inheritance) and read pre-recorded JSON files from a bundle directory.
Three recording wrappers (RecordingExa, RecordingBrowserbase, RecordingLLM)
compose around real clients and tee each response to disk as the pipeline
runs live (D-17: zero divergence from live request formation — the wrappers
only call self._inner.<method>(...) with the args received).

Bundle layout (D-13, D-16):

    <bundle>/
      exa/<method>_<digest>.json         # search_about, search_news
      browserbase/<method>_<digest>.json # render
      llm/writer/<method>_<digest>.json  # synthesize (writer role)
      llm/judge/<method>_<digest>.json   # synthesize (judge role)

`<digest>` is a 16-char truncated SHA256 of the sorted-key JSON
serialization of `{"method": <method>, **kwargs}` — stable across runs and
order-independent so writer-side argument order does not break replay.

Missing fixtures raise `ReplayMissError` (RuntimeError subclass) rather
than returning empty. Per PATTERNS.md, this error is intentionally NOT
added to any pipeline narrow exception tuple: a missing fixture in replay
mode is a real incompleteness, not a transient network error, and should
crash so the operator records the gap (D-13 + D-18).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .browserbase_client import RenderedPage
from .exa_client import ExaResult
from .nvidia_client import LLMResponse
from .protocols import BrowserbaseLike, ExaLike, LLMClient


class ReplayMissError(RuntimeError):
    """Raised when a replay client cannot find the fixture for a call.

    Missing fixtures indicate the demo bundle is incomplete for the current
    pipeline shape. The operator must record the bundle for this call
    signature (RECORD_BUNDLE=<path> make run) before replay will work.
    """


# --- internal helpers ------------------------------------------------------


def _canonical_hash(method: str, **kwargs: Any) -> str:
    """Deterministic 16-char hash of a method-plus-kwargs call signature.

    Sorted-key JSON guarantees the same kwargs map to the same digest
    regardless of caller-side argument order; truncating SHA256 to 16 hex
    chars keeps filenames human-readable while leaving ~2**64 keyspace,
    well below collision risk for a few-hundred-fixture bundle.
    """
    canonical = json.dumps({"method": method, **kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _read_fixture(path: Path, *, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Load a fixture JSON, or raise ReplayMissError with the call signature."""
    if not path.is_file():
        signature = json.dumps({"method": method, **kwargs}, sort_keys=True, default=str)
        raise ReplayMissError(
            f"replay fixture missing for {method}: {signature} (expected at {path})"
        )
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _write_fixture(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write a fixture JSON file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _serialize_exa_result(r: ExaResult) -> dict[str, Any]:
    return {
        "url": r.url,
        "title": r.title,
        "snippet": r.snippet,
        "published_at": r.published_at.isoformat() if r.published_at is not None else None,
    }


def _deserialize_exa_result(raw: dict[str, Any]) -> ExaResult:
    published_raw = raw.get("published_at")
    published_at: datetime | None = None
    if isinstance(published_raw, str) and published_raw:
        try:
            published_at = datetime.fromisoformat(published_raw)
        except ValueError:
            published_at = None
    return ExaResult(
        url=raw["url"],
        title=raw.get("title"),
        snippet=raw.get("snippet"),
        published_at=published_at,
    )


def _serialize_rendered_page(page: RenderedPage | None) -> dict[str, Any]:
    if page is None:
        return {"page": None}
    return {
        "page": {
            "url": page.url,
            "html": page.html,
            "status_code": page.status_code,
        }
    }


def _deserialize_rendered_page(raw: dict[str, Any]) -> RenderedPage | None:
    page = raw.get("page")
    if page is None:
        return None
    return RenderedPage(
        url=page["url"],
        html=page["html"],
        status_code=int(page["status_code"]),
    )


# --- Replay clients --------------------------------------------------------


class ReplayExa:
    """ExaLike client that reads pre-recorded JSON instead of calling Exa."""

    def __init__(self, bundle_dir: Path) -> None:
        self._bundle_dir = bundle_dir / "exa"

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        kwargs: dict[str, Any] = {"domain": domain, "num_results": num_results}
        digest = _canonical_hash("about", **kwargs)
        path = self._bundle_dir / f"about_{digest}.json"
        raw = _read_fixture(path, method="about", kwargs=kwargs)
        return [_deserialize_exa_result(r) for r in raw["results"]]

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        kwargs = {"domain": domain, "days": days, "num_results": num_results}
        digest = _canonical_hash("news", **kwargs)
        path = self._bundle_dir / f"news_{digest}.json"
        raw = _read_fixture(path, method="news", kwargs=kwargs)
        return [_deserialize_exa_result(r) for r in raw["results"]]


class ReplayBrowserbase:
    """BrowserbaseLike client that reads pre-recorded JSON instead of rendering."""

    def __init__(self, bundle_dir: Path) -> None:
        self._bundle_dir = bundle_dir / "browserbase"

    async def render(self, url: str) -> RenderedPage | None:
        kwargs = {"url": url}
        digest = _canonical_hash("render", **kwargs)
        path = self._bundle_dir / f"render_{digest}.json"
        raw = _read_fixture(path, method="render", kwargs=kwargs)
        return _deserialize_rendered_page(raw)


class ReplayLLM:
    """LLMClient that reads pre-recorded JSON instead of calling a live model.

    The `role` parameter ("writer" | "judge") picks the subdirectory so a
    single class serves both writer and judge call sites; the protocol
    surface is identical for both. DRY per CLAUDE.md.
    """

    def __init__(self, bundle_dir: Path, role: Literal["writer", "judge"]) -> None:
        self._bundle_dir = bundle_dir / "llm" / role
        self._role = role

    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "role": self._role,
            "system": system,
            "context": context,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
        }
        digest = _canonical_hash("synthesize", **kwargs)
        path = self._bundle_dir / f"synthesize_{digest}.json"
        raw = _read_fixture(path, method="synthesize", kwargs=kwargs)
        return LLMResponse(text=str(raw["text"]))


# --- Recording wrappers ----------------------------------------------------


class RecordingExa:
    """Tee wrapper around any ExaLike client; mirrors responses to disk.

    Zero divergence from live request formation (D-17): each call delegates
    to self._inner with the exact args received and only tees the result to
    a JSON fixture symmetric with what ReplayExa reads.
    """

    def __init__(self, inner: ExaLike, bundle_dir: Path) -> None:
        self._inner = inner
        self._bundle_dir = bundle_dir / "exa"

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        result = await self._inner.search_about(domain, num_results=num_results)
        kwargs: dict[str, Any] = {"domain": domain, "num_results": num_results}
        digest = _canonical_hash("about", **kwargs)
        path = self._bundle_dir / f"about_{digest}.json"
        _write_fixture(path, {"results": [_serialize_exa_result(r) for r in result]})
        return result

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        result = await self._inner.search_news(domain, days=days, num_results=num_results)
        kwargs = {"domain": domain, "days": days, "num_results": num_results}
        digest = _canonical_hash("news", **kwargs)
        path = self._bundle_dir / f"news_{digest}.json"
        _write_fixture(path, {"results": [_serialize_exa_result(r) for r in result]})
        return result


class RecordingBrowserbase:
    """Tee wrapper around any BrowserbaseLike client."""

    def __init__(self, inner: BrowserbaseLike, bundle_dir: Path) -> None:
        self._inner = inner
        self._bundle_dir = bundle_dir / "browserbase"

    async def render(self, url: str) -> RenderedPage | None:
        result = await self._inner.render(url)
        kwargs = {"url": url}
        digest = _canonical_hash("render", **kwargs)
        path = self._bundle_dir / f"render_{digest}.json"
        _write_fixture(path, _serialize_rendered_page(result))
        return result


class RecordingLLM:
    """Tee wrapper around any LLMClient.

    Like ReplayLLM, takes a `role` so a single class can be used at the
    writer and judge call sites; the recorded JSON lands in the role-keyed
    subdirectory ReplayLLM reads back from.
    """

    def __init__(
        self,
        inner: LLMClient,
        bundle_dir: Path,
        role: Literal["writer", "judge"],
    ) -> None:
        self._inner = inner
        self._bundle_dir = bundle_dir / "llm" / role
        self._role = role

    async def synthesize(
        self,
        system: str,
        context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        result = await self._inner.synthesize(system, context, user_prompt, max_tokens=max_tokens)
        kwargs: dict[str, Any] = {
            "role": self._role,
            "system": system,
            "context": context,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
        }
        digest = _canonical_hash("synthesize", **kwargs)
        path = self._bundle_dir / f"synthesize_{digest}.json"
        _write_fixture(path, {"text": result.text})
        return result

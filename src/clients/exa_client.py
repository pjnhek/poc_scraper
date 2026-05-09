from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

EXA_BASE_URL = "https://api.exa.ai"


@dataclass(frozen=True)
class ExaResult:
    url: str
    title: str | None
    snippet: str | None
    published_at: datetime | None


class ExaClient:
    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> ExaClient:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        start = datetime.now(UTC) - timedelta(days=days)
        payload = {
            "query": f"{domain} company news funding hiring product launch",
            "type": "neural",
            "numResults": num_results,
            "startPublishedDate": start.strftime("%Y-%m-%d"),
            "contents": {"text": {"maxCharacters": 1500}},
        }
        return await self._search(payload)

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        payload = {
            "query": f"about {domain} company overview industry employees products",
            "type": "neural",
            "numResults": num_results,
            "includeDomains": [domain],
            "contents": {"text": {"maxCharacters": 2000}},
        }
        return await self._search(payload)

    async def _search(self, payload: dict[str, Any]) -> list[ExaResult]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=1, max=15),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.post(
                    f"{EXA_BASE_URL}/search",
                    headers={
                        "x-api-key": self._api_key,
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
        data = resp.json()
        return [_to_result(r) for r in data.get("results", [])]


def _to_result(r: dict[str, Any]) -> ExaResult:
    published_at: datetime | None = None
    raw = r.get("publishedDate")
    if isinstance(raw, str) and raw:
        try:
            published_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = None
    return ExaResult(
        url=r["url"],
        title=r.get("title"),
        snippet=(r.get("text") or r.get("snippet") or "").strip() or None,
        published_at=published_at,
    )

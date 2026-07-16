from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .retry import retry_after_aware_wait

BROWSERBASE_BASE_URL = "https://api.browserbase.com/v1"

log = logging.getLogger(__name__)


class BrowserbaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderedPage:
    url: str
    html: str
    status_code: int


class BrowserbaseClient:
    def __init__(
        self,
        api_key: str,
        project_id: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._project_id = project_id
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> BrowserbaseClient:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def render(self, url: str) -> RenderedPage | None:
        try:
            return await self._render_with_retry(url)
        except (httpx.HTTPError, BrowserbaseError) as exc:
            log.warning("browserbase render failed [%s] for %s: %s", type(exc).__name__, url, exc)
            return None

    async def _render_with_retry(self, url: str) -> RenderedPage:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=retry_after_aware_wait(fallback=wait_exponential(multiplier=1, min=1, max=8)),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.post(
                    f"{BROWSERBASE_BASE_URL}/scrape",
                    headers={
                        "x-bb-api-key": self._api_key,
                        "content-type": "application/json",
                    },
                    json={"projectId": self._project_id, "url": url, "format": "html"},
                )
                resp.raise_for_status()
        data = resp.json()
        html = data.get("html") or data.get("content") or ""
        if not html:
            raise BrowserbaseError(f"empty rendered content for {url}")
        return RenderedPage(url=url, html=html, status_code=resp.status_code)


class NullBrowserbase:
    """No-op BrowserbaseLike client: renders nothing, satisfies the protocol structurally.

    Deliberately deviates from the design spec (D-07): render() always returns
    None rather than raising BrowserbaseError. The catch-and-continue path for
    a blocked/disabled render lives inside BrowserbaseClient.render's own
    try/except, not in collect_context. A raising null object would propagate
    into process_account's enrich except clause and mark the whole account
    unscoreable, the opposite of the intended Exa-only continue.
    """

    async def render(self, url: str) -> RenderedPage | None:
        log.info("browserbase disabled: skipping render for %s", url)
        return None

from __future__ import annotations

import httpx
import pytest
import respx

from src.clients.exa_client import EXA_BASE_URL, ExaClient


@pytest.mark.asyncio
async def test_search_news_parses_results() -> None:
    body = {
        "results": [
            {
                "url": "https://techcrunch.com/2026/05/notion-funding",
                "title": "Notion raises $200M",
                "text": "Notion announced a $200M Series D today.",
                "publishedDate": "2026-04-12T10:00:00Z",
            },
        ]
    }
    async with respx.mock(base_url=EXA_BASE_URL) as router:
        router.post("/search").respond(200, json=body)
        async with httpx.AsyncClient() as http:
            client = ExaClient(api_key="k", client=http)
            results = await client.search_news("notion.so", days=90)

    assert len(results) == 1
    r = results[0]
    assert r.url.startswith("https://")
    assert r.title and "Notion" in r.title
    assert r.snippet and "Series D" in r.snippet
    assert r.published_at is not None and r.published_at.year == 2026


@pytest.mark.asyncio
async def test_search_about_sends_include_domains() -> None:
    captured = {}

    def _inspect(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read()
        return httpx.Response(200, json={"results": []})

    async with respx.mock(base_url=EXA_BASE_URL) as router:
        router.post("/search").mock(side_effect=_inspect)
        async with httpx.AsyncClient() as http:
            client = ExaClient(api_key="k", client=http)
            await client.search_about("notion.so")

    body = captured["payload"].decode()
    assert "includeDomains" in body
    assert "notion.so" in body


@pytest.mark.asyncio
async def test_search_retries_then_succeeds() -> None:
    async with respx.mock(base_url=EXA_BASE_URL) as router:
        route = router.post("/search").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"results": []}),
            ]
        )
        async with httpx.AsyncClient() as http:
            client = ExaClient(api_key="k", client=http)
            results = await client.search_news("x.com")
    assert results == []
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_search_gives_up_after_max_attempts() -> None:
    async with respx.mock(base_url=EXA_BASE_URL) as router:
        router.post("/search").respond(500)
        async with httpx.AsyncClient() as http:
            client = ExaClient(api_key="k", client=http)
            with pytest.raises(httpx.HTTPError):
                await client.search_news("x.com")


@pytest.mark.asyncio
async def test_search_honors_retry_after_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    # D-05 + D-08: when the server returns 429 with Retry-After: <seconds>, the
    # client must sleep exactly that many seconds before retrying. Patching
    # asyncio.sleep intercepts tenacity's _portable_async_sleep, which does a
    # fresh `asyncio.sleep(seconds)` lookup on every call.
    sleeps: list[float] = []

    async def _capture_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", _capture_sleep)

    async with respx.mock(base_url=EXA_BASE_URL) as router:
        route = router.post("/search").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "2"}),
                httpx.Response(200, json={"results": []}),
            ]
        )
        async with httpx.AsyncClient() as http:
            client = ExaClient(api_key="k", client=http)
            results = await client.search_news("x.com")

    assert results == []
    assert route.call_count == 2
    assert 2.0 in sleeps


@pytest.mark.asyncio
async def test_handles_missing_published_date() -> None:
    body = {"results": [{"url": "https://x.com/a", "title": "t", "text": "s"}]}
    async with respx.mock(base_url=EXA_BASE_URL) as router:
        router.post("/search").respond(200, json=body)
        async with httpx.AsyncClient() as http:
            client = ExaClient(api_key="k", client=http)
            results = await client.search_news("x.com")
    assert results[0].published_at is None

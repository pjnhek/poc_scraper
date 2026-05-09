from __future__ import annotations

import httpx
import pytest
import respx

from src.clients.browserbase_client import BROWSERBASE_BASE_URL, BrowserbaseClient


@pytest.mark.asyncio
async def test_render_returns_page_on_success() -> None:
    async with respx.mock(base_url=BROWSERBASE_BASE_URL) as router:
        router.post("/scrape").respond(200, json={"html": "<html>ok</html>"})
        async with httpx.AsyncClient() as http:
            client = BrowserbaseClient(api_key="k", project_id="p", client=http)
            page = await client.render("https://x.com/about")
    assert page is not None
    assert page.html == "<html>ok</html>"
    assert page.url == "https://x.com/about"


@pytest.mark.asyncio
async def test_render_returns_none_when_blocked() -> None:
    async with respx.mock(base_url=BROWSERBASE_BASE_URL) as router:
        router.post("/scrape").respond(403)
        async with httpx.AsyncClient() as http:
            client = BrowserbaseClient(api_key="k", project_id="p", client=http)
            page = await client.render("https://blocked.example/about")
    assert page is None


@pytest.mark.asyncio
async def test_render_returns_none_when_empty_content() -> None:
    async with respx.mock(base_url=BROWSERBASE_BASE_URL) as router:
        router.post("/scrape").respond(200, json={"html": ""})
        async with httpx.AsyncClient() as http:
            client = BrowserbaseClient(api_key="k", project_id="p", client=http)
            page = await client.render("https://x.com/about")
    assert page is None


@pytest.mark.asyncio
async def test_render_retries_once_then_succeeds() -> None:
    async with respx.mock(base_url=BROWSERBASE_BASE_URL) as router:
        route = router.post("/scrape").mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(200, json={"html": "<html>ok</html>"}),
            ]
        )
        async with httpx.AsyncClient() as http:
            client = BrowserbaseClient(api_key="k", project_id="p", client=http)
            page = await client.render("https://x.com/about")
    assert page is not None
    assert route.call_count == 2

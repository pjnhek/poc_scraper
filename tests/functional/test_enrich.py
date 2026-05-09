from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.clients.browserbase_client import RenderedPage
from src.clients.exa_client import ExaResult
from src.clients.nvidia_client import CachedSynthesis
from src.enrich import Enricher
from src.models import Account


class FakeExa:
    def __init__(
        self,
        about: list[ExaResult] | None = None,
        news: list[ExaResult] | None = None,
    ) -> None:
        self.about = about or []
        self.news = news or []
        self.calls: list[str] = []

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        self.calls.append(f"about:{domain}")
        return self.about

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        self.calls.append(f"news:{domain}")
        return self.news


class FakeBrowserbase:
    def __init__(self, page: RenderedPage | None = None) -> None:
        self.page = page
        self.calls: list[str] = []

    async def render(self, url: str) -> RenderedPage | None:
        self.calls.append(url)
        return self.page


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, str]] = []

    async def synthesize(
        self,
        system: str,
        cached_context: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> CachedSynthesis:
        self.calls.append({"system": system, "context": cached_context, "user": user_prompt})
        return CachedSynthesis(text=self.text, cache_read_tokens=0, cache_creation_tokens=0)


def _exa_about(text: str = "Notion is a workspace tool. " * 30) -> ExaResult:
    return ExaResult(
        url="https://notion.so/about",
        title="About Notion",
        snippet=text,
        published_at=None,
    )


def _exa_news(url: str = "https://techcrunch.com/notion") -> ExaResult:
    return ExaResult(
        url=url,
        title="Notion launches AI",
        snippet="Notion shipped a new AI feature today.",
        published_at=datetime(2026, 4, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_happy_path_full_enrichment() -> None:
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    bb = FakeBrowserbase()
    llm = FakeAnthropic(
        text='{"name":"Notion","industry":"productivity","headcount_range":"500-1000","tech_signals":["react","postgres"]}'
    )
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="notion.so"))

    assert enr.firmographics is not None
    assert enr.firmographics.name == "Notion"
    assert enr.firmographics.industry == "productivity"
    assert enr.firmographics.headcount_range == "500-1000"
    assert enr.firmographics.tech_signals == ("react", "postgres")
    assert len(enr.news) == 1
    assert enr.news[0].headline == "Notion launches AI"
    assert bb.calls == []  # didn't need fallback


@pytest.mark.asyncio
async def test_browserbase_fallback_when_about_text_thin() -> None:
    exa = FakeExa(about=[_exa_about(text="short")], news=[])
    bb = FakeBrowserbase(
        page=RenderedPage(
            url="https://notion.so/about",
            html="<html><body>"
            + "Notion is a comprehensive workspace platform. " * 30
            + "</body></html>",
            status_code=200,
        )
    )
    llm = FakeAnthropic(
        text='{"name":"Notion","industry":null,"headcount_range":null,"tech_signals":[]}'
    )
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="notion.so"))

    assert bb.calls == ["https://notion.so/about"]
    assert enr.firmographics is not None
    assert enr.firmographics.name == "Notion"
    cite_sources = {c.source for c in enr.firmographics.citations}
    assert "browserbase" in cite_sources or "exa" in cite_sources


@pytest.mark.asyncio
async def test_browserbase_blocked_falls_back_to_exa_text() -> None:
    exa = FakeExa(about=[_exa_about(text="short")], news=[])
    bb = FakeBrowserbase(page=None)
    llm = FakeAnthropic(
        text='{"name":"x","industry":null,"headcount_range":null,"tech_signals":[]}'
    )
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="x.com"))
    assert bb.calls == ["https://notion.so/about"]
    assert enr.firmographics is not None


@pytest.mark.asyncio
async def test_empty_enrichment_when_no_data() -> None:
    exa = FakeExa(about=[], news=[])
    bb = FakeBrowserbase()
    llm = FakeAnthropic(text="{}")
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="dead.example"))
    assert enr.is_empty is True
    assert enr.firmographics is None
    assert llm.calls == []  # we don't call LLM with no context


@pytest.mark.asyncio
async def test_malformed_llm_json_returns_none_firmographics() -> None:
    exa = FakeExa(about=[_exa_about()], news=[])
    bb = FakeBrowserbase()
    llm = FakeAnthropic(text="sorry I cannot help")
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="notion.so"))
    assert enr.firmographics is None


@pytest.mark.asyncio
async def test_handles_json_wrapped_in_code_fences() -> None:
    exa = FakeExa(about=[_exa_about()], news=[])
    bb = FakeBrowserbase()
    llm = FakeAnthropic(
        text='```json\n{"name":"Notion","industry":"productivity","headcount_range":null,"tech_signals":[]}\n```'
    )
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="notion.so"))
    assert enr.firmographics is not None
    assert enr.firmographics.name == "Notion"


@pytest.mark.asyncio
async def test_news_only_no_about_still_returns_news() -> None:
    exa = FakeExa(about=[], news=[_exa_news()])
    bb = FakeBrowserbase()
    llm = FakeAnthropic(text="{}")
    enricher = Enricher(exa, bb, llm)

    enr = await enricher.enrich(Account(domain="x.com"))
    assert enr.is_empty is False
    assert enr.firmographics is None
    assert len(enr.news) == 1

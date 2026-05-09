from __future__ import annotations

import pytest

from src.clients.nvidia_client import LLMResponse
from src.models import Account, Citation, Contact, Enrichment, Firmographics, NewsItem
from src.outreach import OutreachGenerator


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens=None
    ) -> LLMResponse:
        return LLMResponse(text=self.text)


def _enr_with_news(*urls: str) -> Enrichment:
    items = []
    for i, u in enumerate(urls):
        items.append(
            NewsItem(
                headline=f"news {i}",
                summary=f"summary for news {i}",
                citation=Citation.make(url=u, source="exa"),
            )
        )
    return Enrichment(
        account=Account(domain="chime.com"),
        firmographics=Firmographics(name="Chime", industry="fintech"),
        news=tuple(items),
    )


def _contact() -> Contact:
    return Contact(role_title="VP CX", rationale="owns deflection")


@pytest.mark.asyncio
async def test_happy_path_with_valid_citations() -> None:
    enr = _enr_with_news("https://tc.com/chime-1", "https://tc.com/chime-2")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Saw your AI-support push [news 0](https://tc.com/chime-1). '
            'We help teams hit higher deflection.","cited_urls":["https://tc.com/chime-1"]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert "AI-support" in hook.paragraph
    assert len(hook.citations) == 1
    assert str(hook.citations[0].url) == "https://tc.com/chime-1"


@pytest.mark.asyncio
async def test_drops_uncited_url_from_paragraph() -> None:
    enr = _enr_with_news("https://tc.com/chime-1")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Saw [a](https://tc.com/chime-1) and [b](https://hallucinated.com/x).",'
            '"cited_urls":["https://tc.com/chime-1","https://hallucinated.com/x"]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert "hallucinated.com" not in hook.paragraph
    assert "tc.com/chime-1" in hook.paragraph
    assert len(hook.citations) == 1


@pytest.mark.asyncio
async def test_returns_empty_when_no_valid_citations() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(
        text='{"paragraph":"Made up claim [x](https://fake.com/x).","cited_urls":["https://fake.com/x"]}'
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert hook.paragraph == ""
    assert hook.citations == ()


@pytest.mark.asyncio
async def test_handles_malformed_json() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(text="not json")
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert hook.paragraph == ""
    assert hook.citations == ()


@pytest.mark.asyncio
async def test_strips_bare_url_not_in_markdown_link() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Saw [a](https://real.com/news) and also visit '
            'https://hallucinated.example for context.",'
            '"cited_urls":["https://real.com/news"]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert "hallucinated.example" not in hook.paragraph
    assert "real.com/news" in hook.paragraph


@pytest.mark.asyncio
async def test_keeps_bare_url_when_it_is_a_valid_citation() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Source: https://real.com/news shows the trend.",'
            '"cited_urls":["https://real.com/news"]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert "real.com/news" in hook.paragraph


@pytest.mark.asyncio
async def test_canonicalizes_trailing_slash_when_matching() -> None:
    enr = _enr_with_news("https://tc.com/chime-1")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"[a](https://tc.com/chime-1/).",'
            '"cited_urls":["https://tc.com/chime-1/"]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert len(hook.citations) == 1

from __future__ import annotations

import pytest

from src.clients.nvidia_client import LLMResponse
from src.models import (
    Account,
    Citation,
    Contact,
    Enrichment,
    Firmographics,
    Justification,
    NewsItem,
)
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
    justifications = []
    for i, u in enumerate(urls):
        cite = Citation.make(url=u, source="exa", snippet=f"snippet {i}")
        items.append(
            NewsItem(
                headline=f"news {i}",
                summary=f"summary for news {i}",
                citation=cite,
            )
        )
        justifications.append(
            Justification(index=i + 1, summary=f"news {i}: summary for news {i}", citation=cite)
        )
    return Enrichment(
        account=Account(domain="chime.com"),
        firmographics=Firmographics(name="Chime", industry="fintech"),
        news=tuple(items),
        justifications=tuple(justifications),
    )


def _contact() -> Contact:
    return Contact(role_title="VP CX", rationale="owns deflection")


@pytest.mark.asyncio
async def test_happy_path_with_valid_index_marker() -> None:
    enr = _enr_with_news("https://tc.com/chime-1", "https://tc.com/chime-2")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Saw your AI-support push [1]. We help teams hit higher '
            'deflection.","cited_justifications":[1]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert "AI-support" in hook.paragraph
    assert "[1]" in hook.paragraph
    assert hook.cited_indices == (1,)


@pytest.mark.asyncio
async def test_drops_indices_not_marked_in_paragraph() -> None:
    enr = _enr_with_news("https://tc.com/chime-1", "https://tc.com/chime-2")
    llm = FakeAnthropic(
        text=('{"paragraph":"Saw [1]. We can help.",' '"cited_justifications":[1, 2]}')
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    # Writer claimed [1, 2] but only [1] appears in paragraph.
    assert hook.cited_indices == (1,)


@pytest.mark.asyncio
async def test_drops_unknown_index() -> None:
    enr = _enr_with_news("https://tc.com/chime-1")
    llm = FakeAnthropic(
        text=('{"paragraph":"Saw [99]. We can help.",' '"cited_justifications":[99]}')
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    # 99 isn't a valid justification index, so this hook is dropped.
    assert hook.paragraph == ""
    assert hook.cited_indices == ()


@pytest.mark.asyncio
async def test_returns_empty_when_no_valid_markers() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(
        text='{"paragraph":"Generic claim with no markers.","cited_justifications":[1]}'
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert hook.paragraph == ""
    assert hook.cited_indices == ()


@pytest.mark.asyncio
async def test_handles_malformed_json() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(text="not json")
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert hook.paragraph == ""
    assert hook.cited_indices == ()


@pytest.mark.asyncio
async def test_strips_raw_urls_from_paragraph() -> None:
    enr = _enr_with_news("https://real.com/news")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Saw your push [1]. Visit https://real.com/news for more.",'
            '"cited_justifications":[1]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert "https://" not in hook.paragraph
    assert "[1]" in hook.paragraph


@pytest.mark.asyncio
async def test_supports_multi_index_marker() -> None:
    enr = _enr_with_news("https://a.com/x", "https://b.com/y")
    llm = FakeAnthropic(
        text=(
            '{"paragraph":"Saw two recent pushes [1, 2]. We can help.",'
            '"cited_justifications":[1, 2]}'
        )
    )
    hook = await OutreachGenerator(llm).generate(_contact(), enr, score=None)
    assert hook.cited_indices == (1, 2)

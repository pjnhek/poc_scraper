from __future__ import annotations

import pytest

from src.clients.nvidia_client import LLMResponse
from src.contacts import ContactExtractor
from src.models import Account, Citation, Enrichment, NewsItem


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens=None
    ) -> LLMResponse:
        return LLMResponse(text=self.text)


def _enr() -> Enrichment:
    return Enrichment(
        account=Account(domain="exampleapp.com"),
        news=(
            NewsItem(
                headline="ExampleApp adds AI",
                summary="...",
                citation=Citation.make(url="https://example.com/a", source="exa"),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_returns_three_contacts_from_array() -> None:
    llm = FakeAnthropic(text="""[
            {"role_title":"VP CX","rationale":"owns CSAT"},
            {"role_title":"Head of Support","rationale":"owns deflection"},
            {"role_title":"Director CX Auto","rationale":"runs RFPs"}
        ]""")
    contacts = await ContactExtractor(llm).extract(_enr(), score=None)
    assert len(contacts) == 3
    assert contacts[0].role_title == "VP CX"
    assert contacts[2].rationale == "runs RFPs"


@pytest.mark.asyncio
async def test_pads_when_fewer_than_three_returned() -> None:
    llm = FakeAnthropic(text='[{"role_title":"VP CX","rationale":"r"}]')
    contacts = await ContactExtractor(llm).extract(_enr(), score=None)
    assert len(contacts) == 3
    assert contacts[0].role_title == "VP CX"
    assert "(no rationale" in contacts[1].rationale


@pytest.mark.asyncio
async def test_truncates_when_more_than_three_returned() -> None:
    llm = FakeAnthropic(text="""[
            {"role_title":"a","rationale":"r"},
            {"role_title":"b","rationale":"r"},
            {"role_title":"c","rationale":"r"},
            {"role_title":"d","rationale":"r"}
        ]""")
    contacts = await ContactExtractor(llm).extract(_enr(), score=None)
    assert len(contacts) == 3
    assert [c.role_title for c in contacts] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_falls_back_to_defaults_on_garbage() -> None:
    llm = FakeAnthropic(text="not json")
    contacts = await ContactExtractor(llm).extract(_enr(), score=None)
    assert len(contacts) == 3
    assert all(c.rationale == "(no rationale provided)" for c in contacts)


@pytest.mark.asyncio
async def test_handles_object_wrapped_array() -> None:
    llm = FakeAnthropic(
        text='{"contacts":[{"role_title":"VP CX","rationale":"r"},{"role_title":"H","rationale":"r"},{"role_title":"D","rationale":"r"}]}'
    )
    contacts = await ContactExtractor(llm).extract(_enr(), score=None)
    assert len(contacts) == 3
    assert contacts[0].role_title == "VP CX"

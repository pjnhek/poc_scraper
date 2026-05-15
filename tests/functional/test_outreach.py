from __future__ import annotations

import pytest

from src.clients.nvidia_client import LLMResponse
from src.icp_config import ICPConfig, load_config
from src.models import (
    Account,
    Citation,
    Contact,
    Enrichment,
    Firmographics,
    Justification,
)
from src.outreach import OutreachGenerator


class FakeAnthropic:
    def __init__(self, text: str) -> None:
        self.text = text

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        return LLMResponse(text=self.text)


def _justification(index: int, summary: str, url: str = "") -> Justification:
    cite = Citation.make(url=url or f"https://example.com/{index}", source="exa")
    return Justification(index=index, summary=summary, citation=cite)


def _enr(justifications: list[Justification]) -> Enrichment:
    return Enrichment(
        account=Account(domain="chime.com"),
        firmographics=Firmographics(name="Chime", industry="fintech"),
        news=(),
        justifications=tuple(justifications),
    )


def _contact() -> Contact:
    return Contact(role_title="VP CX", rationale="owns deflection")


def _config() -> ICPConfig:
    return load_config()


@pytest.mark.asyncio
async def test_happy_path_grounded_claim() -> None:
    """A grounded claim that overlaps its cited evidence survives assembly."""
    j1 = _justification(1, "Chime expanded its AI support automation program in 2024")
    enr = _enr([j1])
    llm = FakeAnthropic(
        text=(
            '{"claims": [{"claim": "Chime expanded AI support automation", "cited_indices": [1]}], '
            '"connective_text": "We help teams hit higher deflection."}'
        )
    )
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)
    assert "Chime expanded AI support automation" in hook.paragraph
    assert hook.cited_indices == (1,)


@pytest.mark.asyncio
async def test_drops_claim_with_unknown_index() -> None:
    """A claim citing a non-existent justification index is suppressed."""
    j1 = _justification(1, "Chime expanded its AI support automation program")
    enr = _enr([j1])
    llm = FakeAnthropic(
        text=(
            '{"claims": [{"claim": "Chime expanded AI support automation", "cited_indices": [99]}], '
            '"connective_text": ""}'
        )
    )
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)
    # Index 99 is not a valid justification, so coverage fails -> empty hook.
    assert hook.paragraph == ""
    assert hook.cited_indices == ()


@pytest.mark.asyncio
async def test_returns_empty_when_all_claims_fail_coverage() -> None:
    """When all claims fail the rapidfuzz coverage gate, an empty hook is returned."""
    j1 = _justification(1, "Chime news: their support team won an award")
    enr = _enr([j1])
    llm = FakeAnthropic(
        text=(
            '{"claims": [{"claim": "completely unrelated fabricated claim about space travel", '
            '"cited_indices": [1]}], "connective_text": ""}'
        )
    )
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)
    assert hook.paragraph == ""
    assert hook.cited_indices == ()


@pytest.mark.asyncio
async def test_handles_malformed_json() -> None:
    """Unparseable LLM output returns an empty hook without raising."""
    j1 = _justification(1, "some summary")
    enr = _enr([j1])
    llm = FakeAnthropic(text="not json")
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)
    assert hook.paragraph == ""
    assert hook.cited_indices == ()


@pytest.mark.asyncio
async def test_supports_multi_claim_multi_index() -> None:
    """Two grounded claims each with a single cited index both survive."""
    j1 = _justification(1, "Chime automated support ticket deflection by 40 percent")
    j2 = _justification(2, "Chime launched voice channel support in 2024")
    enr = _enr([j1, j2])
    llm = FakeAnthropic(
        text=(
            '{"claims": ['
            '{"claim": "Chime automated support ticket deflection", "cited_indices": [1]}, '
            '{"claim": "Chime launched voice channel support", "cited_indices": [2]}'
            '], "connective_text": "We help teams hit higher deflection."}'
        )
    )
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)
    assert "Chime automated" in hook.paragraph
    assert "voice channel" in hook.paragraph
    assert set(hook.cited_indices) == {1, 2}


@pytest.mark.asyncio
async def test_connective_text_appended_after_surviving_claims() -> None:
    """Connective text appears after surviving claim content in the paragraph."""
    j1 = _justification(1, "Chime expanded AI support automation program in 2024")
    enr = _enr([j1])
    llm = FakeAnthropic(
        text=(
            '{"claims": [{"claim": "Chime expanded AI support automation", "cited_indices": [1]}], '
            '"connective_text": "Would love to connect and share how we can help."}'
        )
    )
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)
    assert "Chime expanded AI support automation" in hook.paragraph
    assert "Would love to connect" in hook.paragraph
    # Connective text comes after the claim.
    assert hook.paragraph.index("Chime") < hook.paragraph.index("Would love")


@pytest.mark.asyncio
async def test_fabricated_claim_suppressed_end_to_end() -> None:
    """Fabricated claim with no evidence overlap is dropped; grounded claim survives.

    This is the D-06 functional test: the rapidfuzz coverage gate in
    citations.assemble_paragraph() must suppress uncited-specific claims
    even when the writer includes a valid-looking cited_indices entry.
    """
    # Index 1: summary is about support awards, no overlap with "quantum widget" claim.
    j1 = _justification(1, "Acme support team received a service excellence award")
    # Index 2: summary directly overlaps the second claim about Asia expansion.
    j2 = _justification(2, "Acme expanded into Asia markets in 2024 opening three offices")
    enr = _enr([j1, j2])

    llm = FakeAnthropic(
        text=(
            '{"claims": ['
            '{"claim": "TechCorp dominates 99% of the quantum widget sector", '
            '"cited_indices": [1]}, '
            '{"claim": "Acme expanded into Asia", "cited_indices": [2]}'
            '], "connective_text": "We noticed your company."}'
        )
    )
    hook = await OutreachGenerator(llm, config=_config()).generate(_contact(), enr, score=None)

    # Fabricated claim must NOT appear: "quantum widget sector" has no overlap with
    # "service excellence award" evidence (token_set_ratio well below threshold 0.4).
    assert "quantum widget" not in hook.paragraph

    # Grounded claim MUST survive: "Acme expanded into Asia" overlaps the evidence.
    assert "Acme expanded into Asia" in hook.paragraph

    # Only the surviving claim's index should be present.
    assert len(hook.cited_indices) == 1
    assert hook.cited_indices[0] == 2

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import (
    Account,
    Citation,
    Enrichment,
    EvalScore,
    Firmographics,
    ICPScore,
    NewsItem,
    RubricBreakdown,
    ScoredAccount,
)


class TestAccount:
    def test_normalizes_domain_strips_protocol_and_www(self) -> None:
        assert Account(domain="https://www.Notion.so/").domain == "notion.so"
        assert Account(domain="HTTP://Linear.app").domain == "linear.app"
        assert Account(domain="duolingo.com").domain == "duolingo.com"

    def test_rejects_blank_or_malformed_domain(self) -> None:
        with pytest.raises(ValidationError):
            Account(domain="")
        with pytest.raises(ValidationError):
            Account(domain="not a domain")
        with pytest.raises(ValidationError):
            Account(domain="nodot")

    def test_is_frozen(self) -> None:
        a = Account(domain="notion.so")
        with pytest.raises(ValidationError):
            a.domain = "linear.app"  # type: ignore[misc]


class TestCitation:
    def test_requires_http_url_and_source(self) -> None:
        c = Citation(url="https://example.com/news/x", source="exa")
        assert str(c.url).startswith("https://")
        with pytest.raises(ValidationError):
            Citation(url="not-a-url", source="exa")  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            Citation(url="https://example.com", source="bing")  # type: ignore[arg-type]


class TestEnrichmentEmpty:
    def test_is_empty_when_no_firmographics_and_no_news(self) -> None:
        e = Enrichment(account=Account(domain="x.com"))
        assert e.is_empty is True

    def test_not_empty_with_firmographics(self) -> None:
        e = Enrichment(
            account=Account(domain="x.com"),
            firmographics=Firmographics(name="X"),
        )
        assert e.is_empty is False

    def test_not_empty_with_news(self) -> None:
        cite = Citation(url="https://x.com/news", source="exa")
        n = NewsItem(headline="h", summary="s", citation=cite)
        e = Enrichment(account=Account(domain="x.com"), news=(n,))
        assert e.is_empty is False


class TestRubricRanges:
    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RubricBreakdown(
                support_volume=11,
                ai_maturity=5,
                stage_fit=5,
                channel_breadth=5,
                support_volume_reason="r",
                ai_maturity_reason="r",
                stage_fit_reason="r",
                channel_breadth_reason="r",
            )

    def test_accepts_valid(self) -> None:
        rb = RubricBreakdown(
            support_volume=8,
            ai_maturity=7,
            stage_fit=6,
            channel_breadth=5,
            support_volume_reason="b2c high volume",
            ai_maturity_reason="ai jobs posted",
            stage_fit_reason="series c",
            channel_breadth_reason="email + chat",
        )
        ICPScore(total=7.0, breakdown=rb, justification="solid fit")


class TestEvalScoreFlag:
    def test_flagged_when_groundedness_below_threshold(self) -> None:
        s = EvalScore(groundedness=5.9, icp_relevance=8, personalization=8)
        assert s.is_flagged is True

    def test_not_flagged_at_or_above_threshold(self) -> None:
        s = EvalScore(groundedness=6.0, icp_relevance=8, personalization=8)
        assert s.is_flagged is False


class TestScoredAccountUnscoreable:
    def test_factory_marks_unscoreable_with_reason(self) -> None:
        acc = Account(domain="x.com")
        enr = Enrichment(account=acc)
        sa = ScoredAccount.unscoreable(acc, enr, "no enrichment data")
        assert sa.status == "unscoreable"
        assert sa.score is None
        assert sa.error == "no enrichment data"

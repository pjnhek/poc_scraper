from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import (
    Account,
    AccountStatus,
    Citation,
    Enrichment,
    EvalScore,
    Firmographics,
    ICPScore,
    Justification,
    NewsItem,
    RubricBreakdown,
    ScoredAccount,
)


class TestAccount:
    def test_normalizes_domain_strips_protocol_and_www(self) -> None:
        assert Account(domain="https://www.Notion.so/").domain == "notion.so"
        assert Account(domain="HTTP://Linear.app").domain == "linear.app"
        assert Account(domain="examplelearnco.com").domain == "examplelearnco.com"

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
                support_volume=6,
                ai_maturity=5,
                stage_fit=5,
                channel_breadth=5,
                support_volume_reason="r",
                ai_maturity_reason="r",
                stage_fit_reason="r",
                channel_breadth_reason="r",
            )
        with pytest.raises(ValidationError):
            RubricBreakdown(
                support_volume=0,
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
            support_volume=4,
            ai_maturity=3,
            stage_fit=4,
            channel_breadth=2,
            support_volume_reason="high volume",
            ai_maturity_reason="ai jobs posted",
            stage_fit_reason="series c",
            channel_breadth_reason="email + chat",
        )
        ICPScore(total=3.5, breakdown=rb, justification="solid fit", verdict="borderline")


class TestEvalScoreFlag:
    def test_flagged_when_groundedness_below_threshold(self) -> None:
        s = EvalScore(
            groundedness=2.5, icp_relevance=4, personalization=4, specificity=3, recency=3
        )
        assert s.is_flagged is True

    def test_not_flagged_at_or_above_threshold(self) -> None:
        s = EvalScore(
            groundedness=3.0, icp_relevance=4, personalization=4, specificity=3, recency=3
        )
        assert s.is_flagged is False

    def test_custom_threshold_overrides_default(self) -> None:
        strict = EvalScore(
            groundedness=3.5,
            icp_relevance=4,
            personalization=4,
            specificity=3,
            recency=3,
            flag_threshold=4.0,
        )
        assert strict.is_flagged is True


class TestJustification:
    def test_index_must_be_positive(self) -> None:
        cite = Citation(url="https://x.com/a", source="exa")
        with pytest.raises(ValidationError):
            Justification(index=0, summary="s", citation=cite)
        with pytest.raises(ValidationError):
            Justification(index=-1, summary="s", citation=cite)

    def test_accepts_valid(self) -> None:
        cite = Citation(url="https://x.com/a", source="exa")
        j = Justification(index=1, summary="company raised funding", citation=cite)
        assert j.index == 1
        assert j.summary == "company raised funding"
        assert str(j.citation.url) == "https://x.com/a"


class TestScoredAccountUnscoreable:
    def test_factory_marks_unscoreable_with_reason(self) -> None:
        acc = Account(domain="x.com")
        enr = Enrichment(account=acc)
        sa = ScoredAccount.unscoreable(acc, enr, "no enrichment data")
        assert sa.status == AccountStatus.hook_suppressed
        assert sa.score is None
        assert sa.error == "no enrichment data"

    def test_account_status_serializes_as_string(self) -> None:
        acc = Account(domain="x.com")
        enr = Enrichment(account=acc)
        sa = ScoredAccount(account=acc, status=AccountStatus.clean, enrichment=enr)
        assert sa.model_dump()["status"] == "clean"

    def test_scored_account_rejects_invalid_status(self) -> None:
        from pydantic import ValidationError

        acc = Account(domain="x.com")
        enr = Enrichment(account=acc)
        with pytest.raises(ValidationError):
            ScoredAccount(account=acc, status="invalid_status", enrichment=enr)  # type: ignore[arg-type]

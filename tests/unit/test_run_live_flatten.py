from __future__ import annotations

from evals.run_live import _flatten, summary_line
from src.models import (
    Account,
    AccountStatus,
    Citation,
    Contact,
    Enrichment,
    EvalScore,
    Firmographics,
    ICPScore,
    Justification,
    OutreachHook,
    RubricBreakdown,
    ScoredAccount,
)


def _clean_account() -> ScoredAccount:
    acc = Account(domain="examplefintech.com")
    citation = Citation.make(url="https://example.com/n", source="exa", snippet="s")
    enr = Enrichment(
        account=acc,
        firmographics=Firmographics(name="ExampleFintech"),
        news=(),
        justifications=(Justification(index=1, summary="h: s", citation=citation),),
    )
    bd = RubricBreakdown(
        support_volume=5,
        ai_maturity=4,
        stage_fit=4,
        channel_breadth=4,
        support_volume_reason="r",
        ai_maturity_reason="r",
        stage_fit_reason="r",
        channel_breadth_reason="r",
    )
    score = ICPScore(
        total=4.4, breakdown=bd, justification="strong", verdict="strong", supporting_indices=(1,)
    )
    contact = Contact(role_title="VP CX", rationale="owns deflection")
    hook = OutreachHook(contact=contact, paragraph="grounded hook [1]", cited_indices=(1,))
    ev = EvalScore(groundedness=4.0, icp_relevance=4, personalization=4, specificity=3, recency=3)
    return ScoredAccount(
        account=acc,
        status=AccountStatus.clean,
        enrichment=enr,
        score=score,
        contacts=(contact,),
        hooks=(hook,),
        eval_score=ev,
    )


def test_clean_account_produces_judged_rows() -> None:
    # Regression: the flattener once gated on `sa.status != "scored"`, but the
    # AccountStatus enum has no "scored" value, so every account, including
    # clean ones, fell through to "(unscoreable)" and make eval-live judged
    # nothing. A clean account must yield a real judged row.
    rows = _flatten([_clean_account()])

    assert len(rows) == 1
    assert rows[0].verdict == "strong"
    assert rows[0].verdict != "(unscoreable)"
    assert rows[0].persona == "VP CX"
    assert rows[0].groundedness == 4.0


def test_account_without_score_is_unscoreable() -> None:
    acc = Account(domain="blocked.com")
    enr = Enrichment(account=acc, firmographics=None, news=(), justifications=())
    sa = ScoredAccount.unscoreable(acc, enr, "empty enrichment")

    rows = _flatten([sa])

    assert len(rows) == 1
    assert rows[0].verdict == "(unscoreable)"


def test_judge_failed_row_is_excluded_from_summary_average() -> None:
    # A scored account whose judge crashed (eval_score=None) still has a
    # verdict and hooks, so it produces a row, but it must be marked unjudged
    # and excluded from the summary average rather than counted as a real 0.0.
    judged = _clean_account()  # groundedness 4.0, judged
    crashed = _clean_account_no_eval()  # eval_score=None

    rows = _flatten([judged, crashed])
    assert len(rows) == 2
    crashed_row = next(r for r in rows if r.domain == "crashed.com")
    assert crashed_row.judged is False
    assert crashed_row.verdict != "(unscoreable)"  # still scored, just unjudged

    summary = summary_line(rows)
    # Only the one genuinely judged hook (groundedness 4.0) feeds the average,
    # not a 4.0-and-0.0 blend that would read as 2.0.
    assert "groundedness=4.00" in summary
    assert "1 unjudged hooks excluded" in summary


def _clean_account_no_eval() -> ScoredAccount:
    base = _clean_account()
    acc = Account(domain="crashed.com")
    return ScoredAccount(
        account=acc,
        status=AccountStatus.judge_failed,
        enrichment=Enrichment(account=acc, firmographics=base.enrichment.firmographics),
        score=base.score,
        contacts=base.contacts,
        hooks=tuple(h for h in base.hooks),
        eval_score=None,
    )

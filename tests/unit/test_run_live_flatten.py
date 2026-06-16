from __future__ import annotations

from evals.run_live import _flatten
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

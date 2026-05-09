from __future__ import annotations

from src.models import (
    Account,
    Citation,
    Contact,
    Enrichment,
    EvalScore,
    Firmographics,
    ICPScore,
    NewsItem,
    OutreachHook,
    RubricBreakdown,
    ScoredAccount,
)
from src.sheets import (
    FLAG_COLOR,
    HEADERS,
    VERDICT_COLORS,
    build_rows,
    flagged_row_indices,
    verdict_row_colors,
)


def _scored(domain: str = "chime.com", flag: bool = False) -> ScoredAccount:
    acc = Account(domain=domain)
    citation = Citation.make(url="https://example.com/news", source="exa")
    enr = Enrichment(
        account=acc,
        firmographics=Firmographics(
            name="Chime",
            industry="fintech",
            headcount_range="1000-2000",
            tech_signals=("zendesk", "react"),
        ),
        news=(NewsItem(headline="h", summary="s", citation=citation),),
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
    score = ICPScore(total=4.4, breakdown=bd, justification="strong fit", verdict="strong")
    contacts = (
        Contact(role_title="VP CX", rationale="owns deflection"),
        Contact(role_title="Head Support", rationale="r"),
        Contact(role_title="Dir Auto", rationale="r"),
    )
    hooks = tuple(OutreachHook(contact=c, paragraph="p", citations=(citation,)) for c in contacts)
    ev = EvalScore(
        groundedness=2.0 if flag else 4.0,
        icp_relevance=4,
        personalization=4,
    )
    return ScoredAccount(
        account=acc,
        status="scored",
        enrichment=enr,
        score=score,
        contacts=contacts,
        hooks=hooks,
        eval_score=ev,
    )


def test_build_rows_starts_with_headers() -> None:
    rows = build_rows([_scored()])
    assert rows[0] == list(HEADERS)


def test_build_rows_writes_account_data() -> None:
    rows = build_rows([_scored()])
    row = rows[1]
    headers = rows[0]
    assert row[0] == "chime.com"
    assert row[1] == "scored"
    assert row[2] == "Chime"
    assert row[headers.index("icp_total")] == "4.4"
    assert row[headers.index("verdict")] == "strong"
    assert "VP CX" in row
    assert any("example.com/news" in cell for cell in row)


def test_build_rows_handles_unscoreable() -> None:
    acc = Account(domain="dead.com")
    enr = Enrichment(account=acc)
    sa = ScoredAccount.unscoreable(acc, enr, "no enrichment")
    rows = build_rows([sa])
    headers = rows[0]
    assert rows[1][0] == "dead.com"
    assert rows[1][1] == "unscoreable"
    assert rows[1][headers.index("icp_total")] == ""
    assert rows[1][headers.index("verdict")] == ""
    assert rows[1][-1] == "no enrichment"


def test_flagged_indices_picks_up_low_groundedness() -> None:
    items = [_scored(), _scored(domain="chime2.com", flag=True), _scored(domain="chime3.com")]
    assert flagged_row_indices(items) == [2]


def test_flagged_indices_empty_when_no_eval() -> None:
    assert flagged_row_indices([]) == []


def test_verdict_colors_strong_gets_green() -> None:
    items = [_scored(domain="strong.com")]
    colors = verdict_row_colors(items)
    assert colors == {1: VERDICT_COLORS["strong"]}


def test_verdict_colors_flag_overrides_verdict() -> None:
    items = [_scored(domain="strong.com", flag=True)]
    colors = verdict_row_colors(items)
    assert colors == {1: FLAG_COLOR}

from __future__ import annotations

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
    NewsItem,
    OutreachHook,
    RubricBreakdown,
    ScoredAccount,
)
from src.sheets import (
    ACCOUNT_STATUS_COLORS,
    HEADERS,
    LEGEND_TAB_TITLE,
    STATUS_LEGEND,
    _hyperlink_formula,
    _sources_row_lookup,
    account_status_row_colors,
    build_legend_rows,
    build_rows,
    build_sources_rows,
    flagged_eval_rows,
)


def _scored(
    domain: str = "examplefintech.com",
    flag: bool = False,
    status: AccountStatus = AccountStatus.clean,
) -> ScoredAccount:
    acc = Account(domain=domain)
    citation = Citation.make(url="https://example.com/news", source="exa", snippet="snippet")
    enr = Enrichment(
        account=acc,
        firmographics=Firmographics(
            name="ExampleFintech",
            industry="software",
            headcount_range="1000-2000",
            tech_signals=("zendesk", "react"),
        ),
        news=(NewsItem(headline="h", summary="s", citation=citation),),
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
        total=4.4,
        breakdown=bd,
        justification="strong fit",
        verdict="strong",
        supporting_indices=(1,),
    )
    contacts = (
        Contact(role_title="VP CX", rationale="owns deflection"),
        Contact(role_title="Head Support", rationale="r"),
        Contact(role_title="Dir Auto", rationale="r"),
    )
    hooks = tuple(OutreachHook(contact=c, paragraph="p [1]", cited_indices=(1,)) for c in contacts)
    ev = EvalScore(
        groundedness=2.0 if flag else 4.0,
        icp_relevance=4,
        personalization=4,
        specificity=3,
        recency=3,
    )
    return ScoredAccount(
        account=acc,
        status=status,
        enrichment=enr,
        score=score,
        contacts=contacts,
        hooks=hooks,
        eval_score=ev,
    )


def test_build_rows_starts_with_headers() -> None:
    rows = build_rows([_scored()])
    assert rows[0] == list(HEADERS)
    assert len(HEADERS) == 28
    assert "hook_1_citations" not in HEADERS
    assert "hook_2_citations" not in HEADERS
    assert "hook_3_citations" not in HEADERS


def test_build_rows_writes_account_data() -> None:
    sa = _scored()
    rows = build_rows(
        [sa],
        sources_sheet_id=123,
        sources_lookup=_sources_row_lookup([sa]),
    )
    row = rows[1]
    headers = rows[0]
    assert row[0] == "examplefintech.com"
    assert row[1] == AccountStatus.clean
    assert row[2] == "ExampleFintech"
    assert row[headers.index("icp_total")] == "4.4"
    assert row[headers.index("verdict")] == "strong"
    assert "VP CX" in row
    assert row[headers.index("hook_1")].startswith('=HYPERLINK("#gid=')


def test_justification_cell_includes_supporting_evidence() -> None:
    sa = _scored()
    rows = build_rows(
        [sa],
        sources_sheet_id=123,
        sources_lookup=_sources_row_lookup([sa]),
    )
    row = rows[1]
    headers = rows[0]
    just_cell = row[headers.index("justification")]
    assert just_cell.startswith('=HYPERLINK("#gid=')
    assert "Supporting:" in just_cell
    assert "[1]" in just_cell
    assert "https://" not in just_cell


def test_justification_cell_flags_missing_supporting_indices() -> None:
    """If the writer omits supporting_indices, the cell should make that
    visible rather than silently rendering an unsupported claim."""
    sa = _scored()
    # Reconstruct the score with empty supporting_indices.
    assert sa.score is not None
    bare_score = sa.score.model_copy(update={"supporting_indices": ()})
    sa_bare = sa.model_copy(update={"score": bare_score})
    rows = build_rows(
        [sa_bare],
        sources_sheet_id=123,
        sources_lookup=_sources_row_lookup([sa_bare]),
    )
    row = rows[1]
    headers = rows[0]
    just_cell = row[headers.index("justification")]
    assert just_cell.startswith('=HYPERLINK("#gid=')
    assert "no supporting indices" in just_cell


def test_build_rows_handles_unscoreable() -> None:
    acc = Account(domain="dead.com")
    enr = Enrichment(account=acc)
    sa = ScoredAccount.unscoreable(acc, enr, "no enrichment")
    rows = build_rows([sa])
    headers = rows[0]
    assert rows[1][0] == "dead.com"
    assert rows[1][1] == AccountStatus.hook_suppressed
    assert rows[1][headers.index("icp_total")] == ""
    assert rows[1][headers.index("verdict")] == ""
    assert rows[1][headers.index("hook_1")] == ""
    assert rows[1][-1] == "no enrichment"


def test_hyperlink_formula_basic() -> None:
    assert _hyperlink_formula(123, 5, "hello") == '=HYPERLINK("#gid=123&range=A5", "hello")'


def test_hyperlink_formula_escapes_quotes() -> None:
    assert (
        _hyperlink_formula(123, 5, 'he said "hi"')
        == '=HYPERLINK("#gid=123&range=A5", "he said ""hi""")'
    )


def test_hyperlink_formula_empty_text() -> None:
    assert _hyperlink_formula(123, 5, "") == ""


def test_build_sources_rows_header() -> None:
    rows = build_sources_rows([_scored()])
    assert rows[0] == ["domain", "index", "summary", "url", "source"]


def test_build_sources_rows_emits_one_per_justification() -> None:
    base = _scored()
    citation = Citation.make(url="https://example.com/second", source="browserbase")
    justifications = base.enrichment.justifications + (
        Justification(index=2, summary="second", citation=citation),
        Justification(index=3, summary="third", citation=citation),
    )
    enrichment = base.enrichment.model_copy(update={"justifications": justifications})
    sa = base.model_copy(update={"enrichment": enrichment})

    rows = build_sources_rows([sa])

    assert len(rows) == 4
    assert [row[0] for row in rows[1:]] == ["examplefintech.com"] * 3
    assert [row[1] for row in rows[1:]] == ["1", "2", "3"]
    assert rows[1][3] == "https://example.com/news"
    assert rows[2][3] == "https://example.com/second"
    assert rows[2][4] == "browserbase"


def test_build_sources_rows_omits_unscoreable() -> None:
    acc = Account(domain="dead.com")
    enr = Enrichment(account=acc)
    sa = ScoredAccount.unscoreable(acc, enr, "no enrichment")
    rows = build_sources_rows([sa])
    assert rows == [["domain", "index", "summary", "url", "source"]]


def test_sources_row_lookup_returns_first_data_row_two() -> None:
    sa = _scored()
    lookup = _sources_row_lookup([sa])
    assert lookup[(sa.account.domain, 1)] == 2


def test_flagged_eval_rows_picks_up_low_groundedness() -> None:
    items = [
        _scored(),
        _scored(domain="exampleapp2.com", flag=True),
        _scored(domain="exampleapp3.com"),
    ]
    assert flagged_eval_rows(items) == [2]


def test_flagged_eval_rows_empty_when_no_eval() -> None:
    assert flagged_eval_rows([]) == []


def test_account_status_colors_palette_complete() -> None:
    assert set(ACCOUNT_STATUS_COLORS) == set(AccountStatus)
    for color in ACCOUNT_STATUS_COLORS.values():
        assert all(0.0 <= component <= 1.0 for component in color.values())


def test_account_status_colors_clean_omitted_from_row_colors() -> None:
    assert account_status_row_colors([_scored(status=AccountStatus.clean)]) == {}


def test_account_status_colors_judge_failed_is_gray_not_red() -> None:
    color = ACCOUNT_STATUS_COLORS[AccountStatus.judge_failed]
    assert abs(color["red"] - color["green"]) <= 0.05
    assert abs(color["green"] - color["blue"]) <= 0.05
    assert color["red"] <= 0.92


def test_account_status_colors_hook_suppressed_distinct_from_clean() -> None:
    color = ACCOUNT_STATUS_COLORS[AccountStatus.hook_suppressed]
    assert color != {"red": 1.0, "green": 1.0, "blue": 1.0}
    assert any(component < 0.95 for component in color.values())


def test_build_legend_rows_emits_four_states() -> None:
    rows = build_legend_rows()
    assert LEGEND_TAB_TITLE == "Legend"
    assert rows[0] == ["status", "color", "meaning", "precedence"]
    assert [row[0] for row in rows[1:]] == [status.value for status in AccountStatus]


def test_build_legend_rows_publishes_precedence_string() -> None:
    rendered = "\n".join(cell for row in build_legend_rows() for cell in row)
    assert STATUS_LEGEND in rendered

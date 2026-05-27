from __future__ import annotations

from src.icp_config import ICPConfig, get_config
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
    COLUMN_WIDTHS,
    HEADERS,
    LEGEND_TAB_TITLE,
    STATUS_LEGEND,
    WIDTH_CLASS_PX,
    _hyperlink_formula,
    _sources_row_lookup,
    account_status_row_colors,
    axis_display_labels,
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
    for hook_index in range(1, 4):
        assert f"hook_{hook_index}_citations" not in HEADERS


def test_axis_display_labels_uses_configured_weights() -> None:
    assert axis_display_labels(get_config()) == {
        "support_volume": "Support Volume (40%)",
        "ai_maturity": "AI Maturity (30%)",
        "stage_fit": "Stage Fit (20%)",
        "channel_breadth": "Channel Breadth (10%)",
    }


def test_axis_display_labels_rounds_to_integer_percent() -> None:
    config = _config_with_weights(
        {
            "support_volume": 1 / 3,
            "ai_maturity": 1 / 3,
            "stage_fit": 1 / 6,
            "channel_breadth": 1 / 6,
        }
    )

    assert axis_display_labels(config) == {
        "support_volume": "Support Volume (33%)",
        "ai_maturity": "AI Maturity (33%)",
        "stage_fit": "Stage Fit (17%)",
        "channel_breadth": "Channel Breadth (17%)",
    }


def test_build_rows_projects_display_labels_when_config_provided() -> None:
    rows = build_rows([_scored()], config=get_config())

    assert rows[0][HEADERS.index("support_volume")] == "Support Volume (40%)"
    assert rows[0][HEADERS.index("ai_maturity")] == "AI Maturity (30%)"
    assert rows[0][HEADERS.index("stage_fit")] == "Stage Fit (20%)"
    assert rows[0][HEADERS.index("channel_breadth")] == "Channel Breadth (10%)"
    assert rows[0][HEADERS.index("domain")] == "domain"
    assert rows[0][HEADERS.index("icp_total")] == "icp_total"


def test_build_rows_keeps_snake_case_when_no_config() -> None:
    assert build_rows([_scored()])[0] == list(HEADERS)


def test_axis_display_labels_only_four_keys() -> None:
    assert set(axis_display_labels(get_config())) == {
        "support_volume",
        "ai_maturity",
        "stage_fit",
        "channel_breadth",
    }


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


def _config_with_weights(weights: dict[str, float]) -> ICPConfig:
    raw = get_config().model_dump()
    raw["axes"] = {name: {**axis, "weight": weights[name]} for name, axis in raw["axes"].items()}
    return ICPConfig.model_validate(raw)


def test_width_class_px_locks_pixel_values() -> None:
    assert WIDTH_CLASS_PX == {"narrow": 110, "medium": 180, "wide": 400, "extra": 250}


def test_column_widths_covers_every_header_exactly_once() -> None:
    assert set(COLUMN_WIDTHS.keys()) == set(HEADERS)
    assert len(COLUMN_WIDTHS) == len(HEADERS)


def test_column_widths_values_are_known_classes() -> None:
    assert set(COLUMN_WIDTHS.values()).issubset(set(WIDTH_CLASS_PX.keys()))


def test_column_widths_class_assignment_per_d13() -> None:
    narrow = {
        "domain",
        "status",
        "icp_total",
        "verdict",
        "support_volume",
        "ai_maturity",
        "stage_fit",
        "channel_breadth",
        "eval_groundedness",
        "eval_icp_relevance",
        "eval_personalization",
        "eval_specificity",
        "eval_recency",
    }
    medium = {
        "name",
        "industry",
        "headcount",
        "tech_signals",
        "contact_1_role",
        "contact_1_rationale",
        "contact_2_role",
        "contact_2_rationale",
        "contact_3_role",
        "contact_3_rationale",
    }
    wide = {"hook_1", "hook_2", "hook_3", "justification"}
    extra = {"error"}
    for name in narrow:
        assert COLUMN_WIDTHS[name] == "narrow", name
    for name in medium:
        assert COLUMN_WIDTHS[name] == "medium", name
    for name in wide:
        assert COLUMN_WIDTHS[name] == "wide", name
    for name in extra:
        assert COLUMN_WIDTHS[name] == "extra", name

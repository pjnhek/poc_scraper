from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.icp_config import get_config
from src.mcp_server.scoring import ScoreResult, build_score_result


def test_all_fives_yields_five_and_strong() -> None:
    result = build_score_result(support_volume=5, ai_maturity=5, stage_fit=5, channel_breadth=5)
    assert result.total == 5.0
    assert result.verdict == "strong"


def test_all_ones_yields_one_and_weak() -> None:
    result = build_score_result(support_volume=1, ai_maturity=1, stage_fit=1, channel_breadth=1)
    assert result.total == 1.0
    assert result.verdict == "weak"


def test_weighted_average_matches_manual_and_borderline() -> None:
    config = get_config()
    weights = {n: a.weight for n, a in config.axes.items()}
    expected = round(
        4 * weights["support_volume"]
        + 3 * weights["ai_maturity"]
        + 5 * weights["stage_fit"]
        + 2 * weights["channel_breadth"],
        1,
    )
    result = build_score_result(support_volume=4, ai_maturity=3, stage_fit=5, channel_breadth=2)
    assert result.total == expected
    assert result.total == 3.7
    assert result.verdict == "borderline"


@pytest.mark.parametrize(
    ("axis", "kwargs"),
    [
        ("support_volume", {"support_volume": 0}),
        ("ai_maturity", {"ai_maturity": 6}),
        ("stage_fit", {"stage_fit": -1}),
    ],
)
def test_out_of_range_axis_raises_per_axis_value_error(axis: str, kwargs: dict[str, int]) -> None:
    base = {"support_volume": 3, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3}
    base.update(kwargs)
    with pytest.raises(ValueError, match=f"^{axis} must be an integer 1-5$"):
        build_score_result(**base)


def test_omitted_reasons_default_to_empty_string() -> None:
    result = build_score_result(support_volume=3, ai_maturity=3, stage_fit=3, channel_breadth=3)
    assert result.breakdown.support_volume_reason == ""
    assert result.breakdown.ai_maturity_reason == ""
    assert result.breakdown.stage_fit_reason == ""
    assert result.breakdown.channel_breadth_reason == ""


def test_provided_reasons_pass_through_verbatim() -> None:
    result = build_score_result(
        support_volume=3,
        ai_maturity=3,
        stage_fit=3,
        channel_breadth=3,
        support_volume_reason="high ticket volume [1]",
        ai_maturity_reason="AI hiring signal [2]",
        stage_fit_reason="series B [3]",
        channel_breadth_reason="four channels [4]",
    )
    assert result.breakdown.support_volume_reason == "high ticket volume [1]"
    assert result.breakdown.ai_maturity_reason == "AI hiring signal [2]"
    assert result.breakdown.stage_fit_reason == "series B [3]"
    assert result.breakdown.channel_breadth_reason == "four channels [4]"


def test_domain_echoed_verbatim() -> None:
    result = build_score_result(
        support_volume=3, ai_maturity=3, stage_fit=3, channel_breadth=3, domain="notion.so"
    )
    assert result.domain == "notion.so"


def test_omitted_domain_echoes_none() -> None:
    result = build_score_result(support_volume=3, ai_maturity=3, stage_fit=3, channel_breadth=3)
    assert result.domain is None


def test_weights_and_verdict_thresholds_echo_config() -> None:
    config = get_config()
    result = build_score_result(support_volume=3, ai_maturity=3, stage_fit=3, channel_breadth=3)
    expected_weights = {name: axis.weight for name, axis in config.axes.items()}
    expected_thresholds = {v.label: v.min_total for v in config.verdicts.values()}
    assert result.weights == expected_weights
    assert result.verdict_thresholds == expected_thresholds


def test_score_result_is_frozen() -> None:
    result = build_score_result(support_volume=3, ai_maturity=3, stage_fit=3, channel_breadth=3)
    with pytest.raises(ValidationError):
        result.total = 4.0  # type: ignore[misc]


def test_score_result_forbids_unknown_kwargs() -> None:
    result = build_score_result(support_volume=3, ai_maturity=3, stage_fit=3, channel_breadth=3)
    with pytest.raises(ValidationError):
        ScoreResult(
            domain=result.domain,
            breakdown=result.breakdown,
            total=result.total,
            verdict=result.verdict,
            verdict_description=result.verdict_description,
            weights=result.weights,
            verdict_thresholds=result.verdict_thresholds,
            unknown_field="oops",  # type: ignore[call-arg]
        )

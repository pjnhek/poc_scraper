from __future__ import annotations

import pytest

from src.icp_config import get_config
from src.models import RubricBreakdown
from src.score import compute_total


def _rb(sv: float, ai: float, stage: float, ch: float) -> RubricBreakdown:
    return RubricBreakdown(
        support_volume=sv,
        ai_maturity=ai,
        stage_fit=stage,
        channel_breadth=ch,
        support_volume_reason="r",
        ai_maturity_reason="r",
        stage_fit_reason="r",
        channel_breadth_reason="r",
    )


def test_weights_sum_to_one() -> None:
    config = get_config()
    assert sum(a.weight for a in config.axes.values()) == pytest.approx(1.0)


def test_all_fives_yields_five() -> None:
    assert compute_total(_rb(5, 5, 5, 5)) == 5.0


def test_all_ones_yields_one() -> None:
    assert compute_total(_rb(1, 1, 1, 1)) == 1.0


def test_weighted_average_matches_manual() -> None:
    config = get_config()
    rb = _rb(4, 3, 5, 2)
    weights = {n: a.weight for n, a in config.axes.items()}
    expected = round(
        4 * weights["support_volume"]
        + 3 * weights["ai_maturity"]
        + 5 * weights["stage_fit"]
        + 2 * weights["channel_breadth"],
        1,
    )
    assert compute_total(rb) == expected


def test_support_volume_dominates() -> None:
    high_sv = compute_total(_rb(5, 1, 1, 1))
    high_ai = compute_total(_rb(1, 5, 1, 1))
    assert high_sv > high_ai


def test_strong_archetype_scores_above_strong_threshold() -> None:
    strong = _rb(5, 4, 4, 5)
    config = get_config()
    total = compute_total(strong)
    assert config.verdict_for(total).label == "strong"


def test_weak_archetype_scores_weak() -> None:
    weak = _rb(1, 1, 2, 1)
    config = get_config()
    total = compute_total(weak)
    assert config.verdict_for(total).label == "weak"

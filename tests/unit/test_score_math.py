from __future__ import annotations

import pytest

from src.models import RubricBreakdown
from src.score import WEIGHTS, compute_total


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
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_all_tens_yields_ten() -> None:
    assert compute_total(_rb(10, 10, 10, 10)) == 10.0


def test_all_zeros_yields_zero() -> None:
    assert compute_total(_rb(0, 0, 0, 0)) == 0.0


def test_weighted_average_matches_manual() -> None:
    rb = _rb(8, 6, 5, 4)
    expected = round(8 * 0.4 + 6 * 0.3 + 5 * 0.2 + 4 * 0.1, 1)
    assert compute_total(rb) == expected


def test_support_volume_dominates() -> None:
    high_sv = compute_total(_rb(10, 0, 0, 0))
    high_ai = compute_total(_rb(0, 10, 0, 0))
    assert high_sv > high_ai


def test_acme_archetype_scores_high() -> None:
    cash_app_like = _rb(10, 9, 9, 10)
    assert compute_total(cash_app_like) >= 9.0

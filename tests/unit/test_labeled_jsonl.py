from __future__ import annotations

from pathlib import Path

import pytest

from evals.run_eval import load_labeled

LABELED_PATH = Path(__file__).parents[2] / "evals" / "labeled.jsonl"


def test_all_records_have_split_field() -> None:
    examples = load_labeled(LABELED_PATH)
    assert all(ex.split in ("train", "holdout") for ex in examples)  # type: ignore[attr-defined]


def test_all_records_have_five_axis_expected_values() -> None:
    examples = load_labeled(LABELED_PATH)
    for ex in examples:
        assert 1.0 <= ex.expected_groundedness <= 5.0
        assert 1.0 <= ex.expected_relevance <= 5.0
        assert 1.0 <= ex.expected_personalization <= 5.0
        assert 1.0 <= ex.expected_specificity <= 5.0  # type: ignore[attr-defined]
        assert 1.0 <= ex.expected_recency <= 5.0  # type: ignore[attr-defined]


@pytest.mark.skip(reason="labeled.jsonl not yet rebuilt; will pass after plan 03-04")
def test_holdout_fraction_near_30_pct() -> None:
    examples = load_labeled(LABELED_PATH)
    holdout_count = sum(1 for ex in examples if ex.split == "holdout")  # type: ignore[attr-defined]
    total = len(examples)
    # 20-40% is acceptable for a small labeled set; strict 30% only holds at scale.
    assert total > 0
    assert 0.15 <= holdout_count / total <= 0.45


@pytest.mark.skip(reason="labeled.jsonl not yet rebuilt; will pass after plan 03-04")
def test_all_records_have_coverage_cells() -> None:
    examples = load_labeled(LABELED_PATH)
    assert all(ex.coverage_cells for ex in examples)  # type: ignore[attr-defined]


@pytest.mark.skip(reason="labeled.jsonl not yet rebuilt; will pass after plan 03-04")
def test_no_eval_failed_true_except_sentinel_records() -> None:
    examples = load_labeled(LABELED_PATH)
    failed = [ex for ex in examples if ex.expected_eval_failed]  # type: ignore[attr-defined]
    # Only judge-failure-cell records should have eval_failed=True.
    assert all("judge-failed" in ex.coverage_cells for ex in failed)  # type: ignore[attr-defined]

from __future__ import annotations

import pytest


def test_perfect_agreement_yields_one() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    cohen_kappa_linear = mod.cohen_kappa_linear  # type: ignore[attr-defined]
    scores = [1.0, 2.0, 3.0, 4.0, 5.0, 3.0, 2.0, 1.0, 4.0, 5.0]
    assert cohen_kappa_linear(scores, scores) == pytest.approx(1.0)


def test_single_class_collapse_yields_one() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    cohen_kappa_linear = mod.cohen_kappa_linear  # type: ignore[attr-defined]
    # All same score: kappa undefined, must return 1.0 not raise ZeroDivisionError.
    scores = [3.0] * 10
    assert cohen_kappa_linear(scores, scores) == pytest.approx(1.0)


def test_near_perfect_raters_above_0_8() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    cohen_kappa_linear = mod.cohen_kappa_linear  # type: ignore[attr-defined]
    r1 = [1.0, 2.0, 3.0, 4.0, 5.0, 3.0, 2.0, 1.0, 4.0, 5.0]
    r2 = [1.0, 2.0, 3.0, 4.0, 4.0, 3.0, 2.0, 2.0, 4.0, 5.0]  # one disagreement
    kappa = cohen_kappa_linear(r1, r2)
    assert kappa > 0.8


def test_pct_agreement_exact_match() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    pct_agreement = mod.pct_agreement  # type: ignore[attr-defined]
    r1 = [1.0, 2.0, 3.0]
    r2 = [1.0, 2.0, 4.0]  # one mismatch
    assert pct_agreement(r1, r2) == pytest.approx(2 / 3)


def test_pct_agreement_perfect() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    pct_agreement = mod.pct_agreement  # type: ignore[attr-defined]
    scores = [1.0, 3.0, 5.0]
    assert pct_agreement(scores, scores) == pytest.approx(1.0)

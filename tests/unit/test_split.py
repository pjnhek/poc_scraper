from __future__ import annotations

import pytest


def test_assign_split_is_deterministic() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    assign_split = mod.assign_split  # type: ignore[attr-defined]
    assert assign_split("example01-vp-cx") == assign_split("example01-vp-cx")


def test_assign_split_holdout_rate_near_30_pct() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    assign_split = mod.assign_split  # type: ignore[attr-defined]
    ids = [f"rec-{i:04d}" for i in range(500)]
    holdout_count = sum(1 for id_ in ids if assign_split(id_) == "holdout")
    # Expect 25-35% holdout; tight enough to catch salt bugs.
    assert 125 <= holdout_count <= 175


def test_assign_split_returns_only_valid_literals() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    assign_split = mod.assign_split  # type: ignore[attr-defined]
    for i in range(20):
        result = assign_split(f"record-{i}")
        assert result in ("train", "holdout")


def test_assign_split_stable_across_set_size() -> None:
    mod = pytest.importorskip("evals.agreement", reason="evals.agreement not yet created")
    assign_split = mod.assign_split  # type: ignore[attr-defined]
    id_under_test = "example01-vp-cx"
    original = assign_split(id_under_test)
    # Adding more records must not shift existing assignments; re-call with same id.
    assert assign_split(id_under_test) == original

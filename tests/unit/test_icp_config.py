from __future__ import annotations

from pathlib import Path

import pytest

from src.icp_config import load_config


def test_default_config_loads() -> None:
    config = load_config()
    assert config.buyer_description.strip()
    assert set(config.axes.keys()) == {
        "support_volume",
        "ai_maturity",
        "stage_fit",
        "channel_breadth",
    }
    assert sum(a.weight for a in config.axes.values()) == pytest.approx(1.0)


def test_each_axis_has_five_anchors() -> None:
    config = load_config()
    for name, axis in config.axes.items():
        assert set(axis.anchors.keys()) == {"1", "2", "3", "4", "5"}, name


def test_verdict_bucketing() -> None:
    config = load_config()
    assert config.verdict_for(4.9).label == "strong"
    assert config.verdict_for(4.0).label == "strong"
    assert config.verdict_for(3.0).label == "borderline"
    assert config.verdict_for(2.5).label == "borderline"
    assert config.verdict_for(2.4).label == "weak"
    assert config.verdict_for(0.0).label == "weak"


def test_invalid_weights_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("""
buyer_description: x
seller_description: x
axes:
  support_volume: {weight: 0.5, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  ai_maturity: {weight: 0.3, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  stage_fit: {weight: 0.1, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  channel_breadth: {weight: 0.05, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
verdicts:
  strong: {min_total: 4.0, label: strong, description: d}
  weak: {min_total: 0.0, label: weak, description: d}
eval:
  groundedness_flag_threshold: 3.0
""")
    with pytest.raises(ValueError, match="weights must sum"):
        load_config(bad)

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.icp_config import EvalConfig, load_config


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


_VALID_PERSONAS = """
default_personas:
  - role_title: "Test Role A"
    rationale: "(no rationale provided)"
  - role_title: "Test Role B"
    rationale: "(no rationale provided)"
  - role_title: "Test Role C"
    rationale: "(no rationale provided)"
"""

_VALID_EVAL = """
eval:
  groundedness_flag_threshold: 3.0
  groundedness_suppress_threshold: 0.4
"""


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
""" + _VALID_EVAL + _VALID_PERSONAS)
    with pytest.raises(ValueError, match="weights must sum"):
        load_config(bad)


def test_suppress_threshold_out_of_range_rejected() -> None:
    # groundedness_suppress_threshold must be in [0, 1]; values outside reject at load time (D-07).
    with pytest.raises(ValidationError):
        EvalConfig(groundedness_flag_threshold=3.0, groundedness_suppress_threshold=1.5)


def test_suppress_threshold_boundary_values_accepted() -> None:
    # 0.0 and 1.0 are valid boundary values.
    low = EvalConfig(groundedness_flag_threshold=3.0, groundedness_suppress_threshold=0.0)
    high = EvalConfig(groundedness_flag_threshold=3.0, groundedness_suppress_threshold=1.0)
    assert low.groundedness_suppress_threshold == 0.0
    assert high.groundedness_suppress_threshold == 1.0


def test_default_personas_count_enforced(tmp_path: Path) -> None:
    # Exactly 3 default_personas entries required; 2 must raise with actionable message (D-07).
    bad = tmp_path / "two_personas.yaml"
    bad.write_text("""
buyer_description: x
seller_description: x
axes:
  support_volume: {weight: 0.4, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  ai_maturity: {weight: 0.3, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  stage_fit: {weight: 0.2, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  channel_breadth: {weight: 0.1, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
verdicts:
  strong: {min_total: 4.0, label: strong, description: d}
  weak: {min_total: 0.0, label: weak, description: d}
eval:
  groundedness_flag_threshold: 3.0
  groundedness_suppress_threshold: 0.4
default_personas:
  - role_title: "Test Role A"
    rationale: "(no rationale provided)"
  - role_title: "Test Role B"
    rationale: "(no rationale provided)"
""")
    with pytest.raises(ValueError, match="default_personas must have exactly 3"):
        load_config(bad)


def test_default_personas_empty_role_title_rejected(tmp_path: Path) -> None:
    # A persona with an empty role_title must fail D-07 validation.
    bad = tmp_path / "empty_role.yaml"
    bad.write_text("""
buyer_description: x
seller_description: x
axes:
  support_volume: {weight: 0.4, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  ai_maturity: {weight: 0.3, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  stage_fit: {weight: 0.2, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
  channel_breadth: {weight: 0.1, description: x, anchors: {"1": a, "2": b, "3": c, "4": d, "5": e}}
verdicts:
  strong: {min_total: 4.0, label: strong, description: d}
  weak: {min_total: 0.0, label: weak, description: d}
eval:
  groundedness_flag_threshold: 3.0
  groundedness_suppress_threshold: 0.4
default_personas:
  - role_title: ""
    rationale: "(no rationale provided)"
  - role_title: "Test Role B"
    rationale: "(no rationale provided)"
  - role_title: "Test Role C"
    rationale: "(no rationale provided)"
""")
    with pytest.raises(ValueError, match="role_title must be non-empty"):
        load_config(bad)

from __future__ import annotations

from src.icp_config import get_config
from src.sheets import build_rubric_rows


def test_rubric_rows_include_all_axes() -> None:
    config = get_config()
    rows = build_rubric_rows(config)
    flat = [cell for row in rows for cell in row]
    for axis_name in config.axes:
        assert axis_name in flat, f"missing axis: {axis_name}"


def test_rubric_rows_render_each_axis_weight() -> None:
    config = get_config()
    rows = build_rubric_rows(config)
    weight_cells = [cell for row in rows for cell in row if cell and cell[:1].isdigit()]
    for axis in config.axes.values():
        assert f"{axis.weight:.2f}" in weight_cells


def test_rubric_rows_render_all_five_anchors_per_axis() -> None:
    config = get_config()
    rows = build_rubric_rows(config)
    for axis_name, axis in config.axes.items():
        axis_row = next(r for r in rows if r and r[0] == axis_name)
        anchor_cells = axis_row[3:8]
        for level in ("1", "2", "3", "4", "5"):
            assert axis.anchors[level] in anchor_cells, f"{axis_name} missing anchor {level}"


def test_rubric_rows_include_verdict_thresholds() -> None:
    config = get_config()
    rows = build_rubric_rows(config)
    flat = [cell for row in rows for cell in row]
    for verdict in config.verdicts.values():
        assert verdict.label in flat


def test_rubric_rows_mention_groundedness_flag_threshold() -> None:
    config = get_config()
    rows = build_rubric_rows(config)
    flat_text = "\n".join(cell for row in rows for cell in row)
    assert f"{config.eval.groundedness_flag_threshold:.1f}" in flat_text
    assert "groundedness" in flat_text.lower()


def test_rubric_rows_have_buyer_description() -> None:
    config = get_config()
    rows = build_rubric_rows(config)
    flat_text = "\n".join(cell for row in rows for cell in row)
    assert config.buyer_description.strip()[:40] in flat_text

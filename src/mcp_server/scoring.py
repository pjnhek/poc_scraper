from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.icp_config import ICPConfig, get_config
from src.models import RubricBreakdown
from src.score import compute_total


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScoreResult(_Frozen):
    domain: str | None = None
    breakdown: RubricBreakdown
    total: float
    verdict: str
    verdict_description: str
    # Echoed rubric context (D-06): plain str/float maps keep the wire
    # payload flat and directly JSON-serializable, no new nested model
    # types beyond what src/icp_config.py already exposes as data.
    weights: dict[str, float]
    verdict_thresholds: dict[str, float]


_AXIS_NAMES = ("support_volume", "ai_maturity", "stage_fit", "channel_breadth")


def build_score_result(
    *,
    support_volume: int,
    ai_maturity: int,
    stage_fit: int,
    channel_breadth: int,
    support_volume_reason: str = "",
    ai_maturity_reason: str = "",
    stage_fit_reason: str = "",
    channel_breadth_reason: str = "",
    domain: str | None = None,
    config: ICPConfig | None = None,
) -> ScoreResult:
    cfg = config or get_config()
    scores = {
        "support_volume": support_volume,
        "ai_maturity": ai_maturity,
        "stage_fit": stage_fit,
        "channel_breadth": channel_breadth,
    }
    for name in _AXIS_NAMES:
        value = scores[name]
        if not 1 <= value <= 5:
            raise ValueError(f"{name} must be an integer 1-5")

    breakdown = RubricBreakdown(
        support_volume=support_volume,
        ai_maturity=ai_maturity,
        stage_fit=stage_fit,
        channel_breadth=channel_breadth,
        support_volume_reason=support_volume_reason,
        ai_maturity_reason=ai_maturity_reason,
        stage_fit_reason=stage_fit_reason,
        channel_breadth_reason=channel_breadth_reason,
    )
    total = compute_total(breakdown, cfg)
    verdict = cfg.verdict_for(total)
    return ScoreResult(
        domain=domain,
        breakdown=breakdown,
        total=total,
        verdict=verdict.label,
        verdict_description=verdict.description,
        weights={name: axis.weight for name, axis in cfg.axes.items()},
        verdict_thresholds={v.label: v.min_total for v in cfg.verdicts.values()},
    )

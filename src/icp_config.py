from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "icp.yaml"

AxisName = Literal["support_volume", "ai_maturity", "stage_fit", "channel_breadth"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Axis(_Frozen):
    weight: float = Field(ge=0, le=1)
    description: str
    anchors: dict[str, str]


class Verdict(_Frozen):
    min_total: float = Field(ge=0, le=5)
    label: str
    description: str


class EvalConfig(_Frozen):
    groundedness_flag_threshold: float = Field(ge=0, le=5)


class ICPConfig(_Frozen):
    buyer_description: str
    seller_description: str
    axes: dict[str, Axis]
    verdicts: dict[str, Verdict]
    eval: EvalConfig

    @model_validator(mode="after")
    def _check_axes(self) -> ICPConfig:
        expected = {"support_volume", "ai_maturity", "stage_fit", "channel_breadth"}
        if set(self.axes.keys()) != expected:
            raise ValueError(f"axes must be exactly {sorted(expected)}, got {sorted(self.axes)}")
        total_weight = sum(a.weight for a in self.axes.values())
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"axis weights must sum to 1.0, got {total_weight}")
        return self

    def verdict_for(self, total: float) -> Verdict:
        ranked = sorted(self.verdicts.values(), key=lambda v: v.min_total, reverse=True)
        for v in ranked:
            if total >= v.min_total:
                return v
        return ranked[-1]


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> ICPConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"ICP config not found at {p}")
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return ICPConfig.model_validate(raw)


@lru_cache(maxsize=1)
def get_config() -> ICPConfig:
    return load_config()

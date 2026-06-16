from __future__ import annotations

import logging

from ._json_utils import clip_score, parse_json_object
from .citations import parse_indices
from .clients.protocols import LLMClient
from .icp_config import ICPConfig, get_config
from .models import Enrichment, ICPScore, RubricBreakdown

log = logging.getLogger(__name__)


def _build_score_system(config: ICPConfig) -> str:
    axis_lines = []
    for name, axis in config.axes.items():
        anchor_lines = "; ".join(f"{k}={v}" for k, v in sorted(axis.anchors.items()))
        axis_lines.append(
            f"- {name} (weight {axis.weight}): {axis.description.strip()} "
            f"Anchors: {anchor_lines}"
        )
    axes_block = "\n".join(axis_lines)
    return (
        "You score companies against an ICP rubric and return JSON. "
        f"Buyer description: {config.buyer_description.strip()}\n"
        f"Score each axis on a 1-5 categorical scale using the anchors:\n{axes_block}\n\n"
        "The user message will provide a numbered list of justifications drawn from "
        "Exa retrievals (about pages and recent news). When you score, also return a "
        '"supporting_indices" array listing the 1-based indices of the justifications '
        "that most directly support your verdict.\n\n"
        "Output ONLY one JSON object with keys: "
        '"support_volume" (integer 1-5), "support_volume_reason" (one short sentence), '
        '"ai_maturity" (integer 1-5), "ai_maturity_reason", '
        '"stage_fit" (integer 1-5), "stage_fit_reason", '
        '"channel_breadth" (integer 1-5), "channel_breadth_reason", '
        '"justification" (one sentence summarizing why the total makes sense), '
        '"supporting_indices" (array of at least 1 integer, 1-based, drawn from '
        "the numbered justifications you were given). You MUST include at least one "
        "index in supporting_indices, even if your verdict is weak. If the context "
        "is so thin that nothing supports the verdict, return the index of the "
        "justification you found least useful and explain in the justification "
        "field that the evidence was insufficient. Empty supporting_indices is "
        "not allowed.\n\n"
        "Use only the provided context, do not invent facts. Be conservative when "
        "context is thin; default to 2 (low) rather than guessing high."
    )


class Scorer:
    def __init__(self, llm: LLMClient, config: ICPConfig | None = None) -> None:
        self._llm = llm
        self._config = config or get_config()

    async def score(self, enrichment: Enrichment) -> ICPScore | None:
        cached = _build_score_context(enrichment)
        result = await self._llm.synthesize(
            system=_build_score_system(self._config),
            context=cached,
            user_prompt=(
                "Return the ICP rubric JSON for this account. Be conservative when the "
                "context is thin. Cite supporting justifications by their numbered index."
            ),
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("score: could not parse JSON from %r", result.text[:200])
            return None
        try:
            breakdown = RubricBreakdown(
                support_volume=clip_score(parsed.get("support_volume")),
                ai_maturity=clip_score(parsed.get("ai_maturity")),
                stage_fit=clip_score(parsed.get("stage_fit")),
                channel_breadth=clip_score(parsed.get("channel_breadth")),
                support_volume_reason=str(parsed.get("support_volume_reason") or "").strip()
                or "(no reason given)",
                ai_maturity_reason=str(parsed.get("ai_maturity_reason") or "").strip()
                or "(no reason given)",
                stage_fit_reason=str(parsed.get("stage_fit_reason") or "").strip()
                or "(no reason given)",
                channel_breadth_reason=str(parsed.get("channel_breadth_reason") or "").strip()
                or "(no reason given)",
            )
        except (TypeError, ValueError) as exc:
            log.warning("score: rubric validation failed: %s", exc)
            return None
        total = compute_total(breakdown, self._config)
        verdict = self._config.verdict_for(total)
        justification = (
            str(parsed.get("justification") or "").strip()
            or f"Weighted total {total} ({verdict.label})."
        )
        supporting = parse_indices(
            parsed.get("supporting_indices"),
            {j.index for j in enrichment.justifications},
        )
        return ICPScore(
            total=total,
            breakdown=breakdown,
            justification=justification,
            verdict=verdict.label,
            supporting_indices=supporting,
        )


def compute_total(breakdown: RubricBreakdown, config: ICPConfig | None = None) -> float:
    cfg = config or get_config()
    weights = {name: axis.weight for name, axis in cfg.axes.items()}
    raw = (
        breakdown.support_volume * weights["support_volume"]
        + breakdown.ai_maturity * weights["ai_maturity"]
        + breakdown.stage_fit * weights["stage_fit"]
        + breakdown.channel_breadth * weights["channel_breadth"]
    )
    return round(raw, 1)


def _build_score_context(enrichment: Enrichment) -> str:
    lines = [
        f"<account>{enrichment.account.domain}</account>",
        "<firmographics>",
    ]
    f = enrichment.firmographics
    if f is None:
        lines.append("(no firmographics available)")
    else:
        lines.append(f"name: {f.name}")
        lines.append(f"industry: {f.industry or 'unknown'}")
        lines.append(f"headcount: {f.headcount_range or 'unknown'}")
        if f.tech_signals:
            lines.append(f"tech_signals: {', '.join(f.tech_signals)}")
    lines.append("</firmographics>")

    lines.append("<justifications>")
    for j in enrichment.justifications[:10]:
        lines.append(f"[{j.index}] {j.summary} (source: {j.citation.url})")
    lines.append("</justifications>")
    return "\n".join(lines)

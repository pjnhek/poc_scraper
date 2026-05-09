from __future__ import annotations

import logging
from typing import Final

from ._json_utils import parse_json_object
from .clients.protocols import AnthropicLike
from .models import Enrichment, ICPScore, NewsItem, RubricBreakdown

log = logging.getLogger(__name__)

WEIGHTS: Final[dict[str, float]] = {
    "support_volume": 0.40,
    "ai_maturity": 0.30,
    "stage_fit": 0.20,
    "channel_breadth": 0.10,
}

SCORE_SYSTEM = (
    "You score companies against Acme's ICP rubric. Acme sells AI customer-support "
    "agents (chat, voice, email, SMS). Their best customers are B2C with high support "
    "volume (Cash App, Chime, Duolingo, Oura, Hertz) and B2B SaaS with consumer-like "
    "support load (Notion, Webflow, Rippling). Output ONLY one JSON object with keys: "
    '"support_volume" (0-10), "support_volume_reason" (one short sentence), '
    '"ai_maturity" (0-10), "ai_maturity_reason", '
    '"stage_fit" (0-10), "stage_fit_reason", '
    '"channel_breadth" (0-10), "channel_breadth_reason", '
    '"justification" (one sentence summarizing why the total score makes sense). '
    "Use only the provided context, do not invent facts."
)


class Scorer:
    def __init__(self, anthropic: AnthropicLike) -> None:
        self._anthropic = anthropic

    async def score(self, enrichment: Enrichment) -> ICPScore | None:
        cached = _build_score_context(enrichment)
        result = await self._anthropic.synthesize(
            system=SCORE_SYSTEM,
            cached_context=cached,
            user_prompt=(
                "Return the ICP rubric JSON for this account. Be conservative when the "
                "context is thin."
            ),
            max_tokens=600,
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("score: could not parse JSON from %r", result.text[:200])
            return None
        try:
            breakdown = RubricBreakdown(
                support_volume=_clip(parsed.get("support_volume")),
                ai_maturity=_clip(parsed.get("ai_maturity")),
                stage_fit=_clip(parsed.get("stage_fit")),
                channel_breadth=_clip(parsed.get("channel_breadth")),
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
        total = compute_total(breakdown)
        justification = (
            str(parsed.get("justification") or "").strip()
            or f"Weighted total {total} from rubric breakdown."
        )
        return ICPScore(total=total, breakdown=breakdown, justification=justification)


def compute_total(breakdown: RubricBreakdown) -> float:
    raw = (
        breakdown.support_volume * WEIGHTS["support_volume"]
        + breakdown.ai_maturity * WEIGHTS["ai_maturity"]
        + breakdown.stage_fit * WEIGHTS["stage_fit"]
        + breakdown.channel_breadth * WEIGHTS["channel_breadth"]
    )
    return round(raw, 1)


def _clip(value: object) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, f))


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

    lines.append("<news>")
    for item in enrichment.news[:10]:
        lines.append(_format_news(item))
    lines.append("</news>")
    return "\n".join(lines)


def _format_news(item: NewsItem) -> str:
    return f"- [{item.headline}]({item.citation.url}) {item.summary}"

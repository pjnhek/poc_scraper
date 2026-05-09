from __future__ import annotations

import logging
from collections.abc import Iterable

from src._json_utils import parse_json_object
from src.clients.protocols import AnthropicLike
from src.models import EvalScore, OutreachHook, ScoredAccount

log = logging.getLogger(__name__)

EVAL_SYSTEM = (
    "You are an LLM-as-judge evaluating outreach copy from a Acme seller. Score the "
    'paragraph 0-10 on three axes: (1) "groundedness": every factual claim is supported '
    "by one of the cited URLs (10 = fully grounded, 0 = hallucinated); "
    '(2) "icp_relevance": the message reflects Acme\'s ICP (B2C with high support '
    "volume, AI-mature companies seeking deflection); "
    '(3) "personalization": the message references something specific to this account, '
    "not generic boilerplate. Output ONLY one JSON object with keys "
    '"groundedness", "icp_relevance", "personalization", and "notes" (one short sentence).'
)


class EvalRubric:
    def __init__(self, anthropic: AnthropicLike) -> None:
        self._anthropic = anthropic

    async def evaluate_hook(self, hook: OutreachHook, account_domain: str) -> EvalScore:
        cached = _build_eval_context(hook, account_domain)
        result = await self._anthropic.synthesize(
            system=EVAL_SYSTEM,
            cached_context=cached,
            user_prompt="Score the outreach paragraph and return the JSON object.",
            max_tokens=400,
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("eval: could not parse JSON from %r", result.text[:200])
            return EvalScore(
                groundedness=0,
                icp_relevance=0,
                personalization=0,
                notes="(judge output unparseable)",
            )
        try:
            return EvalScore(
                groundedness=_clip(parsed.get("groundedness")),
                icp_relevance=_clip(parsed.get("icp_relevance")),
                personalization=_clip(parsed.get("personalization")),
                notes=str(parsed.get("notes") or "").strip() or None,
            )
        except (TypeError, ValueError) as exc:
            log.warning("eval: validation failed: %s", exc)
            return EvalScore(
                groundedness=0,
                icp_relevance=0,
                personalization=0,
                notes=f"(validation failed: {exc})",
            )

    async def evaluate_account(self, sa: ScoredAccount) -> EvalScore:
        if not sa.hooks:
            return EvalScore(
                groundedness=0,
                icp_relevance=0,
                personalization=0,
                notes="(no hooks to evaluate)",
            )
        scores = [await self.evaluate_hook(h, sa.account.domain) for h in sa.hooks if h.paragraph]
        if not scores:
            return EvalScore(
                groundedness=0,
                icp_relevance=0,
                personalization=0,
                notes="(no grounded hooks)",
            )
        return EvalScore(
            groundedness=_avg(s.groundedness for s in scores),
            icp_relevance=_avg(s.icp_relevance for s in scores),
            personalization=_avg(s.personalization for s in scores),
            notes=f"averaged across {len(scores)} hooks",
        )


def _build_eval_context(hook: OutreachHook, domain: str) -> str:
    lines = [
        f"<account>{domain}</account>",
        f"<contact>{hook.contact.role_title}</contact>",
        "<citations>",
    ]
    for c in hook.citations:
        lines.append(f"- {c.url} (snippet: {(c.snippet or '')[:200]})")
    lines.append("</citations>")
    lines.append(f"<paragraph>{hook.paragraph}</paragraph>")
    return "\n".join(lines)


def _clip(value: object) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, f))


def _avg(values: Iterable[float]) -> float:
    nums = list(values)
    if not nums:
        return 0.0
    return round(sum(nums) / len(nums), 1)

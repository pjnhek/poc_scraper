from __future__ import annotations

import logging
from collections.abc import Iterable

from src._json_utils import parse_json_object
from src.clients.protocols import AnthropicLike
from src.icp_config import ICPConfig, get_config
from src.models import EvalScore, OutreachHook, ScoredAccount

log = logging.getLogger(__name__)


def _build_eval_system(config: ICPConfig) -> str:
    return (
        "You are an LLM judge evaluating an outreach paragraph against a target account.\n"
        f"Buyer description (use this for the ICP-relevance axis): "
        f"{config.buyer_description.strip()}\n\n"
        "Score the paragraph on three axes using a 1-5 categorical scale:\n"
        "1. groundedness: every factual claim about the account is supported by one of "
        "the cited URLs (5 = fully grounded, 1 = hallucinated).\n"
        "2. icp_relevance: how well the message reflects the buyer description above.\n"
        "3. personalization: the message references something specific to this account "
        "rather than generic boilerplate.\n\n"
        "Anchors per axis: 1 = poor, 2 = fair, 3 = acceptable, 4 = strong, 5 = excellent.\n"
        "Output ONLY one JSON object with integer keys "
        '"groundedness", "icp_relevance", "personalization", and "notes" '
        "(one short sentence). Do not include any other prose."
    )


class EvalRubric:
    def __init__(self, anthropic: AnthropicLike, config: ICPConfig | None = None) -> None:
        self._anthropic = anthropic
        self._config = config or get_config()

    @property
    def _flag_threshold(self) -> float:
        return self._config.eval.groundedness_flag_threshold

    async def evaluate_hook(self, hook: OutreachHook, account_domain: str) -> EvalScore:
        cached = _build_eval_context(hook, account_domain)
        result = await self._anthropic.synthesize(
            system=_build_eval_system(self._config),
            cached_context=cached,
            user_prompt="Score the outreach paragraph and return the JSON object.",
            max_tokens=400,
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("eval: could not parse JSON from %r", result.text[:200])
            return EvalScore(
                groundedness=1,
                icp_relevance=1,
                personalization=1,
                notes="(judge output unparseable)",
                flag_threshold=self._flag_threshold,
            )
        try:
            return EvalScore(
                groundedness=_clip(parsed.get("groundedness")),
                icp_relevance=_clip(parsed.get("icp_relevance")),
                personalization=_clip(parsed.get("personalization")),
                notes=str(parsed.get("notes") or "").strip() or None,
                flag_threshold=self._flag_threshold,
            )
        except (TypeError, ValueError) as exc:
            log.warning("eval: validation failed: %s", exc)
            return EvalScore(
                groundedness=1,
                icp_relevance=1,
                personalization=1,
                notes=f"(validation failed: {exc})",
                flag_threshold=self._flag_threshold,
            )

    async def evaluate_account(self, sa: ScoredAccount) -> EvalScore:
        if not sa.hooks:
            return EvalScore(
                groundedness=1,
                icp_relevance=1,
                personalization=1,
                notes="(no hooks to evaluate)",
                flag_threshold=self._flag_threshold,
            )
        scores = [await self.evaluate_hook(h, sa.account.domain) for h in sa.hooks if h.paragraph]
        if not scores:
            return EvalScore(
                groundedness=1,
                icp_relevance=1,
                personalization=1,
                notes="(no grounded hooks)",
                flag_threshold=self._flag_threshold,
            )
        return EvalScore(
            groundedness=_avg(s.groundedness for s in scores),
            icp_relevance=_avg(s.icp_relevance for s in scores),
            personalization=_avg(s.personalization for s in scores),
            notes=f"averaged across {len(scores)} hooks",
            flag_threshold=self._flag_threshold,
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
        return 1.0
    return max(1.0, min(5.0, f))


def _avg(values: Iterable[float]) -> float:
    nums = list(values)
    if not nums:
        return 1.0
    return round(sum(nums) / len(nums), 1)

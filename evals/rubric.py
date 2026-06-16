from __future__ import annotations

import logging
from collections.abc import Iterable

from src._json_utils import clip_score, parse_json_object
from src.citations import INDEX_MARKER_RE  # noqa: F401 — consolidates marker pattern (CHANGE-01)
from src.clients.protocols import LLMClient
from src.icp_config import ICPConfig, get_config
from src.models import EvalScore, Justification, OutreachHook, ScoredAccount

log = logging.getLogger(__name__)


def _build_eval_system(config: ICPConfig) -> str:
    return (
        "You are an LLM judge evaluating an outreach paragraph against a target "
        "account.\n"
        f"Buyer description (use this for the ICP-relevance axis): "
        f"{config.buyer_description.strip()}\n\n"
        "The user message will give you:\n"
        "1. A numbered list of justifications (the only evidence the writer was "
        "given).\n"
        "2. The indices the writer claims to have cited.\n"
        "3. The outreach paragraph.\n\n"
        "Your job is to decompose the paragraph into atomic factual claims about "
        "the account, then for each claim mark which justification supports it "
        "(by 1-based index) or 'uncited' if no justification supports it.\n\n"
        "A claim is 'supported_by': [index] when the listed justification's text "
        "actually contains the fact being claimed (paraphrasing is fine; making "
        "up new numbers or facts is not).\n\n"
        "Also score icp_relevance, personalization, specificity, and recency on a "
        "1-5 scale (1 poor, 5 excellent). Do NOT score groundedness yourself; it "
        "will be derived from your claims array.\n\n"
        "Output ONLY one JSON object with these keys:\n"
        '"claims": array of {"text": str, "supported_by": int | "uncited"},\n'
        '"icp_relevance": int 1-5,\n'
        '"personalization": int 1-5,\n'
        '"specificity": int 1-5 (1 = generic claim could apply to any company, '
        "5 = highly specific facts unique to this account),\n"
        '"recency": int 1-5 (1 = no recent evidence cited, '
        "5 = multiple recent-news citations),\n"
        '"notes": one short sentence (quote the most-uncited claim if any).\n'
        "Do not include any other prose."
    )


class EvalRubric:
    def __init__(self, llm: LLMClient, config: ICPConfig | None = None) -> None:
        self._llm = llm
        self._config = config or get_config()

    @property
    def _flag_threshold(self) -> float:
        return self._config.eval.groundedness_flag_threshold

    async def evaluate_hook(
        self,
        hook: OutreachHook,
        account_domain: str,
        justifications: tuple[Justification, ...] = (),
    ) -> EvalScore:
        cached = _build_eval_context(hook, account_domain, justifications)
        result = await self._llm.synthesize(
            system=_build_eval_system(self._config),
            context=cached,
            user_prompt=(
                "Decompose the paragraph into atomic factual claims, mark each as "
                "supported_by an index from the numbered justifications or "
                "'uncited', then score icp_relevance and personalization. "
                "Return the JSON object."
            ),
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("eval: could not parse JSON from %r", result.text[:200])
            return self._floor("(judge output unparseable)")

        claims = _parse_claims(parsed.get("claims"))
        groundedness = _compute_groundedness(claims)
        try:
            return EvalScore(
                groundedness=groundedness,
                icp_relevance=clip_score(parsed.get("icp_relevance")),
                personalization=clip_score(parsed.get("personalization")),
                specificity=clip_score(parsed.get("specificity")),
                recency=clip_score(parsed.get("recency")),
                eval_failed=False,
                notes=str(parsed.get("notes") or "").strip() or None,
                flag_threshold=self._flag_threshold,
            )
        except (TypeError, ValueError) as exc:
            log.warning("eval: validation failed: %s", exc)
            return self._floor(f"(validation failed: {exc})")

    async def evaluate_account(self, sa: ScoredAccount) -> EvalScore:
        if not sa.hooks:
            # No hooks means the outreach stage produced nothing; this is content
            # suppression, not a judge failure, so eval_failed stays False.
            return self._no_content_floor("(no hooks to evaluate)")
        scores = [
            await self.evaluate_hook(h, sa.account.domain, sa.enrichment.justifications)
            for h in sa.hooks
            if h.paragraph
        ]
        if not scores:
            # All hooks had empty paragraphs (rapidfuzz gate suppressed everything);
            # again content suppression, not a judge failure.
            return self._no_content_floor("(no grounded hooks)")
        # eval_failed propagates up: if any hook's judge call failed, the
        # account-level score must carry eval_failed=True so D-03 precedence
        # in pipeline.py can assign judge_failed status.
        any_failed = any(s.eval_failed for s in scores)
        return EvalScore(
            groundedness=_avg(s.groundedness for s in scores),
            icp_relevance=_avg(s.icp_relevance for s in scores),
            personalization=_avg(s.personalization for s in scores),
            specificity=_avg(s.specificity for s in scores),
            recency=_avg(s.recency for s in scores),
            eval_failed=any_failed,
            notes=f"averaged across {len(scores)} hooks",
            flag_threshold=self._flag_threshold,
        )

    def _floor(self, note: str) -> EvalScore:
        """Judge API failure: unparseable output or validation error.

        Sets eval_failed=True so D-03 precedence assigns judge_failed status.
        """
        return EvalScore(
            groundedness=1,
            icp_relevance=1,
            personalization=1,
            specificity=1,
            recency=1,
            eval_failed=True,
            notes=note,
            flag_threshold=self._flag_threshold,
        )

    def _no_content_floor(self, note: str) -> EvalScore:
        """No content available to evaluate (empty hooks or all-suppressed).

        eval_failed=False because the judge was not invoked; this is content
        suppression, not a judge-side failure.
        """
        return EvalScore(
            groundedness=1,
            icp_relevance=1,
            personalization=1,
            specificity=1,
            recency=1,
            eval_failed=False,
            notes=note,
            flag_threshold=self._flag_threshold,
        )


def _build_eval_context(
    hook: OutreachHook,
    domain: str,
    justifications: tuple[Justification, ...],
) -> str:
    lines = [
        f"<account>{domain}</account>",
        f"<contact>{hook.contact.role_title}</contact>",
        "<justifications>",
    ]
    for j in justifications:
        lines.append(f"[{j.index}] {j.summary} (source: {j.citation.url})")
    lines.append("</justifications>")
    lines.append(f"<cited_indices>{', '.join(str(i) for i in hook.cited_indices)}</cited_indices>")
    lines.append(f"<paragraph>{hook.paragraph}</paragraph>")
    return "\n".join(lines)


def _parse_claims(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, object]] = []
    for item in raw:
        if isinstance(item, dict) and "text" in item:
            out.append(item)
    return out


def _compute_groundedness(claims: list[dict[str, object]]) -> float:
    """`(cited / max(total, 3)) * 5`, rounded to 1 decimal.

    The `max(total, 3)` floor penalizes short hooks: a 1-claim hook with 1
    citation can only score 5/3 ≈ 1.7, not 5.0. Forces the writer to
    actually back up the value prop, not just drop one citation and stop.
    """
    if not claims:
        return 1.0
    total = len(claims)
    cited = sum(1 for c in claims if isinstance(c.get("supported_by"), int))
    raw = (cited / max(total, 3)) * 5
    return round(max(1.0, min(5.0, raw)), 1)


def _avg(values: Iterable[float]) -> float:
    nums = list(values)
    if not nums:
        return 1.0
    return round(sum(nums) / len(nums), 1)

from __future__ import annotations

import logging

from ._json_utils import parse_json_object
from .citations import assemble_paragraph
from .clients.protocols import LLMClient
from .icp_config import ICPConfig, get_config
from .models import Contact, Enrichment, ICPScore, Justification, OutreachHook

log = logging.getLogger(__name__)


def _build_outreach_system(config: ICPConfig) -> str:
    return (
        "You write outreach claims from a seller to a specific persona at a target account.\n"
        f"Seller description: {config.seller_description.strip()}\n\n"
        "The user message will provide a numbered list of justifications drawn from "
        "Exa retrievals (about pages and recent news). EVERY factual claim about the "
        "account must be supported by one of those numbered justifications. "
        "Do not invent claims.\n\n"
        "Output ONLY one JSON object with keys:\n"
        '"claims": array of {"claim": string, "cited_indices": array of 1-based integer indices}\n'
        '"connective_text": short transitional text (1-2 sentences, no factual claims, no [N] markers)\n'
        "Each claim object makes exactly one factual assertion about the account and cites "
        "the justification indices that support it. Non-factual connective sentences go in "
        '"connective_text". End connective_text with a soft, specific ask to connect. '
        'If the context is too thin, return an empty "claims" array and empty "connective_text".'
    )


class OutreachGenerator:
    def __init__(self, llm: LLMClient, config: ICPConfig | None = None) -> None:
        self._llm = llm
        self._config = config or get_config()

    async def generate(
        self,
        contact: Contact,
        enrichment: Enrichment,
        score: ICPScore | None,
    ) -> OutreachHook:
        cached = _build_outreach_context(enrichment, score)
        user = (
            f"Write the outreach paragraph for the persona: {contact.role_title}. "
            f"Persona rationale: {contact.rationale}. "
            "Use [N] markers to cite the numbered justifications above; do not include "
            "raw URLs in the paragraph."
        )
        result = await self._llm.synthesize(
            system=_build_outreach_system(self._config),
            context=cached,
            user_prompt=user,
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("outreach: could not parse JSON from %r", result.text[:200])
            return OutreachHook(contact=contact, paragraph="", cited_indices=())

        raw_claims = parsed.get("claims") or []
        connective = str(parsed.get("connective_text") or "").strip()
        paragraph, cited_indices = assemble_paragraph(
            raw_claims=raw_claims if isinstance(raw_claims, list) else [],
            connective_text=connective,
            justifications=enrichment.justifications,
            threshold_01=self._config.eval.groundedness_suppress_threshold,
        )
        return OutreachHook(contact=contact, paragraph=paragraph, cited_indices=cited_indices)


def _build_outreach_context(enrichment: Enrichment, score: ICPScore | None) -> str:
    lines = [f"<account>{enrichment.account.domain}</account>"]
    f = enrichment.firmographics
    if f is not None:
        lines.append("<firmographics>")
        lines.append(f"name: {f.name}")
        lines.append(f"industry: {f.industry or 'unknown'}")
        lines.append(f"headcount: {f.headcount_range or 'unknown'}")
        lines.append("</firmographics>")

    if score is not None:
        lines.append(
            f"<icp_score>total={score.total}; verdict={score.verdict}; "
            f"support_volume={score.breakdown.support_volume}/5 "
            f"({score.breakdown.support_volume_reason}); "
            f"ai_maturity={score.breakdown.ai_maturity}/5 "
            f"({score.breakdown.ai_maturity_reason})</icp_score>"
        )

    lines.append("<justifications>")
    for j in enrichment.justifications[:10]:
        lines.append(_format_justification(j))
    lines.append("</justifications>")
    return "\n".join(lines)


def _format_justification(j: Justification) -> str:
    return f"[{j.index}] {j.summary} (source: {j.citation.url})"

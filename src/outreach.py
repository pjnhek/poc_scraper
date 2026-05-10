from __future__ import annotations

import logging
import re

from ._json_utils import parse_json_object
from .clients.protocols import LLMClient
from .icp_config import ICPConfig, get_config
from .models import Contact, Enrichment, ICPScore, Justification, OutreachHook

log = logging.getLogger(__name__)


def _build_outreach_system(config: ICPConfig) -> str:
    return (
        "You write one short outreach paragraph (3-5 sentences) from a seller to a "
        "specific persona at a target account.\n"
        f"Seller description: {config.seller_description.strip()}\n\n"
        "The user message will provide a numbered list of justifications drawn from "
        "Exa retrievals (about pages and recent news). EVERY factual claim about the "
        "account must be supported by one of those numbered justifications. Reference "
        'the supporting justification inline using [N] markers (e.g. "recent push on '
        'AI [2]"). Do not paste raw URLs into the paragraph; do not invent claims.\n\n'
        "End with a soft, specific ask to connect. "
        "Output ONLY one JSON object with keys: "
        '"paragraph" (string with [N] markers, no raw URLs) and '
        '"cited_justifications" (array of 1-based integer indices you actually used). '
        "If the context is too thin to ground at least one claim, return an empty "
        '"paragraph" and an empty "cited_justifications".'
    )


# [1], [2,3], [1, 4] — tolerate optional whitespace and comma-separated lists.
INDEX_MARKER_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
# Strip raw URLs the writer shouldn't have included anyway.
URL_RE = re.compile(r"\(?https?://\S+\)?")


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

        paragraph = str(parsed.get("paragraph") or "").strip()
        valid_indices = {j.index for j in enrichment.justifications}
        claimed = _parse_indices(parsed.get("cited_justifications"), valid_indices)

        # Cross-check: only count indices the writer actually marked in the paragraph.
        marked = _markers_in_paragraph(paragraph, valid_indices)
        cited = tuple(i for i in claimed if i in marked)

        if not cited:
            log.info(
                "outreach: no valid [N] markers for %s, dropping paragraph",
                contact.role_title,
            )
            return OutreachHook(contact=contact, paragraph="", cited_indices=())

        cleaned = URL_RE.sub("", paragraph).strip()
        return OutreachHook(contact=contact, paragraph=cleaned, cited_indices=cited)


def _parse_indices(raw: object, valid: set[int]) -> tuple[int, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[int] = []
    for v in raw:
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        if i in valid and i not in out:
            out.append(i)
    return tuple(out)


def _markers_in_paragraph(paragraph: str, valid: set[int]) -> set[int]:
    found: set[int] = set()
    for match in INDEX_MARKER_RE.finditer(paragraph):
        for piece in match.group(1).split(","):
            try:
                n = int(piece.strip())
            except ValueError:
                continue
            if n in valid:
                found.add(n)
    return found


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

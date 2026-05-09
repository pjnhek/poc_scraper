from __future__ import annotations

import logging
import re

from ._json_utils import parse_json_object
from .clients.protocols import LLMClient
from .models import Citation, Contact, Enrichment, ICPScore, OutreachHook

log = logging.getLogger(__name__)

OUTREACH_SYSTEM = (
    "You write one short outreach paragraph (3-5 sentences) from a Acme seller to a "
    "specific persona at a target account. EVERY factual claim about the account must "
    "come from the provided <news> or <firmographics> blocks; do not invent or "
    "extrapolate. Reference each fact by its citation URL inline using markdown like "
    "[fact](url). End with a soft, specific ask to connect. Output ONLY one JSON object "
    'with keys "paragraph" (string) and "cited_urls" (array of strings, every URL you '
    "actually used). If the context is too thin to ground at least one claim, return "
    "an empty paragraph and an empty cited_urls."
)

URL_RE = re.compile(r"\((https?://[^)]+)\)")


class OutreachGenerator:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def generate(
        self,
        contact: Contact,
        enrichment: Enrichment,
        score: ICPScore | None,
    ) -> OutreachHook:
        cached = _build_outreach_context(enrichment, score)
        user = (
            f"Write the outreach paragraph for the persona: {contact.role_title}. "
            f"Persona rationale: {contact.rationale}"
        )
        result = await self._llm.synthesize(
            system=OUTREACH_SYSTEM,
            cached_context=cached,
            user_prompt=user,
            max_tokens=600,
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("outreach: could not parse JSON from %r", result.text[:200])
            return OutreachHook(contact=contact, paragraph="", citations=())

        paragraph = str(parsed.get("paragraph") or "").strip()
        raw_urls = parsed.get("cited_urls") or []
        cited_urls: list[str] = (
            [str(u) for u in raw_urls if isinstance(u, str)] if isinstance(raw_urls, list) else []
        )

        allowed = _allowed_urls(enrichment)
        valid_citations = _validate_citations(cited_urls, allowed)
        if not valid_citations:
            log.info("outreach: no valid citations for %s, dropping paragraph", contact.role_title)
            return OutreachHook(contact=contact, paragraph="", citations=())

        cleaned = _strip_uncited_urls(paragraph, {str(c.url) for c in valid_citations})
        return OutreachHook(contact=contact, paragraph=cleaned, citations=tuple(valid_citations))


def _allowed_urls(enrichment: Enrichment) -> dict[str, Citation]:
    allowed: dict[str, Citation] = {}
    if enrichment.firmographics is not None:
        for c in enrichment.firmographics.citations:
            allowed[str(c.url)] = c
    for n in enrichment.news:
        allowed[str(n.citation.url)] = n.citation
    return allowed


def _validate_citations(urls: list[str], allowed: dict[str, Citation]) -> list[Citation]:
    out: list[Citation] = []
    for u in urls:
        canonical = _canonical(u)
        for allowed_url, cit in allowed.items():
            if _canonical(allowed_url) == canonical:
                out.append(cit)
                break
    return out


def _canonical(u: str) -> str:
    return u.rstrip("/").lower()


def _strip_uncited_urls(paragraph: str, allowed_urls: set[str]) -> str:
    canonical_allowed = {_canonical(u) for u in allowed_urls}

    def _replace(match: re.Match[str]) -> str:
        url = match.group(1)
        if _canonical(url) in canonical_allowed:
            return match.group(0)
        return ""

    return URL_RE.sub(_replace, paragraph)


def _build_outreach_context(enrichment: Enrichment, score: ICPScore | None) -> str:
    lines = [f"<account>{enrichment.account.domain}</account>"]
    f = enrichment.firmographics
    if f is not None:
        lines.append("<firmographics>")
        lines.append(f"name: {f.name}")
        lines.append(f"industry: {f.industry or 'unknown'}")
        lines.append(f"headcount: {f.headcount_range or 'unknown'}")
        if f.citations:
            lines.append("citations: " + ", ".join(str(c.url) for c in f.citations))
        lines.append("</firmographics>")

    if score is not None:
        lines.append(
            f"<icp_score>total={score.total}; verdict={score.verdict}; "
            f"support_volume={score.breakdown.support_volume}/5 "
            f"({score.breakdown.support_volume_reason}); "
            f"ai_maturity={score.breakdown.ai_maturity}/5 "
            f"({score.breakdown.ai_maturity_reason})</icp_score>"
        )

    lines.append("<news>")
    for n in enrichment.news[:8]:
        lines.append(f"- [{n.headline}]({n.citation.url}) {n.summary[:300]}")
    lines.append("</news>")
    return "\n".join(lines)

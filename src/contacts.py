from __future__ import annotations

import logging

from ._json_utils import parse_json_array
from .clients.protocols import LLMClient
from .icp_config import ICPConfig, get_config
from .models import Contact, Enrichment, ICPScore

log = logging.getLogger(__name__)


def _build_contacts_system(config: ICPConfig) -> str:
    return (
        "You propose the top 3 buyer personas (job titles) inside the target company "
        "who would be the right point of contact for the seller described below.\n"
        f"Seller description: {config.seller_description.strip()}\n"
        f"Buyer description (target account profile): {config.buyer_description.strip()}\n\n"
        "Output ONLY a JSON array of exactly 3 objects, each with keys "
        '"role_title" (string, e.g. "Head of Operations") and "rationale" '
        "(one short sentence grounded in the provided context, naming what makes this role "
        "the right reach for this account). Do not invent specific people."
    )


DEFAULT_RATIONALE = "(no rationale provided)"


class ContactExtractor:
    def __init__(self, llm: LLMClient, config: ICPConfig | None = None) -> None:
        self._llm = llm
        self._config = config or get_config()

    async def extract(self, enrichment: Enrichment, score: ICPScore | None) -> tuple[Contact, ...]:
        cached = _build_contacts_context(enrichment, score)
        result = await self._llm.synthesize(
            system=_build_contacts_system(self._config),
            context=cached,
            user_prompt="Return the JSON array of three personas.",
        )
        items = parse_json_array(result.text)
        if items is None:
            log.warning("contacts: could not parse array from %r", result.text[:200])
            return tuple(_default_contacts(self._config))
        return tuple(_to_contacts(items, self._config))


def _to_contacts(items: list[dict[str, object]], config: ICPConfig) -> list[Contact]:
    contacts: list[Contact] = []
    for entry in items[:3]:
        role = str(entry.get("role_title") or "").strip()
        if not role:
            continue
        rationale = str(entry.get("rationale") or "").strip() or DEFAULT_RATIONALE
        contacts.append(Contact(role_title=role, rationale=rationale))
    while len(contacts) < 3:
        contacts.append(_default_contacts(config)[len(contacts)])
    return contacts


def _default_contacts(config: ICPConfig) -> list[Contact]:
    return [
        Contact(role_title=p.role_title, rationale=p.rationale or DEFAULT_RATIONALE)
        for p in config.default_personas
    ]


def _build_contacts_context(enrichment: Enrichment, score: ICPScore | None) -> str:
    lines = [f"<account>{enrichment.account.domain}</account>"]
    f = enrichment.firmographics
    if f is not None:
        lines.append(
            f"<firmographics>name={f.name}; industry={f.industry or 'unknown'}; "
            f"headcount={f.headcount_range or 'unknown'}</firmographics>"
        )
    if score is not None:
        lines.append(
            f"<icp_score>total={score.total}; verdict={score.verdict}; "
            f"support_volume={score.breakdown.support_volume}; "
            f"ai_maturity={score.breakdown.ai_maturity}</icp_score>"
        )
    lines.append("<news>")
    for item in enrichment.news[:6]:
        lines.append(f"- {item.headline}: {item.summary[:200]}")
    lines.append("</news>")
    return "\n".join(lines)

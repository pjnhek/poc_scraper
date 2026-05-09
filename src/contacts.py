from __future__ import annotations

import logging

from ._json_utils import parse_json_object
from .clients.protocols import AnthropicLike
from .models import Contact, Enrichment, ICPScore

log = logging.getLogger(__name__)

CONTACTS_SYSTEM = (
    "You propose the top 3 buyer personas (job titles) inside a B2C-heavy company that "
    "would be the right point of contact for Acme, an AI customer-support agent "
    "platform. The buyer cares about deflection rate, support cost reduction, and CX "
    "quality. Output ONLY a JSON array of exactly 3 objects, each with keys "
    '"role_title" (string, e.g. "VP Customer Experience") and "rationale" '
    "(one short sentence grounded in the provided context, naming what makes this role "
    "the right reach for this account). Do not invent specific people."
)

DEFAULT_RATIONALE = "(no rationale provided)"


class ContactExtractor:
    def __init__(self, anthropic: AnthropicLike) -> None:
        self._anthropic = anthropic

    async def extract(self, enrichment: Enrichment, score: ICPScore | None) -> tuple[Contact, ...]:
        cached = _build_contacts_context(enrichment, score)
        result = await self._anthropic.synthesize(
            system=CONTACTS_SYSTEM,
            cached_context=cached,
            user_prompt="Return the JSON array of three personas.",
            max_tokens=400,
        )
        items = _parse_contacts_array(result.text)
        if items is None:
            log.warning("contacts: could not parse array from %r", result.text[:200])
            return tuple(_default_contacts())
        return tuple(_to_contacts(items))


def _to_contacts(items: list[dict[str, object]]) -> list[Contact]:
    contacts: list[Contact] = []
    for entry in items[:3]:
        role = str(entry.get("role_title") or "").strip()
        if not role:
            continue
        rationale = str(entry.get("rationale") or "").strip() or DEFAULT_RATIONALE
        contacts.append(Contact(role_title=role, rationale=rationale))
    while len(contacts) < 3:
        contacts.append(_default_contacts()[len(contacts)])
    return contacts


def _default_contacts() -> list[Contact]:
    return [
        Contact(role_title="VP Customer Experience", rationale=DEFAULT_RATIONALE),
        Contact(role_title="Head of Support Operations", rationale=DEFAULT_RATIONALE),
        Contact(role_title="Director of CX Automation", rationale=DEFAULT_RATIONALE),
    ]


def _parse_contacts_array(text: str) -> list[dict[str, object]] | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        wrapped = parse_json_object(text)
        if wrapped is None:
            return None
        for value in wrapped.values():
            if isinstance(value, list):
                return [v for v in value if isinstance(v, dict)]
        return None
    import json

    try:
        loaded = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, list):
        return None
    return [v for v in loaded if isinstance(v, dict)]


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
            f"<icp_score>total={score.total}; "
            f"support_volume={score.breakdown.support_volume}; "
            f"ai_maturity={score.breakdown.ai_maturity}</icp_score>"
        )
    lines.append("<news>")
    for item in enrichment.news[:6]:
        lines.append(f"- {item.headline}: {item.summary[:200]}")
    lines.append("</news>")
    return "\n".join(lines)

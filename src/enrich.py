from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ._json_utils import parse_json_object
from .clients.exa_client import ExaResult
from .clients.protocols import BrowserbaseLike, ExaLike, LLMClient
from .models import Account, Citation, Enrichment, Firmographics, NewsItem

log = logging.getLogger(__name__)

ABOUT_TEXT_MIN_CHARS = 200
HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")

FIRMOGRAPHICS_SYSTEM = (
    "You are a sales analyst. From the provided company context, extract structured "
    "firmographics. Output ONLY a single JSON object with these exact keys: "
    '"name" (string), "industry" (string or null), "headcount_range" (string or null, '
    'e.g. "200-500"), "tech_signals" (array of short strings, e.g. ["zendesk","react"]). '
    "Do not invent data. If unsure, use null or an empty array."
)


@dataclass(frozen=True)
class _RawContext:
    about_text: str
    about_citations: list[Citation]
    news_items: list[NewsItem]


class Enricher:
    def __init__(
        self,
        exa: ExaLike,
        browserbase: BrowserbaseLike,
        llm: LLMClient,
    ) -> None:
        self._exa = exa
        self._browserbase = browserbase
        self._llm = llm

    async def enrich(self, account: Account) -> Enrichment:
        ctx = await self._collect_context(account)
        if not ctx.about_text and not ctx.news_items:
            return Enrichment(account=account, news=tuple(ctx.news_items))

        firmographics: Firmographics | None = None
        if ctx.about_text:
            firmographics = await self._extract_firmographics(ctx)

        return Enrichment(
            account=account,
            firmographics=firmographics,
            news=tuple(ctx.news_items),
        )

    async def _collect_context(self, account: Account) -> _RawContext:
        about_results = await self._exa.search_about(account.domain)
        about_text, about_citations = self._gather_about_text(about_results)

        if len(about_text) < ABOUT_TEXT_MIN_CHARS and about_results:
            rendered = await self._browserbase.render(about_results[0].url)
            if rendered is not None:
                stripped = _strip_html(rendered.html)
                if len(stripped) > len(about_text):
                    about_text = stripped[:6000]
                    if not any(str(c.url) == rendered.url for c in about_citations):
                        about_citations.append(
                            Citation.make(url=rendered.url, source="browserbase")
                        )

        news_results = await self._exa.search_news(account.domain)
        news_items = [_to_news_item(r) for r in news_results if r.snippet]

        return _RawContext(
            about_text=about_text,
            about_citations=about_citations,
            news_items=news_items,
        )

    def _gather_about_text(self, results: list[ExaResult]) -> tuple[str, list[Citation]]:
        chunks: list[str] = []
        citations: list[Citation] = []
        for r in results:
            if r.snippet:
                chunks.append(r.snippet)
                citations.append(Citation.make(url=r.url, title=r.title, source="exa"))
        return ("\n\n".join(chunks).strip(), citations)

    async def _extract_firmographics(self, ctx: _RawContext) -> Firmographics | None:
        cached_block = _build_context_block(ctx)
        result = await self._llm.synthesize(
            system=FIRMOGRAPHICS_SYSTEM,
            context=cached_block,
            user_prompt=(
                "Return the firmographics JSON for this company. "
                "If the context is insufficient for a field, use null or an empty array."
            ),
        )
        parsed = parse_json_object(result.text)
        if parsed is None:
            log.warning("firmographics extraction: could not parse JSON from %r", result.text[:200])
            return None
        try:
            raw_tech = parsed.get("tech_signals") or []
            tech_iter: list[object] = list(raw_tech) if isinstance(raw_tech, list) else []
            return Firmographics(
                name=str(parsed.get("name") or "").strip() or "(unknown)",
                industry=_clean_str(parsed.get("industry")),
                headcount_range=_clean_str(parsed.get("headcount_range")),
                tech_signals=tuple(str(t).strip() for t in tech_iter if str(t).strip()),
                citations=tuple(ctx.about_citations),
            )
        except (TypeError, ValueError) as exc:
            log.warning("firmographics validation failed: %s", exc)
            return None


def _build_context_block(ctx: _RawContext) -> str:
    lines = ["<about>", ctx.about_text, "</about>", "", "<news>"]
    for item in ctx.news_items:
        lines.append(f"- [{item.headline}]({item.citation.url}) {item.summary}")
    lines.append("</news>")
    return "\n".join(lines)


def _to_news_item(r: ExaResult) -> NewsItem:
    citation = Citation.make(
        url=r.url,
        source="exa",
        title=r.title,
        snippet=r.snippet,
        retrieved_at=r.published_at,
    )
    return NewsItem(
        headline=r.title or r.url,
        summary=(r.snippet or "")[:500],
        citation=citation,
        published_at=r.published_at,
    )


def _strip_html(html: str) -> str:
    text = HTML_TAG.sub(" ", html)
    return WHITESPACE.sub(" ", text).strip()


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None

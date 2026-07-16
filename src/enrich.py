from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ._json_utils import parse_json_object
from .clients.exa_client import ExaResult
from .clients.protocols import BrowserbaseLike, ExaLike, LLMClient
from .models import Account, Citation, Enrichment, Firmographics, Justification, NewsItem

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
class RawContext:
    about_text: str
    about_citations: list[Citation]
    news_items: list[NewsItem]


async def collect_context(
    account: Account, *, exa: ExaLike, browserbase: BrowserbaseLike
) -> RawContext:
    about_results = await exa.search_about(account.domain)
    about_text, about_citations = _gather_about_text(about_results)

    if len(about_text) < ABOUT_TEXT_MIN_CHARS and about_results:
        rendered = await browserbase.render(about_results[0].url)
        if rendered is not None:
            stripped = _strip_html(rendered.html)
            if len(stripped) > len(about_text):
                about_text = stripped[:6000]
                if not any(str(c.url) == rendered.url for c in about_citations):
                    about_citations.append(Citation.make(url=rendered.url, source="browserbase"))

    news_results = await exa.search_news(account.domain)
    news_items = [_to_news_item(r) for r in news_results if r.snippet]

    return RawContext(
        about_text=about_text,
        about_citations=about_citations,
        news_items=news_items,
    )


def _gather_about_text(results: list[ExaResult]) -> tuple[str, list[Citation]]:
    chunks: list[str] = []
    citations: list[Citation] = []
    for r in results:
        if r.snippet:
            chunks.append(r.snippet)
            citations.append(
                Citation.make(url=r.url, title=r.title, snippet=r.snippet, source="exa")
            )
    return ("\n\n".join(chunks).strip(), citations)


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
        ctx = await collect_context(account, exa=self._exa, browserbase=self._browserbase)
        if not ctx.about_text and not ctx.news_items:
            return Enrichment(account=account, news=tuple(ctx.news_items))

        firmographics: Firmographics | None = None
        if ctx.about_text:
            firmographics = await self._extract_firmographics(ctx)

        justifications = _number_justifications(ctx.about_citations, ctx.news_items)

        return Enrichment(
            account=account,
            firmographics=firmographics,
            news=tuple(ctx.news_items),
            justifications=justifications,
        )

    async def _extract_firmographics(self, ctx: RawContext) -> Firmographics | None:
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


def _number_justifications(
    about_citations: list[Citation],
    news_items: list[NewsItem],
) -> tuple[Justification, ...]:
    """Combine about-page citations and news into a single numbered list.

    About-page citations come first (they describe the company in general),
    then news items in retrieval order. URLs are deduped: if the same URL
    shows up in both lists, the about-page version wins because its snippet
    is usually the richer 2000-char company overview.
    """
    seen: set[str] = set()
    out: list[Justification] = []
    idx = 1

    for c in about_citations:
        url = _canonical(str(c.url))
        if url in seen:
            continue
        seen.add(url)
        # Prefer the title (e.g. "About Mercury | The art of simplified
        # finances") over the snippet, which is a noisy raw page dump
        # including logo descriptions and nav links.
        summary = _clean_summary(c.title) or _clean_summary(c.snippet) or "(no summary)"
        out.append(Justification(index=idx, summary=summary, citation=c))
        idx += 1

    for n in news_items:
        url = _canonical(str(n.citation.url))
        if url in seen:
            continue
        seen.add(url)
        # News retrievals already give us a clean headline; that's the right
        # cell-level summary. Snippet would balloon with article boilerplate.
        summary = _clean_summary(n.headline) or _clean_summary(n.summary) or "(no summary)"
        out.append(Justification(index=idx, summary=summary, citation=n.citation))
        idx += 1

    return tuple(out)


def _canonical(u: str) -> str:
    return u.rstrip("/").lower()


SUMMARY_MAX_CHARS = 140


def _clean_summary(text: str | None) -> str:
    """Collapse whitespace, drop markdown chrome, cap length for cell display."""
    if not text:
        return ""
    s = text.strip()
    # Strip leading markdown headings/list markers and pipe-separated nav crumbs
    # that Exa snippets often start with.
    s = WHITESPACE.sub(" ", s)
    s = s.replace("# ", "").replace("## ", "").strip()
    if len(s) <= SUMMARY_MAX_CHARS:
        return s
    cut = s[: SUMMARY_MAX_CHARS - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _build_context_block(ctx: RawContext) -> str:
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

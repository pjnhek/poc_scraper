from __future__ import annotations

from src.clients.protocols import BrowserbaseLike, ExaLike
from src.enrich import ABOUT_TEXT_MIN_CHARS, RawContext, _number_justifications, collect_context
from src.models import Account, Citation, EvidencePack, Justification, NewsItem

# MCP-boundary caps (D-03). Values are Claude's Discretion, no env knobs
# (Phase 9 D-09 principle: the Exa results clamp is Phase 11 scope, not this).
ABOUT_TEXT_MCP_CAP = 2000
JUSTIFICATION_SUMMARY_MCP_CAP = 300
NEWS_ITEM_MCP_CAP = 10
CITATION_URL_MCP_CAP = 2048
EVIDENCE_PACK_MAX_BYTES = 24_000


def _truncate_words(text: str, cap: int) -> str:
    """Cut text at a word boundary and append an ellipsis, never a hard slice.

    Mirrors src.enrich._clean_summary's mechanic so MCP-boundary truncation
    reads the same as the CLI's existing cell-display truncation.
    """
    if len(text) <= cap:
        return text
    cut = text[: cap - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _truncate_utf8_words(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    ellipsis = "…"
    remaining = max_bytes - len(ellipsis.encode("utf-8"))
    if remaining <= 0:
        return ""

    chars: list[str] = []
    used = 0
    for char in text:
        size = len(char.encode("utf-8"))
        if used + size > remaining:
            break
        chars.append(char)
        used += size

    prefix = "".join(chars)
    ended_at_word_boundary = bool(prefix and prefix[-1].isspace())
    prefix = prefix.rstrip()
    if prefix and not ended_at_word_boundary and any(char.isspace() for char in prefix):
        prefix = prefix.rsplit(maxsplit=1)[0].rstrip()
    return prefix + ellipsis if prefix else ""


def _mcp_citation(citation: Citation) -> Citation:
    return citation.model_copy(update={"title": None, "snippet": None})


def _mcp_news(item: NewsItem) -> NewsItem:
    return item.model_copy(
        update={
            "headline": _truncate_words(item.headline, JUSTIFICATION_SUMMARY_MCP_CAP),
            "summary": _truncate_words(item.summary, JUSTIFICATION_SUMMARY_MCP_CAP),
            "citation": _mcp_citation(item.citation),
        }
    )


def _serialized_size(pack: EvidencePack) -> int:
    return len(pack.model_dump_json().encode("utf-8"))


def _url_within_cap(citation: Citation) -> bool:
    return len(str(citation.url).encode("utf-8")) <= CITATION_URL_MCP_CAP


def _candidate_pack(
    about_text: str,
    about_citations: tuple[Citation, ...],
    news_items: tuple[NewsItem, ...],
) -> EvidencePack:
    justifications = _number_justifications(about_citations, news_items)
    safe_justifications: tuple[Justification, ...] = tuple(
        justification.model_copy(
            update={
                "summary": _truncate_words(justification.summary, JUSTIFICATION_SUMMARY_MCP_CAP),
                "citation": _mcp_citation(justification.citation),
            }
        )
        for justification in justifications
    )
    safe_news = [_mcp_news(item) for item in news_items]
    return EvidencePack.from_context(
        about_text=about_text,
        news_items=safe_news,
        justifications=safe_justifications,
        about_text_min_chars=ABOUT_TEXT_MIN_CHARS,
    )


def _pack_with_largest_fitting_about_text(
    about_text: str,
    about_citations: tuple[Citation, ...],
    news_items: tuple[NewsItem, ...],
) -> EvidencePack | None:
    low = 0
    high = len(about_text.encode("utf-8"))
    best: EvidencePack | None = None
    while low <= high:
        allowance = (low + high) // 2
        candidate = _candidate_pack(
            _truncate_utf8_words(about_text, allowance), about_citations, news_items
        )
        if _serialized_size(candidate) <= EVIDENCE_PACK_MAX_BYTES:
            best = candidate
            low = allowance + 1
        else:
            high = allowance - 1
    return best


def _fit_pack_to_byte_budget(
    about_text: str,
    about_citations: tuple[Citation, ...],
    news_items: tuple[NewsItem, ...],
) -> EvidencePack:
    retained_news = news_items
    candidate = _candidate_pack(about_text, about_citations, retained_news)
    if _serialized_size(candidate) <= EVIDENCE_PACK_MAX_BYTES:
        return candidate

    while retained_news:
        retained_news = retained_news[:-1]
        candidate = _candidate_pack(about_text, about_citations, retained_news)
        if _serialized_size(candidate) <= EVIDENCE_PACK_MAX_BYTES:
            return candidate

    retained_about = about_citations
    while retained_about:
        fitted = _pack_with_largest_fitting_about_text(about_text, retained_about, ())
        if fitted is not None:
            return fitted
        retained_about = retained_about[:-1]

    empty = _candidate_pack("", (), ())
    assert _serialized_size(empty) <= EVIDENCE_PACK_MAX_BYTES
    return empty


def pack_from_context(ctx: RawContext) -> EvidencePack:
    source_units_present = bool(ctx.about_citations or ctx.news_items)
    about_citations = tuple(
        citation for citation in ctx.about_citations if _url_within_cap(citation)
    )
    valid_news = tuple(
        item for item in ctx.news_items if _url_within_cap(item.citation)
    )
    news = valid_news[:NEWS_ITEM_MCP_CAP]
    about_text = _truncate_words(ctx.about_text, ABOUT_TEXT_MCP_CAP)
    if source_units_present and not about_citations and not news:
        return _fit_pack_to_byte_budget("", (), ())
    pack = _fit_pack_to_byte_budget(about_text, about_citations, news)
    assert _serialized_size(pack) <= EVIDENCE_PACK_MAX_BYTES
    return pack


async def build_evidence_pack(
    account: Account, *, exa: ExaLike, browserbase: BrowserbaseLike
) -> EvidencePack:
    ctx = await collect_context(account, exa=exa, browserbase=browserbase)
    return pack_from_context(ctx)

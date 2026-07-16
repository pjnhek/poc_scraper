from __future__ import annotations

from src.clients.protocols import BrowserbaseLike, ExaLike
from src.enrich import ABOUT_TEXT_MIN_CHARS, RawContext, _number_justifications, collect_context
from src.models import Account, EvidencePack, Justification

# MCP-boundary caps (D-03). Values are Claude's Discretion, no env knobs
# (Phase 9 D-09 principle: the Exa results clamp is Phase 11 scope, not this).
ABOUT_TEXT_MCP_CAP = 2000
JUSTIFICATION_SUMMARY_MCP_CAP = 300
NEWS_ITEM_MCP_CAP = 10


def _truncate_words(text: str, cap: int) -> str:
    """Cut text at a word boundary and append an ellipsis, never a hard slice.

    Mirrors src.enrich._clean_summary's mechanic so MCP-boundary truncation
    reads the same as the CLI's existing cell-display truncation.
    """
    if len(text) <= cap:
        return text
    cut = text[: cap - 1].rsplit(" ", 1)[0]
    return cut + "…"


def pack_from_context(ctx: RawContext) -> EvidencePack:
    # Cap news FIRST so justification numbering and the news field agree;
    # numbering the uncapped news tuple would emit indices for items the
    # payload never actually includes.
    news = list(ctx.news_items)[:NEWS_ITEM_MCP_CAP]
    justifications = _number_justifications(ctx.about_citations, tuple(news))
    capped_justifications: tuple[Justification, ...] = tuple(
        (
            j
            if len(j.summary) <= JUSTIFICATION_SUMMARY_MCP_CAP
            else j.model_copy(
                update={"summary": _truncate_words(j.summary, JUSTIFICATION_SUMMARY_MCP_CAP)}
            )
        )
        for j in justifications
    )
    about_text = _truncate_words(ctx.about_text, ABOUT_TEXT_MCP_CAP)
    return EvidencePack.from_context(
        about_text=about_text,
        news_items=news,
        justifications=capped_justifications,
        about_text_min_chars=ABOUT_TEXT_MIN_CHARS,
    )


async def build_evidence_pack(
    account: Account, *, exa: ExaLike, browserbase: BrowserbaseLike
) -> EvidencePack:
    ctx = await collect_context(account, exa=exa, browserbase=browserbase)
    return pack_from_context(ctx)

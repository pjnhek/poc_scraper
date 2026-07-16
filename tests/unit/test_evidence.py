from __future__ import annotations

from src.enrich import RawContext
from src.mcp_server.evidence import (
    ABOUT_TEXT_MCP_CAP,
    JUSTIFICATION_SUMMARY_MCP_CAP,
    NEWS_ITEM_MCP_CAP,
    _truncate_words,
    pack_from_context,
)
from src.models import Citation, NewsItem


def _citation(url: str, title: str | None = "About") -> Citation:
    return Citation.make(url=url, source="exa", title=title)


def _news(url: str, headline: str = "Headline") -> NewsItem:
    return NewsItem(headline=headline, summary="summary text", citation=Citation.make(url=url, source="exa"))


def test_pack_from_context_caps_about_text_over_cap_at_word_boundary() -> None:
    about_text = "word " * 500  # 2500 chars, well over ABOUT_TEXT_MCP_CAP
    ctx = RawContext(about_text=about_text, about_citations=(), news_items=())

    pack = pack_from_context(ctx)

    assert len(pack.about_text) <= ABOUT_TEXT_MCP_CAP
    assert pack.about_text.endswith("…")
    body = pack.about_text.rstrip("…").rstrip()
    assert all(part == "word" for part in body.split())


def test_pack_from_context_passes_through_about_text_at_or_under_cap() -> None:
    about_text = "word " * 100  # 500 chars, under ABOUT_TEXT_MCP_CAP
    ctx = RawContext(about_text=about_text, about_citations=(), news_items=())

    pack = pack_from_context(ctx)

    assert pack.about_text == about_text


def test_pack_from_context_caps_news_to_ten_and_justifications_agree() -> None:
    about_citations = (_citation("https://example.com/about"),)
    news_items = tuple(_news(f"https://example.com/news/{i}") for i in range(15))
    ctx = RawContext(about_text="x" * 250, about_citations=about_citations, news_items=news_items)

    pack = pack_from_context(ctx)

    assert len(pack.news) == NEWS_ITEM_MCP_CAP
    assert pack.news == tuple(news_items[:NEWS_ITEM_MCP_CAP])
    assert len(pack.justifications) == 1 + NEWS_ITEM_MCP_CAP
    assert [j.index for j in pack.justifications] == list(range(1, 1 + 1 + NEWS_ITEM_MCP_CAP))
    justification_urls = {str(j.citation.url) for j in pack.justifications}
    assert "https://example.com/news/10" not in justification_urls
    assert "https://example.com/news/14" not in justification_urls


def test_truncate_words_caps_justification_summary_over_defensive_ceiling() -> None:
    long_summary = "word " * 100  # ~500 chars, over JUSTIFICATION_SUMMARY_MCP_CAP

    out = _truncate_words(long_summary, JUSTIFICATION_SUMMARY_MCP_CAP)

    assert len(out) <= JUSTIFICATION_SUMMARY_MCP_CAP
    assert out.endswith("…")
    body = out.rstrip("…").rstrip()
    assert all(part == "word" for part in body.split())


def test_truncate_words_passes_through_normal_clean_summary_length() -> None:
    normal_summary = "word " * 20  # ~100 chars, well under both the 140 and 300 caps

    out = _truncate_words(normal_summary, JUSTIFICATION_SUMMARY_MCP_CAP)

    assert out == normal_summary


def test_retrieval_status_honesty_survives_capping() -> None:
    empty_ctx = RawContext(about_text="", about_citations=(), news_items=())
    assert pack_from_context(empty_ctx).retrieval_status == "empty"

    thin_ctx = RawContext(about_text="short text", about_citations=(), news_items=())
    assert pack_from_context(thin_ctx).retrieval_status == "thin"

    rich_ctx = RawContext(about_text="word " * 1000, about_citations=(), news_items=())
    rich_pack = pack_from_context(rich_ctx)
    assert rich_pack.retrieval_status == "ok"
    assert len(rich_pack.about_text) <= ABOUT_TEXT_MCP_CAP


def test_pack_from_context_populates_about_text_on_evidence_pack() -> None:
    ctx = RawContext(about_text="a rich company overview", about_citations=(), news_items=())

    pack = pack_from_context(ctx)

    assert pack.about_text == "a rich company overview"

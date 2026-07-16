from __future__ import annotations

from src.enrich import RawContext
from src.mcp_server.evidence import (
    ABOUT_TEXT_MCP_CAP,
    CITATION_URL_MCP_CAP,
    EVIDENCE_PACK_MAX_BYTES,
    JUSTIFICATION_SUMMARY_MCP_CAP,
    NEWS_ITEM_MCP_CAP,
    _truncate_words,
    pack_from_context,
)
from src.models import Citation, NewsItem


def _citation(url: str, title: str | None = "About") -> Citation:
    return Citation.make(url=url, source="exa", title=title)


def _news(url: str, headline: str = "Headline") -> NewsItem:
    return NewsItem(
        headline=headline, summary="summary text", citation=Citation.make(url=url, source="exa")
    )


def _long_url(path_bytes: int) -> str:
    return "https://example.com/" + ("a" * path_bytes)


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


def test_pack_from_context_makes_every_nested_evidence_path_mcp_safe() -> None:
    long_text = ('quoted \\"value\\" \\\\ path 🚀 ' * 200).strip()
    about_citations = tuple(
        Citation.make(
            url=f"https://example.com/about/{i}",
            source="exa",
            title=long_text,
            snippet=long_text,
        )
        for i in range(5)
    )
    news_items = tuple(
        NewsItem(
            headline=long_text,
            summary=long_text,
            citation=Citation.make(
                url=f"https://example.com/news/{i}",
                source="exa",
                title=long_text,
                snippet=long_text,
            ),
        )
        for i in range(15)
    )
    ctx = RawContext(
        about_text=long_text,
        about_citations=about_citations,
        news_items=news_items,
    )

    pack = pack_from_context(ctx)

    assert len(pack.model_dump_json().encode("utf-8")) <= EVIDENCE_PACK_MAX_BYTES
    assert len(pack.about_text) <= ABOUT_TEXT_MCP_CAP
    assert len(pack.news) <= NEWS_ITEM_MCP_CAP
    assert [item.index for item in pack.justifications] == list(
        range(1, len(pack.justifications) + 1)
    )
    assert all(len(item.summary) <= JUSTIFICATION_SUMMARY_MCP_CAP for item in pack.justifications)
    assert all(item.citation.title is None for item in pack.justifications)
    assert all(item.citation.snippet is None for item in pack.justifications)
    assert all(len(item.headline) <= JUSTIFICATION_SUMMARY_MCP_CAP for item in pack.news)
    assert all(len(item.summary) <= JUSTIFICATION_SUMMARY_MCP_CAP for item in pack.news)
    assert all(item.citation.title is None for item in pack.news)
    assert all(item.citation.snippet is None for item in pack.news)
    assert all(str(item.citation.url) for item in pack.justifications)
    assert about_citations[0].title == long_text
    assert about_citations[0].snippet == long_text
    assert news_items[0].citation.title == long_text
    assert news_items[0].citation.snippet == long_text


def test_pack_from_context_reduces_deterministically_without_rewriting_urls() -> None:
    near_cap_urls = tuple(_long_url(1950 - i) for i in range(15))
    about_citations = tuple(
        Citation.make(url=url, source="exa", title=f"About {i}")
        for i, url in enumerate(near_cap_urls[:5])
    )
    adversarial_text = ('🚀 \\"quoted\\" \\\\ ' * 300).strip()
    news_items = tuple(
        NewsItem(
            headline=adversarial_text,
            summary=adversarial_text,
            citation=Citation.make(url=url, source="exa", snippet=adversarial_text),
        )
        for url in near_cap_urls[5:]
    )
    ctx = RawContext(
        about_text=adversarial_text,
        about_citations=about_citations,
        news_items=news_items,
    )

    first = pack_from_context(ctx)
    second = pack_from_context(ctx)

    input_urls = {str(citation.url) for citation in about_citations} | {
        str(item.citation.url) for item in news_items
    }
    retained_urls = {str(item.citation.url) for item in first.justifications} | {
        str(item.citation.url) for item in first.news
    }
    assert first == second
    assert len(first.model_dump_json().encode("utf-8")) <= EVIDENCE_PACK_MAX_BYTES
    assert retained_urls <= input_urls
    assert {str(citation.url) for citation in about_citations} <= retained_urls
    assert len(first.news) < NEWS_ITEM_MCP_CAP
    assert [item.index for item in first.justifications] == list(
        range(1, len(first.justifications) + 1)
    )


def test_pack_from_context_drops_over_limit_url_as_an_indivisible_unit() -> None:
    safe = Citation.make(url="https://example.com/about", source="exa", title="About")
    over_limit = Citation.make(
        url=_long_url(CITATION_URL_MCP_CAP),
        source="exa",
        title="Oversized provenance",
    )
    assert len(str(over_limit.url).encode("utf-8")) > CITATION_URL_MCP_CAP
    ctx = RawContext(
        about_text="x" * 500,
        about_citations=(safe, over_limit),
        news_items=(),
    )

    pack = pack_from_context(ctx)

    retained_urls = [str(item.citation.url) for item in pack.justifications]
    assert retained_urls == [str(safe.url)]
    assert str(over_limit.url) not in retained_urls
    assert len(pack.model_dump_json().encode("utf-8")) <= EVIDENCE_PACK_MAX_BYTES


def test_pack_from_context_filters_invalid_news_before_count_cap() -> None:
    over_limit_news = tuple(
        _news(_long_url(CITATION_URL_MCP_CAP), headline=f"Invalid {index}")
        for index in range(NEWS_ITEM_MCP_CAP)
    )
    safe = _news("https://example.com/news/safe", headline="Safe")
    ctx = RawContext(
        about_text="",
        about_citations=(),
        news_items=(*over_limit_news, safe),
    )

    pack = pack_from_context(ctx)

    assert pack.news == (safe,)
    assert str(pack.news[0].citation.url) == "https://example.com/news/safe"
    assert [item.index for item in pack.justifications] == [1]
    assert str(pack.justifications[0].citation.url) == "https://example.com/news/safe"
    assert pack.retrieval_status == "ok"
    assert len(pack.model_dump_json().encode("utf-8")) <= EVIDENCE_PACK_MAX_BYTES


def test_pack_from_context_keeps_first_ten_valid_news_in_source_order() -> None:
    valid_news = tuple(
        _news(f"https://example.com/news/{index}", headline=f"Valid {index}")
        for index in range(NEWS_ITEM_MCP_CAP + 2)
    )
    source_news = tuple(
        item
        for index, valid in enumerate(valid_news)
        for item in (_news(_long_url(CITATION_URL_MCP_CAP), headline=f"Invalid {index}"), valid)
    )
    ctx = RawContext(about_text="", about_citations=(), news_items=source_news)

    pack = pack_from_context(ctx)

    assert pack.news == valid_news[:NEWS_ITEM_MCP_CAP]
    assert [str(item.citation.url) for item in pack.news] == [
        str(item.citation.url) for item in valid_news[:NEWS_ITEM_MCP_CAP]
    ]
    assert [item.index for item in pack.justifications] == list(range(1, NEWS_ITEM_MCP_CAP + 1))


def test_pack_from_context_returns_honest_empty_pack_when_no_provenance_can_fit() -> None:
    over_limit = Citation.make(
        url=_long_url(CITATION_URL_MCP_CAP),
        source="exa",
        snippet="retrieved evidence",
    )
    ctx = RawContext(
        about_text="uncited company text",
        about_citations=(over_limit,),
        news_items=(),
    )

    pack = pack_from_context(ctx)

    assert pack.retrieval_status == "empty"
    assert pack.about_text == ""
    assert pack.news == ()
    assert pack.justifications == ()
    assert len(pack.model_dump_json().encode("utf-8")) <= EVIDENCE_PACK_MAX_BYTES

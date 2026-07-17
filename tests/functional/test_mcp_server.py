from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import AnyUrl

from evals.report import REPORT_PATH
from src.clients.browserbase_client import NullBrowserbase
from src.clients.exa_client import ExaClient, ExaResult
from src.clients.protocols import ExaLike
from src.config import Settings
from src.icp_config import DEFAULT_CONFIG_PATH
from src.mcp_server.limits import DemoLimiter
from src.mcp_server.server import build_server, resolve_and_log_tier
from src.mcp_server.wiring import DemoClampedExa, ThinDeps, make_thin_lifespan
from tests.functional.test_enrich import FakeExa


def _lifespan_factory(
    exa: ExaLike,
    limiter: DemoLimiter | None = None,
) -> Callable[[FastMCP], AbstractAsyncContextManager[ThinDeps]]:
    @asynccontextmanager
    async def lifespan(_app: FastMCP) -> AsyncIterator[ThinDeps]:
        yield ThinDeps(exa=exa, browserbase=NullBrowserbase(), limiter=limiter)

    return lifespan


class FakeClock:
    """Injected clock for limiter tests: no wall-clock dependence (roadmap criterion 3)."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now

    def advance(self, minutes: float) -> None:
        self._now += timedelta(minutes=minutes)


class RaisingExa:
    """FakeExa variant whose search_about raises, for provider/unexpected error tests."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        raise self._exc

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        return []


class RecordingExa:
    """Records the num_results kwarg it receives, for DemoClampedExa forwarding tests."""

    def __init__(self) -> None:
        self.about_num_results: int | None = None
        self.news_num_results: int | None = None

    async def search_about(self, domain: str, num_results: int = 5) -> list[ExaResult]:
        self.about_num_results = num_results
        return []

    async def search_news(
        self, domain: str, days: int = 90, num_results: int = 8
    ) -> list[ExaResult]:
        self.news_num_results = num_results
        return []


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.exa.ai/search")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def _exa_about(text: str = "Notion is a workspace tool. " * 30) -> ExaResult:
    return ExaResult(
        url="https://notion.so/about",
        title="About Notion",
        snippet=text,
        published_at=None,
    )


def _exa_news(url: str = "https://techcrunch.com/notion") -> ExaResult:
    return ExaResult(
        url=url,
        title="Notion launches AI",
        snippet="Notion shipped a new AI feature today.",
        published_at=None,
    )


@pytest.mark.asyncio
async def test_happy_path_returns_structured_evidence_pack() -> None:
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["retrieval_status"] == "ok"
    justifications = result.structuredContent["justifications"]
    assert len(justifications) > 0
    for j in justifications:
        assert j["index"] >= 1
        assert j["summary"]
        assert j["citation"]["url"]
    assert isinstance(result.structuredContent["about_text"], str)
    assert result.structuredContent["about_text"] != ""


@pytest.mark.asyncio
async def test_empty_retrieval_is_not_an_error() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "dead.example"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["retrieval_status"] == "empty"


@pytest.mark.parametrize(
    "domain",
    [
        "example.com/path",
        "example.com?query=yes",
        "example.com#fragment",
        "example.com?",
        "example.com#",
        "https://example.com/?",
        "https://example.com/#",
        "https://user@example.com",
        "example.com:443",
        "example.com\n",
        "example.com\t",
        "a..example.com",
        "-leading.example",
        "trailing-.example",
        f"{'a' * 64}.example",
        f"{'a' * 63}.{'b' * 63}.{'c' * 63}.{'d' * 62}.com",
        "127.0.0.1",
        "https://127.0.0.1/",
        "2001:db8::1",
        "[2001:db8::1]",
        "https://[2001:db8::1]/",
        "xn--a.example",
    ],
)
@pytest.mark.asyncio
async def test_invalid_domain_sanitized_error_before_provider_access(domain: str) -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": domain})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "invalid domain" in text
    assert "Traceback" not in text
    assert "/Users/" not in text
    assert exa.calls == []


@pytest.mark.asyncio
async def test_invalid_domain_error_is_bounded_without_raw_input_reflection() -> None:
    raw_suffix = "distinctive-raw-suffix.example"
    domain = f"{'x' * 1_000_000}.{raw_suffix}"
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": domain})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "invalid domain" in text
    assert len(text.encode("utf-8")) <= 256
    assert raw_suffix not in text
    assert exa.calls == []


@pytest.mark.asyncio
async def test_provider_failure_sanitized_error() -> None:
    exa = RaisingExa(httpx.HTTPError("connect boom secret-host"))
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "retrieval unavailable, try again" in text
    assert "secret-host" not in text


@pytest.mark.asyncio
async def test_unexpected_exception_sanitized_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exa = RaisingExa(RuntimeError("/private/path/leak"))
    app = build_server(lifespan=_lifespan_factory(exa))

    with caplog.at_level(logging.WARNING):
        async with create_connected_server_and_client_session(app) as client:
            result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "internal error" in text
    assert "/private/path/leak" not in text
    assert any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_annotations_and_description_over_the_wire() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_tools()

    tool = listed.tools[0]
    assert tool.name == "get_account_evidence"
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.description is not None
    assert "[N]" in tool.description


def test_tier_logging_thin(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]

    with caplog.at_level(logging.INFO):
        tier = resolve_and_log_tier(settings)

    assert tier == "thin"
    assert any("thin" in record.message for record in caplog.records)


def test_tier_logging_full(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        deepseek_api_key="y",
        browserbase_api_key="z",
        browserbase_project_id="p",
    )

    with caplog.at_level(logging.INFO):
        tier = resolve_and_log_tier(settings)

    assert tier == "full"
    assert any("full" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_demo_per_ip_refusal_over_stdio_shared_bucket() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=2, daily_cap=100, clock=clock)
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        first = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        second = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        third = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert first.isError is False
    assert second.isError is False
    assert third.isError is True
    text = third.content[0].text  # type: ignore[union-attr]
    # No transport attaches a Request over the in-memory session (stdio-equivalent),
    # so the fail-closed shared bucket is what all three calls share (D-01).
    expected_reset = (clock() + timedelta(hours=1)).strftime("%H:%M")
    assert "rate limit reached, resets at " in text
    assert expected_reset in text


@pytest.mark.asyncio
async def test_demo_rolling_window_resets_after_clock_advance() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=2, daily_cap=100, clock=clock)
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        refused = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        assert refused.isError is True

        clock.advance(61)
        allowed_again = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert allowed_again.isError is False


@pytest.mark.asyncio
async def test_demo_refusal_consumes_no_exa_credit() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=1, daily_cap=100, clock=clock)
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        calls_before = list(exa.calls)
        refused = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert refused.isError is True
    assert exa.calls == calls_before


@pytest.mark.asyncio
async def test_demo_daily_cap_exact_message() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=100, daily_cap=1, clock=clock)
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        first = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        second = await client.call_tool("get_account_evidence", {"domain": "linear.app"})

    assert first.isError is False
    assert second.isError is True
    text = second.content[0].text  # type: ignore[union-attr]
    assert "demo budget spent for today, resets at 00:00 UTC" in text


@pytest.mark.asyncio
async def test_demo_none_is_unlimited() -> None:
    exa = FakeExa(about=[_exa_about()], news=[_exa_news()])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=None))

    async with create_connected_server_and_client_session(app) as client:
        results = [
            await client.call_tool("get_account_evidence", {"domain": "notion.so"})
            for _ in range(8)
        ]

    assert all(result.isError is False for result in results)


@pytest.mark.asyncio
async def test_demo_success_response_identical_with_and_without_limiter() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=100, daily_cap=100, clock=clock)
    exa_limited = FakeExa(about=[_exa_about()], news=[_exa_news()])
    exa_unlimited = FakeExa(about=[_exa_about()], news=[_exa_news()])

    app_limited = build_server(lifespan=_lifespan_factory(exa_limited, limiter=limiter))
    app_unlimited = build_server(lifespan=_lifespan_factory(exa_unlimited, limiter=None))

    async with create_connected_server_and_client_session(app_limited) as client:
        limited_result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
    async with create_connected_server_and_client_session(app_unlimited) as client:
        unlimited_result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert limited_result.isError is False
    assert unlimited_result.isError is False
    assert limited_result.structuredContent == unlimited_result.structuredContent


@pytest.mark.asyncio
async def test_demo_clamped_exa_forwards_min_of_requested_and_max() -> None:
    recording = RecordingExa()
    clamped = DemoClampedExa(recording, max_results=2)

    await clamped.search_about("notion.so")
    assert recording.about_num_results == 2

    await clamped.search_news("notion.so")
    assert recording.news_num_results == 2

    await clamped.search_about("notion.so", num_results=1)
    assert recording.about_num_results == 1


@pytest.mark.asyncio
async def test_lifespan_demo_mode_builds_clamped_exa_and_limiter() -> None:
    settings = Settings(_env_file=None, exa_api_key="x", mcp_demo_mode=True)  # type: ignore[call-arg]
    lifespan = make_thin_lifespan(settings)
    app = FastMCP("test")

    async with lifespan(app) as deps:
        assert deps.limiter is not None
        assert isinstance(deps.exa, DemoClampedExa)


@pytest.mark.asyncio
async def test_lifespan_demo_mode_forces_null_browserbase_despite_credentials() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        browserbase_api_key="x",
        browserbase_project_id="y",
        mcp_demo_mode=True,
    )
    lifespan = make_thin_lifespan(settings)
    app = FastMCP("test")

    async with lifespan(app) as deps:
        assert isinstance(deps.browserbase, NullBrowserbase)
        assert deps.limiter is not None
        assert isinstance(deps.exa, DemoClampedExa)


@pytest.mark.asyncio
async def test_lifespan_non_demo_mode_builds_plain_exa_and_no_limiter() -> None:
    settings = Settings(_env_file=None, exa_api_key="x")  # type: ignore[call-arg]
    lifespan = make_thin_lifespan(settings)
    app = FastMCP("test")

    async with lifespan(app) as deps:
        assert deps.limiter is None
        assert isinstance(deps.exa, ExaClient)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [402, 429])
async def test_demo_exhaustion_masquerades_as_daily_cap(status_code: int) -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=100, daily_cap=100, clock=clock)
    exa = RaisingExa(_http_status_error(status_code))
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "demo budget spent for today, resets at 00:00 UTC" in text


@pytest.mark.asyncio
async def test_non_demo_exhaustion_keeps_generic_wording() -> None:
    exa = RaisingExa(_http_status_error(402))
    app = build_server(lifespan=_lifespan_factory(exa, limiter=None))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "retrieval unavailable, try again" in text


@pytest.mark.asyncio
async def test_demo_non_exhaustion_status_keeps_generic_wording() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=100, daily_cap=100, clock=clock)
    exa = RaisingExa(_http_status_error(500))
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "retrieval unavailable, try again" in text


@pytest.mark.asyncio
async def test_demo_mid_flight_failure_still_consumes_quota() -> None:
    clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=1, daily_cap=100, clock=clock)
    exa = RaisingExa(_http_status_error(402))
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        first = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        second = await client.call_tool("get_account_evidence", {"domain": "notion.so"})

    assert first.isError is True
    first_text = first.content[0].text  # type: ignore[union-attr]
    assert "demo budget spent for today, resets at 00:00 UTC" in first_text

    assert second.isError is True
    second_text = second.content[0].text  # type: ignore[union-attr]
    assert "rate limit reached" in second_text


@pytest.mark.asyncio
async def test_rubric_resource_serves_verbatim_yaml() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.read_resource(AnyUrl("icp://rubric"))

    content = result.contents[0]
    assert content.text == DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert content.mimeType == "application/yaml"


@pytest.mark.asyncio
async def test_eval_report_resource_serves_verbatim_markdown() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.read_resource(AnyUrl("icp://eval-report"))

    content = result.contents[0]
    assert content.text == REPORT_PATH.read_text(encoding="utf-8")  # type: ignore[union-attr]
    assert content.mimeType == "text/markdown"


@pytest.mark.asyncio
async def test_list_resources_includes_rubric_and_eval_report() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_resources()

    uris = {str(resource.uri) for resource in listed.resources}
    assert "icp://rubric" in uris
    assert "icp://eval-report" in uris


@pytest.mark.asyncio
async def test_research_account_prompt_contains_required_elements() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.get_prompt("research_account", {"domain": "notion.so"})

    assert len(result.messages) >= 1
    message = result.messages[0]
    assert message.role == "user"
    text = message.content.text  # type: ignore[union-attr]
    for required in ("icp://rubric", "get_account_evidence", "notion.so", "[N]", "drop", "fabricate"):
        assert required in text


@pytest.mark.asyncio
async def test_research_account_prompt_never_mentions_full_tier_tool() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.get_prompt("research_account", {"domain": "notion.so"})

    text = result.messages[0].content.text  # type: ignore[union-attr]
    assert "research_account_full" not in text


@pytest.mark.asyncio
async def test_list_prompts_includes_research_account_with_required_domain_arg() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_prompts()

    prompt = next(p for p in listed.prompts if p.name == "research_account")
    assert prompt.arguments is not None
    domain_arg = next(a for a in prompt.arguments if a.name == "domain")
    assert domain_arg.required is True

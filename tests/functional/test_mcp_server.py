from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.session import ServerSession
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import AnyUrl

from evals.report import REPORT_PATH
from src.clients.browserbase_client import NullBrowserbase
from src.clients.exa_client import ExaClient, ExaResult
from src.clients.nvidia_client import LLMResponse
from src.clients.protocols import ExaLike, LLMClient
from src.config import Settings
from src.icp_config import DEFAULT_CONFIG_PATH
from src.mcp_server.limits import DemoLimiter
from src.mcp_server.server import build_server, resolve_and_log_tier, score_account
from src.mcp_server.wiring import DemoClampedExa, ThinDeps, make_full_lifespan, make_thin_lifespan
from src.pipeline import Deps, build_deps
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

    tool = next(t for t in listed.tools if t.name == "get_account_evidence")
    assert tool.name == "get_account_evidence"
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.description is not None
    assert "[N]" in tool.description


@pytest.mark.asyncio
async def test_score_account_happy_path_returns_structured_result() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "score_account",
            {
                "support_volume": 5,
                "ai_maturity": 4,
                "stage_fit": 4,
                "channel_breadth": 5,
                "domain": "notion.so",
            },
        )

    assert result.isError is False
    assert result.structuredContent is not None
    content = result.structuredContent
    assert content["total"] == 4.5
    assert content["verdict"] == "strong"
    assert content["domain"] == "notion.so"
    assert content["weights"]
    assert content["verdict_thresholds"]
    breakdown = content["breakdown"]
    assert breakdown["support_volume"] == 5.0
    assert breakdown["ai_maturity"] == 4.0
    assert breakdown["stage_fit"] == 4.0
    assert breakdown["channel_breadth"] == 5.0


@pytest.mark.asyncio
async def test_score_account_range_violation_sanitized_error() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "score_account",
            {"support_volume": 6, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "support_volume must be an integer 1-5" in text


@pytest.mark.asyncio
async def test_score_account_string_axis_sdk_type_violation() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "score_account",
            {"support_volume": "abc", "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert result.isError is True


@pytest.mark.asyncio
async def test_score_account_fractional_axis_sdk_type_violation() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "score_account",
            {"support_volume": 3.5, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert result.isError is True


@pytest.mark.asyncio
async def test_score_account_annotations_over_the_wire() -> None:
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_tools()

    tool = next(t for t in listed.tools if t.name == "score_account")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_score_account_ignores_demo_limiter_exhaustion() -> None:
    """SCORE-02: score_account never consults DemoLimiter, so it succeeds
    even when the limiter refuses every get_account_evidence call."""
    clock = FakeClock(datetime(2026, 7, 17, 12, 0, tzinfo=UTC))
    limiter = DemoLimiter(ip_limit=0, daily_cap=0, clock=clock)
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa, limiter=limiter))

    async with create_connected_server_and_client_session(app) as client:
        evidence_result = await client.call_tool("get_account_evidence", {"domain": "notion.so"})
        score_result = await client.call_tool(
            "score_account",
            {"support_volume": 3, "ai_maturity": 3, "stage_fit": 3, "channel_breadth": 3},
        )

    assert evidence_result.isError is True
    assert score_result.isError is False


def test_score_account_signature_has_no_sdk_or_lifespan_parameters() -> None:
    params = list(inspect.signature(score_account).parameters)
    assert params == [
        "support_volume",
        "ai_maturity",
        "stage_fit",
        "channel_breadth",
        "support_volume_reason",
        "ai_maturity_reason",
        "stage_fit_reason",
        "channel_breadth_reason",
        "domain",
    ]


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
async def test_make_full_lifespan_delegates_to_open_deps() -> None:
    """Task 1: full-tier lifespan is a thin wrapper around open_deps.

    Dummy key strings are sufficient because only client construction is
    exercised here (mirrors tests/functional/test_pipeline_open_deps.py) --
    no live network calls occur.
    """
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        deepseek_api_key="y",
        browserbase_api_key="z",
        browserbase_project_id="p",
    )
    lifespan = make_full_lifespan(settings)
    app = FastMCP("test")

    async with lifespan(app) as deps:
        assert isinstance(deps, Deps)
        assert deps.limiter is None
        assert deps.exa is not None
        assert deps.enricher is not None


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
    for required in (
        "icp://rubric",
        "get_account_evidence",
        "notion.so",
        "[N]",
        "drop",
        "fabricate",
    ):
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


@pytest.mark.asyncio
async def test_demo_hides_full_tool_even_with_full_keys_present() -> None:
    """Task 2, Test 1: roadmap success criterion 2.

    MCP_DEMO_MODE with all four full-tier keys present must still resolve
    to the thin tier and hide research_account_full -- not merely refuse it
    at call time (MCP-06's "hidden, not visible-but-refusing" requirement).
    """
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        deepseek_api_key="y",
        browserbase_api_key="z",
        browserbase_project_id="p",
        mcp_demo_mode=True,
    )
    assert settings.mcp_tier() == "thin"

    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa), tier=settings.mcp_tier())

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_tools()

    assert {tool.name for tool in listed.tools} == {"get_account_evidence", "score_account"}


@pytest.mark.asyncio
async def test_full_tool_registered_and_described_over_stdio() -> None:
    """Task 2, Test 2: full tier registers both tools, stdio-style.

    `settings` is left at its default None -- the stdio path -- to prove
    tier gating never re-derives from that parameter (RESEARCH Pitfall 1).
    """
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        exa_api_key="x",
        deepseek_api_key="y",
        browserbase_api_key="z",
        browserbase_project_id="p",
    )
    assert settings.mcp_tier() == "full"

    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa), tier="full")

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_tools()

    names = {tool.name for tool in listed.tools}
    assert names == {"get_account_evidence", "score_account", "research_account_full"}

    full_tool = next(t for t in listed.tools if t.name == "research_account_full")
    assert full_tool.annotations is not None
    assert full_tool.annotations.readOnlyHint is True
    assert full_tool.annotations.destructiveHint is False
    assert full_tool.description is not None
    assert "30-60" in full_tool.description
    assert "run_eval=False" in full_tool.description
    assert "[N]" in full_tool.description


@pytest.mark.asyncio
async def test_build_server_default_tier_registers_thin_tool_only() -> None:
    """Task 2, Test 3: every pre-existing call site keeps its exact behavior."""
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa))

    async with create_connected_server_and_client_session(app) as client:
        listed = await client.list_tools()

    assert {tool.name for tool in listed.tools} == {"get_account_evidence", "score_account"}


def _full_lifespan_factory(
    deps: Deps,
) -> Callable[[FastMCP], AbstractAsyncContextManager[Deps]]:
    """Mirrors `_lifespan_factory` above but yields a caller-prepared full `Deps`
    bundle instead of building one internally -- the tests below construct
    `Deps` via `build_deps` with fake writer/judge LLMs and a FakeExa, stubs
    at the API boundary per the functional-test layer (CLAUDE.md)."""

    @asynccontextmanager
    async def lifespan(_app: FastMCP) -> AsyncIterator[Deps]:
        yield deps

    return lifespan


def _full_about(text: str = "Notion is a workspace tool. " * 30) -> ExaResult:
    # title=None so the justification summary derives from the snippet,
    # guaranteeing high rapidfuzz overlap with the fake writer's claim text
    # (mirrors tests/integration/test_pipeline_failures.py::_exa_about).
    return ExaResult(url="https://notion.so/about", title=None, snippet=text, published_at=None)


class HappyWriterLLM:
    """Fake writer LLM producing valid firmographics/score/contacts/outreach
    JSON for every writer-stage prompt. Kept separate from the judge fake so
    judge invocations are independently countable (D-02 honesty test)."""

    def __init__(self) -> None:
        self.calls = 0

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        self.calls += 1
        if "You are a sales analyst" in system:
            return LLMResponse(
                text=(
                    '{"name":"Notion","industry":"productivity software",'
                    '"headcount_range":"201-500","tech_signals":[]}'
                )
            )
        if "score companies against an ICP rubric" in system:
            return LLMResponse(
                text=(
                    '{"support_volume":5,"support_volume_reason":"r",'
                    '"ai_maturity":5,"ai_maturity_reason":"r",'
                    '"stage_fit":5,"stage_fit_reason":"r",'
                    '"channel_breadth":5,"channel_breadth_reason":"r",'
                    '"justification":"ok"}'
                )
            )
        if "propose the top 3 buyer personas" in system:
            return LLMResponse(
                text=(
                    '[{"role_title":"a","rationale":"r"},'
                    '{"role_title":"b","rationale":"r"},'
                    '{"role_title":"c","rationale":"r"}]'
                )
            )
        if "You write outreach claims from a seller" in system:
            return LLMResponse(
                text=(
                    '{"claims":[{"claim":"Notion is a workspace tool",'
                    '"cited_indices":[1]}],"connective_text":"reach out"}'
                )
            )
        raise AssertionError(f"unscripted writer prompt: {system[:60]}")


class HappyJudgeLLM:
    """Fake judge LLM: every claim cited, groundedness 5.0, never flagged."""

    def __init__(self) -> None:
        self.calls = 0

    async def synthesize(
        self, system: str, context: str, user_prompt: str, max_tokens: int | None = None
    ) -> LLMResponse:
        self.calls += 1
        if "LLM judge evaluating" in system:
            return LLMResponse(
                text=(
                    '{"claims":['
                    '{"text":"x","supported_by":1},'
                    '{"text":"y","supported_by":1},'
                    '{"text":"z","supported_by":1}],'
                    '"icp_relevance":4,"personalization":4,'
                    '"specificity":3,"recency":3}'
                )
            )
        raise AssertionError(f"unscripted judge prompt: {system[:60]}")


def _build_full_test_deps(writer: LLMClient, judge: LLMClient, exa: ExaLike) -> Deps:
    return build_deps(writer=writer, judge=judge, exa=exa, browserbase=NullBrowserbase())


@pytest.mark.asyncio
async def test_full_tool_happy_path_returns_complete_scored_account() -> None:
    """Roadmap success criterion 1 + D-01: the wire payload carries every
    ScoredAccount field and every hook's cited_indices resolve within the
    payload's own enrichment.justifications indices."""
    exa = FakeExa(about=[_full_about()])
    writer = HappyWriterLLM()
    judge = HappyJudgeLLM()
    deps = _build_full_test_deps(writer, judge, exa)
    app = build_server(lifespan=_full_lifespan_factory(deps), tier="full")

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("research_account_full", {"domain": "notion.so"})

    assert result.isError is False
    assert result.structuredContent is not None
    content = result.structuredContent
    for field in (
        "account",
        "status",
        "enrichment",
        "score",
        "contacts",
        "hooks",
        "eval_score",
        "error",
    ):
        assert field in content
    assert content["status"] in {"clean", "low_groundedness", "hook_suppressed", "judge_failed"}

    justifications = content["enrichment"]["justifications"]
    assert len(justifications) > 0
    index_set = {j["index"] for j in justifications}
    for j in justifications:
        assert j["index"] >= 1

    assert content["hooks"], "happy-path fakes must survive the citation gate"
    for hook in content["hooks"]:
        assert set(hook["cited_indices"]).issubset(index_set)


@pytest.mark.asyncio
async def test_full_tool_run_eval_false_skips_judge() -> None:
    """D-02: run_eval=False over the wire yields eval_score null, a
    non-failure status, and zero judge invocations."""
    exa = FakeExa(about=[_full_about()])
    writer = HappyWriterLLM()
    judge = HappyJudgeLLM()
    deps = _build_full_test_deps(writer, judge, exa)
    app = build_server(lifespan=_full_lifespan_factory(deps), tier="full")

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "research_account_full", {"domain": "notion.so", "run_eval": False}
        )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["eval_score"] is None
    assert result.structuredContent["status"] == "clean"
    assert judge.calls == 0


@pytest.mark.asyncio
async def test_full_tool_empty_retrieval_mirrors_sheet_row() -> None:
    """D-03: empty retrieval through the full tool is a SUCCESSFUL result
    carrying error text and hook_suppressed status, never isError."""
    exa = FakeExa(about=[], news=[])
    writer = HappyWriterLLM()
    judge = HappyJudgeLLM()
    deps = _build_full_test_deps(writer, judge, exa)
    app = build_server(lifespan=_full_lifespan_factory(deps), tier="full")

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("research_account_full", {"domain": "dead.example"})

    assert result.isError is False
    content = result.structuredContent
    assert content is not None
    assert content["status"] == "hook_suppressed"
    assert content["error"] == "empty enrichment"
    assert content["score"] is None
    assert content["hooks"] == []


@pytest.mark.asyncio
async def test_full_tool_invalid_domain_sanitized_error() -> None:
    exa = FakeExa(about=[], news=[])
    writer = HappyWriterLLM()
    judge = HappyJudgeLLM()
    deps = _build_full_test_deps(writer, judge, exa)
    app = build_server(lifespan=_full_lifespan_factory(deps), tier="full")

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool("research_account_full", {"domain": "example.com/path"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "invalid domain" in text
    assert "Traceback" not in text
    assert "/Users/" not in text
    assert exa.calls == []


@pytest.mark.asyncio
async def test_full_tool_reports_five_stage_progress_notifications() -> None:
    """D-04: per-stage progress is reported over the actual JSON-RPC
    round-trip on a run_eval=True happy path -- 5 notifications, progress
    1.0..5.0 with total 5.0, in enrich/score/contacts/outreach/eval order."""
    exa = FakeExa(about=[_full_about()])
    writer = HappyWriterLLM()
    judge = HappyJudgeLLM()
    deps = _build_full_test_deps(writer, judge, exa)
    app = build_server(lifespan=_full_lifespan_factory(deps), tier="full")

    progress_events: list[tuple[float, float | None, str | None]] = []

    async def _collect(progress: float, total: float | None, message: str | None) -> None:
        progress_events.append((progress, total, message))

    async with create_connected_server_and_client_session(app) as client:
        result = await client.call_tool(
            "research_account_full",
            {"domain": "notion.so"},
            progress_callback=_collect,
        )

    assert result.isError is False
    assert len(progress_events) == 5
    for expected_progress, (progress, total, message) in zip(
        (1.0, 2.0, 3.0, 4.0, 5.0), progress_events, strict=True
    ):
        assert progress == expected_progress
        assert total == 5.0
        assert message is not None and message.endswith("complete")
    stage_names = [
        message.removesuffix(" complete")
        for (_progress, _total, message) in progress_events
        if message is not None
    ]
    assert stage_names == ["enrich", "score", "contacts", "outreach", "eval"]


@pytest.mark.asyncio
async def test_full_tool_thin_lifespan_misconfiguration_fails_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """WR-01: tier="full" registers research_account_full, but pairing it
    with a thin lifespan (ThinDeps has no enricher/scorer/etc) must fail
    loudly with an explicit misconfiguration message at call time, never the
    sanitized "internal error, try again" reserved for genuine transient
    faults. Mirrors the exact mismatched wiring the review flagged."""
    exa = FakeExa(about=[], news=[])
    app = build_server(lifespan=_lifespan_factory(exa), tier="full")

    with caplog.at_level(logging.ERROR):
        async with create_connected_server_and_client_session(app) as client:
            result = await client.call_tool("research_account_full", {"domain": "notion.so"})

    assert result.isError is True
    text = result.content[0].text  # type: ignore[union-attr]
    assert "misconfiguration" in text
    assert "internal error" not in text
    assert any(record.levelno == logging.ERROR for record in caplog.records)


@pytest.mark.asyncio
async def test_full_tool_progress_send_failure_does_not_discard_result(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-02: a failed progress notification send (e.g. client disconnects
    mid-run) must not discard a completed pipeline run and its already-spent
    writer/judge tokens. Patches ServerSession.send_progress_notification --
    what ctx.report_progress calls -- to raise, then asserts the tool call
    still succeeds with a complete result and the failure is only logged at
    WARNING, never propagated."""

    async def _raise_send_progress(*args: object, **kwargs: object) -> None:
        raise httpx.HTTPError("client disconnected mid-run")

    monkeypatch.setattr(ServerSession, "send_progress_notification", _raise_send_progress)

    exa = FakeExa(about=[_full_about()])
    writer = HappyWriterLLM()
    judge = HappyJudgeLLM()
    deps = _build_full_test_deps(writer, judge, exa)
    app = build_server(lifespan=_full_lifespan_factory(deps), tier="full")

    async def _progress_cb(progress: float, total: float | None, message: str | None) -> None:
        pass

    with caplog.at_level(logging.WARNING):
        async with create_connected_server_and_client_session(app) as client:
            result = await client.call_tool(
                "research_account_full",
                {"domain": "notion.so"},
                progress_callback=_progress_cb,
            )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["status"] in {
        "clean",
        "low_groundedness",
        "hook_suppressed",
        "judge_failed",
    }
    assert result.structuredContent["hooks"], "the completed run must not be discarded"
    assert any("progress notification failed" in record.message for record in caplog.records)

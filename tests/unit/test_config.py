from __future__ import annotations

import pytest

from src.config import Settings


def test_defaults_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "NVIDIA_API_KEY",
        "DEEPSEEK_API_KEY",
        "EXA_API_KEY",
        "BROWSERBASE_API_KEY",
        "BROWSERBASE_PROJECT_ID",
        "LLM_PROVIDER",
        "PIPELINE_CONCURRENCY",
    ):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    # No DeepSeek key -> falls back to NVIDIA defaults.
    assert s.resolved_provider == "nvidia"
    assert s.writer_model == "minimaxai/minimax-m2.7"
    assert s.judge_model == "bytedance/seed-oss-36b-instruct"
    assert s.judge_reasoning_budget == 0
    assert s.pipeline_concurrency == 5


def test_deepseek_key_auto_selects_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.resolved_provider == "deepseek"
    assert s.writer_model == "deepseek-v4-flash"
    # Both writer and judge default to flash for demo-friendly latency.
    # Separation comes from thinking-mode toggle + reasoning_effort, not
    # from different model weights.
    assert s.judge_model == "deepseek-v4-flash"


def test_explicit_provider_wins_over_auto_select(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.resolved_provider == "nvidia"
    assert s.writer_model == "minimaxai/minimax-m2.7"


def test_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-test")
    monkeypatch.setenv("EXA_API_KEY", "exa-test")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb-test")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj-test")
    monkeypatch.setenv("PIPELINE_CONCURRENCY", "10")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.nvidia_api_key == "nv-test"
    assert s.exa_api_key == "exa-test"
    assert s.pipeline_concurrency == 10


def test_run_limit_default_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_LIMIT", raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.run_limit is None


def test_run_limit_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_LIMIT", "3")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.run_limit == 3


def test_run_limit_rejects_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("RUN_LIMIT", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_nvidia_writer_and_judge_default_to_different_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On NVIDIA we still rely on different model families for separation;
    DeepSeek shares one model and uses thinking-mode + reasoning_effort instead."""
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.writer_model != s.judge_model


def test_require_for_pipeline_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "NVIDIA_API_KEY",
        "DEEPSEEK_API_KEY",
        "EXA_API_KEY",
        "BROWSERBASE_API_KEY",
        "BROWSERBASE_PROJECT_ID",
        "LLM_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        s.require_for_pipeline()


def test_require_for_pipeline_complains_about_deepseek_when_provider_is_deepseek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        s.require_for_pipeline()


def test_require_for_pipeline_passes_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nv")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    s.require_for_pipeline()


def _clear_mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "NVIDIA_API_KEY",
        "DEEPSEEK_API_KEY",
        "EXA_API_KEY",
        "BROWSERBASE_API_KEY",
        "BROWSERBASE_PROJECT_ID",
        "LLM_PROVIDER",
        "MCP_DEMO_MODE",
        "MCP_DEMO_IP_LIMIT",
        "MCP_DEMO_DAILY_CAP",
        "MCP_DEMO_EXA_RESULTS",
        "MCP_HTTP_HOST",
        "MCP_HTTP_PORT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_mcp_demo_mode_defaults_to_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mcp_env(monkeypatch)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_demo_mode is False


def test_mcp_tier_thin_with_only_exa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("EXA_API_KEY", "exa")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_tier() == "thin"


def test_mcp_tier_full_with_provider_and_browserbase_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_tier() == "full"


def test_mcp_tier_demo_mode_forces_thin_regardless_of_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj")
    monkeypatch.setenv("MCP_DEMO_MODE", "1")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_tier() == "thin"


def test_mcp_tier_raises_when_exa_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mcp_env(monkeypatch)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="EXA_API_KEY"):
        s.mcp_tier()


def test_mcp_tier_raises_when_exa_key_missing_even_in_demo_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("MCP_DEMO_MODE", "1")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="EXA_API_KEY"):
        s.mcp_tier()


def test_mcp_tier_thin_when_resolved_provider_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("NVIDIA_API_KEY", "nv")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_tier() == "thin"


def test_mcp_tier_thin_when_browserbase_project_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_tier() == "thin"


def test_mcp_demo_and_http_knobs_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mcp_env(monkeypatch)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_demo_ip_limit == 5
    assert s.mcp_demo_daily_cap == 25
    assert s.mcp_demo_exa_results == 5
    assert s.mcp_http_port == 8000
    assert s.mcp_http_host == "127.0.0.1"


def test_mcp_demo_and_http_knobs_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("MCP_DEMO_IP_LIMIT", "2")
    monkeypatch.setenv("MCP_DEMO_DAILY_CAP", "3")
    monkeypatch.setenv("MCP_DEMO_EXA_RESULTS", "1")
    monkeypatch.setenv("MCP_HTTP_PORT", "9000")
    monkeypatch.setenv("MCP_HTTP_HOST", "0.0.0.0")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.mcp_demo_ip_limit == 2
    assert s.mcp_demo_daily_cap == 3
    assert s.mcp_demo_exa_results == 1
    assert s.mcp_http_port == 9000
    assert s.mcp_http_host == "0.0.0.0"

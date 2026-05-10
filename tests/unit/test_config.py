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
    assert s.judge_model == "deepseek-v4-pro"


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


def test_writer_and_judge_default_to_different_models() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (
        s.writer_model != s.judge_model
    ), "writer and judge must default to different models to avoid self-grading bias"


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

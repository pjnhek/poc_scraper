from __future__ import annotations

import pytest

from src.config import Settings


def test_defaults_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ANTHROPIC_API_KEY",
        "EXA_API_KEY",
        "BROWSERBASE_API_KEY",
        "BROWSERBASE_PROJECT_ID",
        "ANTHROPIC_MODEL",
        "PIPELINE_CONCURRENCY",
    ):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.anthropic_model == "claude-sonnet-4-6"
    assert s.pipeline_concurrency == 5
    assert s.eval_groundedness_threshold == 6.0


def test_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("EXA_API_KEY", "exa-test")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb-test")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj-test")
    monkeypatch.setenv("PIPELINE_CONCURRENCY", "10")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.anthropic_api_key == "sk-test"
    assert s.exa_api_key == "exa-test"
    assert s.pipeline_concurrency == 10


def test_require_for_pipeline_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ANTHROPIC_API_KEY",
        "EXA_API_KEY",
        "BROWSERBASE_API_KEY",
        "BROWSERBASE_PROJECT_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        s.require_for_pipeline()


def test_require_for_pipeline_passes_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    monkeypatch.setenv("EXA_API_KEY", "exa")
    monkeypatch.setenv("BROWSERBASE_API_KEY", "bb")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "proj")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    s.require_for_pipeline()

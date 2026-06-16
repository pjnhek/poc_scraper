from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from openai import APIError

from src.clients.nvidia_client import GenerationParams, NvidiaClient


async def _no_sleep(_seconds: float) -> None:
    return None


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse("synthesized")


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeOpenAI:
    def __init__(self) -> None:
        self.chat = _FakeChat()


@pytest.mark.asyncio
async def test_synthesize_concatenates_context_into_user_message() -> None:
    fake = _FakeOpenAI()
    client = NvidiaClient(api_key="k", model="m", client=fake)

    result = await client.synthesize(
        system="you are an analyst",
        context="<news>...</news>",
        user_prompt="score the account",
    )

    assert result.text == "synthesized"
    call = fake.chat.completions.calls[0]
    assert call["messages"][0] == {"role": "system", "content": "you are an analyst"}
    assert call["messages"][1]["role"] == "user"
    assert "<news>...</news>" in call["messages"][1]["content"]
    assert "score the account" in call["messages"][1]["content"]


@pytest.mark.asyncio
async def test_uses_configured_model_and_params() -> None:
    fake = _FakeOpenAI()
    params = GenerationParams(temperature=0.6, top_p=0.7, max_tokens=4096)
    client = NvidiaClient(
        api_key="k", model="mistralai/mistral-nemotron", params=params, client=fake
    )
    await client.synthesize("s", "ctx", "p")
    call = fake.chat.completions.calls[0]
    assert call["model"] == "mistralai/mistral-nemotron"
    assert call["temperature"] == 0.6
    assert call["top_p"] == 0.7
    assert call["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_max_tokens_override_wins() -> None:
    fake = _FakeOpenAI()
    client = NvidiaClient(
        api_key="k", model="m", params=GenerationParams(max_tokens=4096), client=fake
    )
    await client.synthesize("s", "ctx", "p", max_tokens=512)
    assert fake.chat.completions.calls[0]["max_tokens"] == 512


@pytest.mark.asyncio
async def test_reasoning_budget_passes_thinking_budget_in_extra_body() -> None:
    fake = _FakeOpenAI()
    params = GenerationParams(reasoning_budget=-1)
    client = NvidiaClient(
        api_key="k", model="bytedance/seed-oss-36b-instruct", params=params, client=fake
    )
    await client.synthesize("s", "ctx", "p")
    call = fake.chat.completions.calls[0]
    assert call["extra_body"] == {"thinking_budget": -1}


@pytest.mark.asyncio
async def test_no_reasoning_budget_omits_extra_body() -> None:
    fake = _FakeOpenAI()
    client = NvidiaClient(api_key="k", model="m", client=fake)
    await client.synthesize("s", "ctx", "p")
    assert "extra_body" not in fake.chat.completions.calls[0]


@pytest.mark.asyncio
async def test_reasoning_effort_passes_through_as_top_level_kwarg() -> None:
    fake = _FakeOpenAI()
    params = GenerationParams(reasoning_effort="high")
    client = NvidiaClient(api_key="k", model="deepseek-v4-pro", params=params, client=fake)
    await client.synthesize("s", "ctx", "p")
    call = fake.chat.completions.calls[0]
    assert call["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_json_mode_sets_response_format() -> None:
    fake = _FakeOpenAI()
    params = GenerationParams(json_mode=True)
    client = NvidiaClient(api_key="k", model="m", params=params, client=fake)
    await client.synthesize("s", "ctx", "p")
    call = fake.chat.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_extra_body_thinking_mode_passes_through() -> None:
    fake = _FakeOpenAI()
    params = GenerationParams(extra_body={"thinking": {"type": "enabled"}})
    client = NvidiaClient(api_key="k", model="deepseek-v4-pro", params=params, client=fake)
    await client.synthesize("s", "ctx", "p")
    call = fake.chat.completions.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}


@pytest.mark.asyncio
async def test_base_url_is_configurable() -> None:
    fake = _FakeOpenAI()
    client = NvidiaClient(api_key="k", model="m", base_url="https://api.deepseek.com", client=fake)
    # We can't easily inspect the OpenAI client's base_url through the fake,
    # but the constructor must accept the kwarg without raising.
    await client.synthesize("s", "ctx", "p")
    assert len(fake.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_retries_then_succeeds_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # The LLM call is the most rate-limited path; prove its tenacity retry
    # actually fires. First create() raises a retryable APIError, second
    # succeeds. Patch asyncio.sleep so backoff does not slow the test.
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    class _FlakyCompletions:
        def __init__(self) -> None:
            self.attempts = 0

        async def create(self, **kwargs: Any) -> _FakeResponse:
            self.attempts += 1
            if self.attempts == 1:
                raise APIError(
                    "rate limited",
                    request=httpx.Request("POST", "https://example.com"),
                    body=None,
                )
            return _FakeResponse("recovered")

    flaky = _FlakyCompletions()
    fake = _FakeOpenAI()
    fake.chat.completions = flaky  # type: ignore[assignment]
    client = NvidiaClient(api_key="k", model="m", client=fake)

    result = await client.synthesize("s", "ctx", "p")

    assert result.text == "recovered"
    assert flaky.attempts == 2


@pytest.mark.asyncio
async def test_empty_context_omits_separator() -> None:
    fake = _FakeOpenAI()
    client = NvidiaClient(api_key="k", model="m", client=fake)
    await client.synthesize(system="s", context="", user_prompt="just this")
    user_content = fake.chat.completions.calls[0]["messages"][1]["content"]
    assert user_content == "just this"

from __future__ import annotations

from typing import Any

import pytest

from src.clients.nvidia_client import GenerationParams, NvidiaClient


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
        cached_context="<news>...</news>",
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
async def test_empty_context_omits_separator() -> None:
    fake = _FakeOpenAI()
    client = NvidiaClient(api_key="k", model="m", client=fake)
    await client.synthesize(system="s", cached_context="", user_prompt="just this")
    user_content = fake.chat.completions.calls[0]["messages"][1]["content"]
    assert user_content == "just this"

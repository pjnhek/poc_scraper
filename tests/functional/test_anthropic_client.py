from __future__ import annotations

from typing import Any

import pytest

from src.clients.anthropic_client import AnthropicClient


class _FakeUsage:
    cache_read_input_tokens = 12
    cache_creation_input_tokens = 34


class _FakeBlock:
    type = "text"
    text = "synthesized"


class _FakeResponse:
    content = [_FakeBlock()]
    usage = _FakeUsage()


class _FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse()


class _FakeAnthropic:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


@pytest.mark.asyncio
async def test_synthesize_marks_context_as_cache_control() -> None:
    fake = _FakeAnthropic()
    client = AnthropicClient(api_key="k", client=fake)  # type: ignore[arg-type]

    result = await client.synthesize(
        system="you are a sales analyst",
        cached_context="<news>...</news>",
        user_prompt="score the account",
    )

    assert result.text == "synthesized"
    assert result.cache_read_tokens == 12
    assert result.cache_creation_tokens == 34

    call = fake.messages.calls[0]
    user_blocks = call["messages"][0]["content"]
    assert user_blocks[0]["text"] == "<news>...</news>"
    assert user_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert user_blocks[1]["text"] == "score the account"
    assert "cache_control" not in user_blocks[1]


@pytest.mark.asyncio
async def test_synthesize_uses_configured_model() -> None:
    fake = _FakeAnthropic()
    client = AnthropicClient(api_key="k", model="claude-sonnet-4-6", client=fake)  # type: ignore[arg-type]
    await client.synthesize("s", "ctx", "p")
    assert fake.messages.calls[0]["model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_synthesize_respects_max_tokens_override() -> None:
    fake = _FakeAnthropic()
    client = AnthropicClient(api_key="k", max_tokens=100, client=fake)  # type: ignore[arg-type]
    await client.synthesize("s", "ctx", "p", max_tokens=2048)
    assert fake.messages.calls[0]["max_tokens"] == 2048
